import pytest
from retro_net.protocols.appletalk import DDPHeader, NBPHeader, AppleTalkPlugin, NBP_SOCKET

class MockNode:
    def __init__(self):
        self.sent_datagrams = []

    async def send_datagram(self, dest_node: str, protocol: str, payload: bytes) -> None:
        self.sent_datagrams.append((dest_node, protocol, payload))

def test_ddp_parsing():
    # Build a DDP packet
    ddp_data = {
        "flags_hop_length": {
            "reserved": 0,
            "hop_count": 0,
            "length": 13
        },
        "checksum": 0,
        "dest_network": 1,
        "src_network": 2,
        "dest_node": 3,
        "src_node": 4,
        "dest_socket": 5,
        "src_socket": 6,
        "type": 7
    }
    encoded = DDPHeader.build(ddp_data)
    assert len(encoded) == 13

    # Parse
    parsed = DDPHeader.parse(encoded)
    assert parsed.flags_hop_length.length == 13
    assert parsed.dest_socket == 5
    assert parsed.type == 7

def test_nbp_parsing():
    # Build an NBP BrRq packet
    nbp_data = {
        "flags": {
            "function": "BrRq",
            "tuple_count": 1
        },
        "nbp_id": 42,
        "tuples": [{
            "network": 100,
            "node": 10,
            "socket": NBP_SOCKET,
            "enumerator": 1,
            "object_name": "My Service",
            "type_name": "AFPServer",
            "zone_name": "*"
        }]
    }
    encoded = NBPHeader.build(nbp_data)

    parsed = NBPHeader.parse(encoded)
    assert parsed.flags.function == "BrRq"
    assert parsed.flags.tuple_count == 1
    assert parsed.nbp_id == 42
    assert len(parsed.tuples) == 1
    assert parsed.tuples[0].object_name == "My Service"
    assert parsed.tuples[0].type_name == "AFPServer"

@pytest.mark.asyncio
async def test_appletalk_plugin_routing():
    node = MockNode()
    plugin = AppleTalkPlugin(node)

    # Register an upper layer service on socket 10
    received_data = []
    received_src = []
    received_src_socket = []

    async def mock_handler(data: bytes, src: str, src_sock: int):
        received_data.append(data)
        received_src.append(src)
        received_src_socket.append(src_sock)

    plugin.register_upper_layer(10, mock_handler)

    # Create DDP packet sent to socket 10
    ddp_data = {
        "flags_hop_length": {"reserved": 0, "hop_count": 0, "length": 13 + 4},
        "checksum": 0, "dest_network": 0, "src_network": 0,
        "dest_node": 0, "src_node": 0,
        "dest_socket": 10, "src_socket": 11, "type": 1
    }
    payload = b"TEST"
    packet = DDPHeader.build(ddp_data) + payload

    await plugin.process_datagram(packet, "node_B")

    assert len(received_data) == 1
    assert received_data[0] == b"TEST"
    assert received_src[0] == "node_B"
    assert received_src_socket[0] == 11

@pytest.mark.asyncio
async def test_appletalk_nbp_lookup():
    node = MockNode()
    plugin = AppleTalkPlugin(node)

    # Register a local service
    plugin.register_service("MyTestService", "TestType", 20)

    # Create NBP Lookup request matching this service
    nbp_data = {
        "flags": {"function": "LkUp", "tuple_count": 1},
        "nbp_id": 99,
        "tuples": [{
            "network": 0, "node": 0, "socket": 0, "enumerator": 1,
            "object_name": "MyTestService",
            "type_name": "TestType",
            "zone_name": "*"
        }]
    }
    nbp_bytes = NBPHeader.build(nbp_data)

    ddp_data = {
        "flags_hop_length": {"reserved": 0, "hop_count": 0, "length": 13 + len(nbp_bytes)},
        "checksum": 0, "dest_network": 0, "src_network": 0,
        "dest_node": 0, "src_node": 0,
        "dest_socket": NBP_SOCKET, "src_socket": NBP_SOCKET, "type": 2
    }
    packet = DDPHeader.build(ddp_data) + nbp_bytes

    await plugin.process_datagram(packet, "node_C")

    # Plugin should have sent a LkUpReply
    assert len(node.sent_datagrams) == 1
    dest, proto, payload = node.sent_datagrams[0]

    assert dest == "node_C"
    assert proto == "appletalk"

    # Parse reply
    reply_ddp = DDPHeader.parse(payload[:13])
    reply_nbp = NBPHeader.parse(payload[13:])

    assert reply_nbp.flags.function == "LkUpReply"
    assert reply_nbp.nbp_id == 99
    assert reply_nbp.flags.tuple_count == 1
    assert reply_nbp.tuples[0].socket == 20
    assert reply_nbp.tuples[0].object_name == "MyTestService"
