import enum
from construct import Struct, Int16ub, Int32ub, BitStruct, BitsInteger, Flag

# ADSP Control Codes (if control flag is 1)
class ADSPControlCode(enum.IntEnum):
    PROBE_OR_ACK = 0
    OPEN_CONN_REQ = 1
    OPEN_CONN_ACK = 2
    OPEN_CONN_REQ_ACK = 3
    OPEN_CONN_DENY = 4
    CLOSE_CONN = 5
    FORWARD_RESET = 6
    FORWARD_RESET_ACK = 7
    RETRANSMIT = 8

ADSPHeader = Struct(
    "src_conn_id" / Int16ub,
    "dest_conn_id" / Int16ub,
    "seq_num" / Int32ub,
    "ack_num" / Int32ub,
    "window_size" / Int16ub,
    "descriptor" / BitStruct(
        "control" / Flag,
        "ack_req" / Flag,
        "eom" / Flag,
        "attention" / Flag,
        "control_code" / BitsInteger(4)
    )
)

class ADSPState(enum.Enum):
    CLOSED = 0
    LISTENING = 1
    OPENING = 2
    OPEN = 3
    CLOSING = 4

import asyncio
from typing import Optional, Callable, Dict

from typing import Any

class ADSPManager:
    """
    Manages active ADSP connections and listens for incoming connections.
    """
    def __init__(self, node: Any, plugin: Any):
        self.node = node
        self.plugin = plugin
        self.connections: Dict[int, 'ADSPConnection'] = {}
        self.listeners: Dict[int, Callable[[], asyncio.Protocol]] = {}
        self.next_conn_id = 1

    def _generate_conn_id(self) -> int:
        cid = self.next_conn_id
        self.next_conn_id += 1
        return cid

    def remove_connection(self, conn: 'ADSPConnection') -> None:
        if conn.local_conn_id in self.connections:
            del self.connections[conn.local_conn_id]

    async def send_packet(self, dest_node: str, dest_socket: int, local_socket: int, payload: bytes) -> None:
        """Sends an ADSP packet wrapped in DDP."""
        from .ddp import DDPHeader
        ddp_header = {
            "flags_hop_length": {
                "reserved": 0,
                "hop_count": 0,
                "length": 13 + len(payload)
            },
            "checksum": 0,
            "dest_network": 0,
            "src_network": 0,
            "dest_node": 0,
            "src_node": 0,
            "dest_socket": dest_socket,
            "src_socket": local_socket,
            "type": 7 # ADSP DDP Type
        }
        encoded_ddp = DDPHeader.build(ddp_header)
        await self.node.send_datagram(dest_node, 'appletalk', encoded_ddp + payload)

    async def handle_incoming(self, payload: bytes, src_node: str, src_socket: int, local_socket: int) -> None:
        """Process incoming ADSP payload (already stripped of DDP header)."""
        try:
            header_size = ADSPHeader.sizeof()
            header = ADSPHeader.parse(payload[:header_size])
            data = payload[header_size:]

            dest_conn_id = header.dest_conn_id

            # Check if it's for an existing connection
            if dest_conn_id in self.connections:
                conn = self.connections[dest_conn_id]
                await conn.process_packet(header, data)
                return

            # If it's a new connection request to a listening socket
            if header.descriptor.control and header.descriptor.control_code == ADSPControlCode.OPEN_CONN_REQ:
                if local_socket in self.listeners:
                    # Create new connection
                    local_conn_id = self._generate_conn_id()
                    conn = ADSPConnection(local_conn_id, self, src_node, src_socket, local_socket)
                    conn.state = ADSPState.LISTENING

                    protocol_factory = self.listeners[local_socket]
                    protocol = protocol_factory()
                    conn.set_protocol(protocol)

                    self.connections[local_conn_id] = conn
                    await conn.process_packet(header, data)
                else:
                    # Connection denied - not listening on this socket
                    pass
        except Exception as e:
            print(f"ADSP parsing error: {e}")

    async def open_connection(self, dest_node: str, dest_socket: int, local_socket: int) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """
        Open a connection to a remote node/socket and return (reader, writer).
        """
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader(limit=2**16, loop=loop)
        protocol = asyncio.StreamReaderProtocol(reader, loop=loop)

        # Create connection
        local_conn_id = self._generate_conn_id()
        conn = ADSPConnection(local_conn_id, self, dest_node, dest_socket, local_socket)
        conn.set_protocol(protocol)

        self.connections[local_conn_id] = conn

        # Make sure our plugin forwards this socket's traffic to our handle_incoming
        async def incoming_handler(payload: bytes, src_node: str, src_sock: int):
            await self.handle_incoming(payload, src_node, src_sock, local_socket)
        self.plugin.register_upper_layer(local_socket, incoming_handler)

        await conn.connect()

        # We know transport is set by set_protocol
        writer = asyncio.StreamWriter(conn.transport, protocol, reader, loop) # type: ignore
        return reader, writer

    async def start_server(self, client_connected_cb: Callable[[asyncio.StreamReader, asyncio.StreamWriter], Any], local_socket: int) -> 'ADSPServer':
        """
        Start an ADSP server listening on a local socket.
        """
        loop = asyncio.get_running_loop()

        def factory() -> asyncio.StreamReaderProtocol:
            reader = asyncio.StreamReader(limit=2**16, loop=loop)
            protocol = asyncio.StreamReaderProtocol(reader, client_connected_cb=client_connected_cb, loop=loop)
            return protocol

        self.listeners[local_socket] = factory

        # Make sure our plugin forwards this socket's traffic to our handle_incoming
        async def incoming_handler(payload: bytes, src_node: str, src_sock: int):
            await self.handle_incoming(payload, src_node, src_sock, local_socket)
        self.plugin.register_upper_layer(local_socket, incoming_handler)

        return ADSPServer(self, local_socket)


