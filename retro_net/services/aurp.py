import io
import socket
import asyncio
from typing import Any, Tuple
from construct import Struct, Int8ub, Int16ub, Bytes, Switch, this
from retro_net.services.base import ServicePlugin

DomainIdentifier = Struct(
    "length" / Int8ub,
    "authority" / Int8ub,
    "identifier" / Switch(this.authority, {
        1: Struct("distinguisher" / Int16ub, "ip" / Bytes(4)),
        0: Bytes(0)
    }, default=Bytes(lambda ctx: max(0, ctx.length - 2)))
)

DomainHeader = Struct(
    "dest_di" / DomainIdentifier,
    "source_di" / DomainIdentifier,
    "version" / Int16ub,
    "reserved" / Int16ub,
    "packet_type" / Int16ub,
)

class AURPProtocol(asyncio.DatagramProtocol):
    def __init__(self, node: Any):
        self.node = node
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport # type: ignore

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        try:
            stream = io.BytesIO(data)
            parsed = DomainHeader.parse_stream(stream)

            # Check if it's an AppleTalk data packet (packet_type == 2)
            if parsed.packet_type == 2:
                payload_offset = stream.tell()
                payload = data[payload_offset:]

                # Inject the encapsulated DDP datagram into the RetroNet Node
                asyncio.create_task(self.node.send_datagram('*', 'appletalk', payload))
        except Exception as e:
            print(f"AURP parse error: {e}")

class AURPBridgeService(ServicePlugin):
    """
    AURP Bridge Service.
    Handles tunneling AppleTalk DDP packets over UDP (AURP - AppleTalk Update-Based Routing Protocol).
    """

    def __init__(self, node: Any, port: int = 387, host: str = '0.0.0.0') -> None:
        self.node = node
        self.port = port
        self.host = host
        self._source_ip_bytes = socket.inet_aton(self.host if self.host != '0.0.0.0' else '127.0.0.1')
        self.transport: asyncio.DatagramTransport | None = None
        self.protocol: AURPProtocol | None = None
        self.peers: list[Tuple[str, int]] = []
        self._original_send_datagram = None

    def add_peer(self, ip: str, port: int) -> None:
        """Add a remote AURP tunnel peer."""
        self.peers.append((ip, port))

    async def _outbound_hook(self, dest_node: str, protocol: str, payload: bytes) -> None:
        """Intercept outbound datagrams and forward AppleTalk packets to peers."""
        if protocol == 'appletalk':
            for peer_ip, peer_port in self.peers:
                self.send_aurp_packet(peer_ip, peer_port, payload)

        # Call the original send_datagram
        if self._original_send_datagram:
            await self._original_send_datagram(dest_node, protocol, payload)

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: AURPProtocol(self.node),
            local_addr=(self.host, self.port)
        )

        # Monkey-patch node to intercept outbound datagrams
        if hasattr(self.node, 'send_datagram'):
            self._original_send_datagram = self.node.send_datagram
            self.node.send_datagram = self._outbound_hook

        print(f"AURPBridgeService started on udp://{self.host}:{self.port}")

    async def stop(self) -> None:
        if self.transport:
            self.transport.close()
            self.transport = None

        # Restore original send_datagram
        if self._original_send_datagram:
            self.node.send_datagram = self._original_send_datagram
            self._original_send_datagram = None

        print("AURPBridgeService stopped.")

    def send_aurp_packet(self, dest_ip: str, dest_port: int, ddp_payload: bytes) -> None:
        """
        Encapsulate a DDP payload in an AURP DomainHeader and send it via UDP.
        """
        if not self.transport:
            print("AURPBridgeService: Cannot send packet, transport is not open.")
            return

        try:
            dest_ip_bytes = socket.inet_aton(dest_ip)

            dest_di = {
                "length": 7,
                "authority": 1,
                "identifier": {"distinguisher": 0, "ip": dest_ip_bytes}
            }
            source_di = {
                "length": 7,
                "authority": 1,
                "identifier": {"distinguisher": 0, "ip": self._source_ip_bytes}
            }

            header = DomainHeader.build({
                "dest_di": dest_di,
                "source_di": source_di,
                "version": 1,
                "reserved": 0,
                "packet_type": 2
            })

            packet = header + ddp_payload
            self.transport.sendto(packet, (dest_ip, dest_port))
        except Exception as e:
            print(f"AURPBridgeService: Error sending packet: {e}")
