import asyncio
from enum import Enum
from typing import Dict, Optional, Tuple, Any

from .tp4 import TP4Header, TP4_CLASS

class TP4PDUType(Enum):
    CR = 0xE0  # Connection Request
    CC = 0xD0  # Connection Confirm
    DR = 0x80  # Disconnect Request
    DC = 0xC0  # Disconnect Confirm
    DT = 0xF0  # Data
    # Other PDUs like ED, AK, EA, RJ, ER exist but omitted for minimal implementation

class TP4State(Enum):
    LISTEN = 1
    SYN_SENT = 2
    SYN_RCVD = 3
    ESTABLISHED = 4
    FIN_WAIT = 5
    CLOSED = 6

class TP4Connection:
    """Represents a single TP4 connection stream."""

    def __init__(self, manager: 'TP4Manager', local_ref: int, remote_ref: int, remote_node: str):
        self.manager = manager
        self.local_ref = local_ref
        self.remote_ref = remote_ref
        self.remote_node = remote_node
        self.state = TP4State.LISTEN

        self.reader = asyncio.StreamReader()
        self.writer = asyncio.StreamWriter(
            transport=self,
            protocol=asyncio.StreamReaderProtocol(self.reader),
            reader=self.reader,
            loop=asyncio.get_event_loop()
        )

    # Required methods for StreamWriter's Transport mock
    def write(self, data: bytes) -> None:
        asyncio.create_task(self.manager.send_data(self, data))

    def writelines(self, list_of_data: list[bytes]) -> None:
        for data in list_of_data:
            self.write(data)

    def write_eof(self) -> None:
        pass # Not implemented

    def can_write_eof(self) -> bool:
        return False

    def abort(self) -> None:
        self.close()

    def close(self) -> None:
        asyncio.create_task(self.manager.close_connection(self))

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        if name == 'peername':
            return self.remote_node
        return default

    def is_closing(self) -> bool:
        return self.state in (TP4State.FIN_WAIT, TP4State.CLOSED)

