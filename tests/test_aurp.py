import pytest
import asyncio
from retro_net.services.aurp import AURPBridgeService

class MockNode:
    def __init__(self):
        self.sent_datagrams = []

    async def send_datagram(self, dest_node: str, protocol: str, payload: bytes) -> None:
        self.sent_datagrams.append((dest_node, protocol, payload))

@pytest.mark.asyncio
async def test_aurp_bridge_service():
    node = MockNode()

    # We will use port 0 for the test to let the OS assign a random free port,
    # preventing "port already in use" errors during test runs.
    service = AURPBridgeService(node, port=0)

    # Start the service
    await service.start()

    assert service.transport is not None
    assert service.protocol is not None

    # Stop the service
    await service.stop()

    assert service.transport is None

@pytest.mark.asyncio
async def test_aurp_datagram_received():
    node = MockNode()

    # We will use port 0 for the test to let the OS assign a random free port,
    # preventing "port already in use" errors during test runs.
    service = AURPBridgeService(node, port=0)

    # Start the service
    await service.start()

    # Send a mock AURP packet
    dest_di = b'\x07\x01\x00\x00\x0a\x00\x00\x01' # 10.0.0.1
    src_di = b'\x07\x01\x00\x00\x0a\x00\x00\x02' # 10.0.0.2
    header_bytes = dest_di + src_di + b'\x00\x01' + b'\x00\x00' + b'\x00\x02'
    payload = b'mock_ddp_payload'

    data = header_bytes + payload

    service.protocol.datagram_received(data, ('127.0.0.1', 12345))

    # Allow async tasks to run
    await asyncio.sleep(0.01)

    assert len(node.sent_datagrams) == 1
    dest_node, protocol, sent_payload = node.sent_datagrams[0]

    assert dest_node == '*'
    assert protocol == 'appletalk'
    assert sent_payload == payload

    # Stop the service
    await service.stop()