class ADSPServer:
    """
    Handle for a running ADSP server.
    """
    def __init__(self, manager: ADSPManager, local_socket: int):
        self.manager = manager
        self.local_socket = local_socket

    def close(self) -> None:
        if self.local_socket in self.manager.listeners:
            del self.manager.listeners[self.local_socket]


class ADSPTransport(asyncio.Transport):
    """
    asyncio.Transport implementation for ADSP connections.
    """
    def __init__(self, conn: 'ADSPConnection', protocol: asyncio.Protocol):
        super().__init__()
        self._conn = conn
        self._protocol = protocol
        self._closing = False

    def write(self, data: bytes) -> None:
        if not self._closing:
            # We defer actual network sending to the ADSP connection
            asyncio.create_task(self._conn.send_data(data))

    def write_eof(self) -> None:
        self.close()

    def can_write_eof(self) -> bool:
        return True

    def abort(self) -> None:
        self.close()

    def close(self) -> None:
        if not self._closing:
            self._closing = True
            asyncio.create_task(self._conn.close_connection())
            self._protocol.connection_lost(None)

    def is_closing(self) -> bool:
        return self._closing

class ADSPConnection:
    """
    State variables needed for an ADSP connection.
    """
    def __init__(self, local_conn_id: int, manager: 'ADSPManager', dest_node: str, dest_socket: int, local_socket: int):
        self.state = ADSPState.CLOSED

        self.manager = manager
        self.dest_node = dest_node
        self.dest_socket = dest_socket
        self.local_socket = local_socket

        # Connection IDs
        self.local_conn_id = local_conn_id
        self.remote_conn_id = 0

        # Sequence numbers and windows
        self.send_seq = 0
        self.recv_seq = 0
        self.send_window = 0
        self.recv_window = 4096  # Example default receive window size

        self.protocol: Optional[asyncio.Protocol] = None
        self.transport: Optional[ADSPTransport] = None

        self._open_future: Optional[asyncio.Future[None]] = None

    def set_protocol(self, protocol: asyncio.Protocol) -> None:
        self.protocol = protocol
        self.transport = ADSPTransport(self, protocol)

    async def connect(self) -> None:
        """Initiate the 3-way handshake."""
        self.state = ADSPState.OPENING
        self._open_future = asyncio.get_running_loop().create_future()
        await self._send_control(ADSPControlCode.OPEN_CONN_REQ)
        await self._open_future

    async def close_connection(self) -> None:
        """Close the connection."""
        if self.state != ADSPState.CLOSED:
            self.state = ADSPState.CLOSING
            await self._send_control(ADSPControlCode.CLOSE_CONN)
            self.state = ADSPState.CLOSED
            self.manager.remove_connection(self)

    async def _send_control(self, control_code: int) -> None:
        header = {
            "src_conn_id": self.local_conn_id,
            "dest_conn_id": self.remote_conn_id,
            "seq_num": self.send_seq,
            "ack_num": self.recv_seq,
            "window_size": self.recv_window,
            "descriptor": {
                "control": True,
                "ack_req": False,
                "eom": False,
                "attention": False,
                "control_code": control_code
            }
        }
        encoded = ADSPHeader.build(header)
        await self.manager.send_packet(self.dest_node, self.dest_socket, self.local_socket, encoded)

    async def send_data(self, data: bytes) -> None:
        """Send data over the open connection."""
        if self.state != ADSPState.OPEN:
            return

        # In a real implementation we would chunk data to fit within window/packet sizes
        header = {
            "src_conn_id": self.local_conn_id,
            "dest_conn_id": self.remote_conn_id,
            "seq_num": self.send_seq,
            "ack_num": self.recv_seq,
            "window_size": self.recv_window,
            "descriptor": {
                "control": False,
                "ack_req": True,
                "eom": True,
                "attention": False,
                "control_code": 0
            }
        }
        encoded = ADSPHeader.build(header) + data
        self.send_seq += len(data)
        await self.manager.send_packet(self.dest_node, self.dest_socket, self.local_socket, encoded)

    async def process_packet(self, header: Any, data: bytes) -> None:
        """Process incoming packets for this connection."""
        if header.descriptor.control:
            await self._process_control(header)
        else:
            await self._process_data(header, data)

    async def _process_control(self, header: Any) -> None:
        code = header.descriptor.control_code

        if self.state == ADSPState.LISTENING and code == ADSPControlCode.OPEN_CONN_REQ:
            self.remote_conn_id = header.src_conn_id
            self.recv_seq = header.seq_num
            self.send_window = header.window_size
            self.state = ADSPState.OPENING
            await self._send_control(ADSPControlCode.OPEN_CONN_REQ_ACK)

        elif self.state == ADSPState.OPENING and code == ADSPControlCode.OPEN_CONN_REQ_ACK:
            self.remote_conn_id = header.src_conn_id
            self.recv_seq = header.seq_num
            self.send_window = header.window_size
            await self._send_control(ADSPControlCode.OPEN_CONN_ACK)
            self.state = ADSPState.OPEN
            if self.protocol and self.transport:
                self.protocol.connection_made(self.transport)
            if self._open_future and not self._open_future.done():
                self._open_future.set_result(None)

        elif self.state == ADSPState.OPENING and code == ADSPControlCode.OPEN_CONN_ACK:
            self.state = ADSPState.OPEN
            if self.protocol and self.transport:
                self.protocol.connection_made(self.transport)

        elif code == ADSPControlCode.CLOSE_CONN:
            self.state = ADSPState.CLOSED
            if self.protocol:
                self.protocol.connection_lost(None)
            self.manager.remove_connection(self)

    async def _process_data(self, header: Any, data: bytes) -> None:
        if self.state == ADSPState.OPEN:
            # Check seq_num
            if header.seq_num == self.recv_seq:
                self.recv_seq += len(data)
                if self.protocol:
                    self.protocol.data_received(data)

                # If ack_req is true, we should send an ACK.
                # Since we don't implement the full flow control in this example,
                # we just send a PROBE_OR_ACK back
                if header.descriptor.ack_req:
                    await self._send_control(ADSPControlCode.PROBE_OR_ACK)
