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
