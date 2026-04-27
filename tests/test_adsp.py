import pytest
import asyncio
from typing import Any
from retro_net.protocols.appletalk.adsp import ADSPManager, ADSPControlCode
from retro_net.protocols.appletalk.plugin import AppleTalkPlugin

class MockNode:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.peer = None # Link to another node

    async def send_datagram(self, dest_node: str, protocol: str, payload: bytes) -> None:
        if self.peer and self.peer.node_id == dest_node:
            asyncio.create_task(self.peer.plugin.process_datagram(payload, self.node_id))


@pytest.mark.asyncio
async def test_adsp_handshake_and_stream():
    # Setup network of 2 nodes
    node_A = MockNode("node_A")
    node_B = MockNode("node_B")

    node_A.peer = node_B
    node_B.peer = node_A

    plugin_A = AppleTalkPlugin(node_A)
    plugin_B = AppleTalkPlugin(node_B)

    node_A.plugin = plugin_A
    node_B.plugin = plugin_B

    manager_A = ADSPManager(node_A, plugin_A)
    manager_B = ADSPManager(node_B, plugin_B)

    # State
    received_data = []

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        data = await reader.read(100)
        received_data.append(data)

        # Echo back
        writer.write(b"ECHO: " + data)
        await writer.drain()

        writer.close()

    # B starts server on socket 50
    server_B = await manager_B.start_server(handle_client, 50)

    # A connects to B on socket 50, from its local socket 60
    reader_A, writer_A = await manager_A.open_connection("node_B", 50, 60)

    # Connection should be established. Send data.
    test_msg = b"Hello from A"
    writer_A.write(test_msg)
    await writer_A.drain()

    # Read response
    response = await reader_A.read(100)

    # Asserts
    assert len(received_data) == 1
    assert received_data[0] == test_msg
    assert response == b"ECHO: " + test_msg

    writer_A.close()
    server_B.close()
