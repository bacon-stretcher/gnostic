import io
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
    })
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
        self.transport: asyncio.DatagramTransport | None = None
        self.protocol: AURPProtocol | None = None

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: AURPProtocol(self.node),
            local_addr=(self.host, self.port)
        )
        print(f"AURPBridgeService started on udp://{self.host}:{self.port}")

    async def stop(self) -> None:
        if self.transport:
            self.transport.close()
            self.transport = None
        print("AURPBridgeService stopped.")