class TP4Manager:
    """Manages TP4 connections and state transitions."""

    def __init__(self, node: Any):
        self.node = node
        self.connections: Dict[int, TP4Connection] = {} # Keyed by local_ref
        self.listen_handlers: Dict[int, Any] = {} # For passive opens (not fully used in this minimal version, we accept all)
        self._next_ref = 1000

    def get_next_ref(self) -> int:
        ref = self._next_ref
        self._next_ref += 1
        return ref

    async def handle_pdu(self, payload: bytes, src_node: str) -> None:
        if len(payload) < 6:
            return # Too short

        try:
            parsed = TP4Header.parse(payload)
            pdu_type = parsed.pdu_type
            dst_ref = parsed.dst_ref
            src_ref = parsed.src_ref
            variable_part = parsed.variable_part
            data_offset = parsed.length_indicator + 1
            data = payload[data_offset:]
        except Exception as e:
            print(f"TP4 Parse error: {e}")
            return

        if pdu_type == TP4PDUType.CR.value:
            await self._handle_cr(src_ref, variable_part, src_node, data)
        elif pdu_type == TP4PDUType.CC.value:
            await self._handle_cc(dst_ref, src_ref, src_node)
        elif pdu_type == TP4PDUType.DR.value:
            await self._handle_dr(dst_ref, src_ref, src_node)
        elif pdu_type == TP4PDUType.DC.value:
            await self._handle_dc(dst_ref, src_node)
        elif pdu_type == TP4PDUType.DT.value:
            await self._handle_dt(dst_ref, data, src_node)
        else:
            print(f"TP4 Manager: Unknown PDU type 0x{pdu_type:02x}")

    async def _handle_cr(self, src_ref: int, variable_part: bytes, src_node: str, data: bytes) -> None:
        """Handle incoming Connection Request."""
        local_ref = self.get_next_ref()
        conn = TP4Connection(self, local_ref, src_ref, src_node)
        conn.state = TP4State.ESTABLISHED
        self.connections[local_ref] = conn

        # Send CC (Connection Confirm)
        await self._send_cc(conn)

        # Notify upper layer (simplified: just put any data if present)
        if data:
            conn.reader.feed_data(data)

    async def _handle_cc(self, dst_ref: int, src_ref: int, src_node: str) -> None:
        """Handle incoming Connection Confirm."""
        conn = self.connections.get(dst_ref)
        if conn and conn.state == TP4State.SYN_SENT:
            conn.remote_ref = src_ref
            conn.state = TP4State.ESTABLISHED

    async def _handle_dr(self, dst_ref: int, src_ref: int, src_node: str) -> None:
        """Handle incoming Disconnect Request."""
        conn = self.connections.get(dst_ref)
        if conn:
            conn.state = TP4State.CLOSED
            conn.reader.feed_eof()
            await self._send_dc(conn)
            del self.connections[dst_ref]

    async def _handle_dc(self, dst_ref: int, src_node: str) -> None:
        """Handle incoming Disconnect Confirm."""
        conn = self.connections.get(dst_ref)
        if conn and conn.state == TP4State.FIN_WAIT:
            conn.state = TP4State.CLOSED
            conn.reader.feed_eof()
            del self.connections[dst_ref]

    async def _handle_dt(self, dst_ref: int, data: bytes, src_node: str) -> None:
        """Handle incoming Data."""
        conn = self.connections.get(dst_ref)
        if conn and conn.state == TP4State.ESTABLISHED:
            if data:
                conn.reader.feed_data(data)

    async def _send_cc(self, conn: TP4Connection) -> None:
        """Send Connection Confirm."""
        header = TP4Header.build({
            "length_indicator": 6,
            "pdu_type": TP4PDUType.CC.value,
            "dst_ref": conn.remote_ref,
            "src_ref": conn.local_ref,
            "class_option": TP4_CLASS,
            "variable_part": b""
        })
        await self._send_to_clnp(conn.remote_node, header)

    async def _send_dc(self, conn: TP4Connection) -> None:
        """Send Disconnect Confirm."""
        header = TP4Header.build({
            "length_indicator": 6,
            "pdu_type": TP4PDUType.DC.value,
            "dst_ref": conn.remote_ref,
            "src_ref": conn.local_ref,
            "class_option": TP4_CLASS,
            "variable_part": b""
        })
        await self._send_to_clnp(conn.remote_node, header)

    async def send_data(self, conn: TP4Connection, data: bytes) -> None:
        """Send Data PDU."""
        if conn.state != TP4State.ESTABLISHED:
            return

        header = TP4Header.build({
            "length_indicator": 6,
            "pdu_type": TP4PDUType.DT.value,
            "dst_ref": conn.remote_ref,
            "src_ref": conn.local_ref, # Not strictly required for DT, but adding for completeness
            "class_option": TP4_CLASS,
            "variable_part": b""
        })
        await self._send_to_clnp(conn.remote_node, header + data)

    async def connect(self, remote_node: str) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Initiate a TP4 connection (Active Open)."""
        local_ref = self.get_next_ref()
        conn = TP4Connection(self, local_ref, 0, remote_node)
        conn.state = TP4State.SYN_SENT
        self.connections[local_ref] = conn

        # Send CR (Connection Request)
        header = TP4Header.build({
            "length_indicator": 6,
            "pdu_type": TP4PDUType.CR.value,
            "dst_ref": 0, # Don't know it yet
            "src_ref": local_ref,
            "class_option": TP4_CLASS,
            "variable_part": b""
        })
        await self._send_to_clnp(remote_node, header)

        # Wait for connection to be established (simplified wait)
        for _ in range(50): # 5 seconds max wait
            if conn.state == TP4State.ESTABLISHED:
                return conn.reader, conn.writer
            await asyncio.sleep(0.1)

        raise ConnectionError("TP4 Connection timed out")

    async def close_connection(self, conn: TP4Connection) -> None:
        """Initiate disconnect (Active Close)."""
        if conn.state == TP4State.CLOSED:
            return

        conn.state = TP4State.FIN_WAIT

        # Send DR (Disconnect Request)
        header = TP4Header.build({
            "length_indicator": 6,
            "pdu_type": TP4PDUType.DR.value,
            "dst_ref": conn.remote_ref,
            "src_ref": conn.local_ref,
            "class_option": TP4_CLASS,
            "variable_part": b""
        })
        await self._send_to_clnp(conn.remote_node, header)

    async def _send_to_clnp(self, dest_node: str, payload: bytes) -> None:
        # In a real OSI stack, this would build a CLNP header and send it via the node's CLNP plugin
        # For simplicity, we assume self.node has a way to route OSI packets.
        # However, to integrate with the existing OSIPlugin seamlessly, we need to
        # encode the payload such that CLNP can handle it.
        # But wait, TP4Manager needs to send *CLNP* datagrams!

        # Let's import NLPID_CLNP
        from .clnp import CLNPHeader, NLPID_CLNP

        # We need to build a CLNP header. We assume very simple addressing.
        clnp_header = CLNPHeader.build({
            "nlpid": NLPID_CLNP,
            "length_indicator": 13,
            "version": 1,
            "ttl": 64,
            "type_flags": 0,
            "segment_length": 13 + len(payload),
            "checksum": 0,
            "dest_address_length": 1,
            "dest_address": b"\x01", # Dummy address
            "src_address_length": 1,
            "src_address": b"\x02"   # Dummy address
        })

        full_payload = clnp_header + payload
        await self.node.send_datagram(dest_node, "osi", full_payload)
