import pytest
import asyncio
from typing import List, Tuple
from retro_net.protocols.osi import OSIPlugin, CLNPHeader, NLPID_CLNP, NLPID_ESIS, NLPID_ISIS, ESISHeader, ISISHeader, TP4Header

class MockNode:
    def __init__(self):
        self.sent_datagrams = []

    async def send_datagram(self, dest_node: str, protocol: str, payload: bytes) -> None:
        self.sent_datagrams.append((dest_node, protocol, payload))

@pytest.fixture
def osi_plugin():
    node = MockNode()
    return OSIPlugin(node)

@pytest.mark.asyncio
async def test_clnp_tp4_routing(osi_plugin):
    received_data = []

    async def mock_tp4_handler(data: bytes, src_node: str, port: int):
        received_data.append((data, src_node, port))

    # Register TP4 handler (using 0x84)
    osi_plugin.register_upper_layer(0x84, mock_tp4_handler)

    # Build a fake TP4 payload
    tp4_data = b"tp4_test_data"

    # Build CLNP Header manually or using construct
    # Let's use build
    clnp_header_bytes = CLNPHeader.build({
        "nlpid": NLPID_CLNP,
        "length_indicator": 13, # 13 bytes header for this specific address length setup
        "version": 1,
        "ttl": 64,
        "type_flags": 0,
        "segment_length": 13 + len(tp4_data),
        "checksum": 0,
        "dest_address_length": 1,
        "dest_address": b"\x01",
        "src_address_length": 1,
        "src_address": b"\x02"
    })

    # CLNP total payload
    payload = clnp_header_bytes + tp4_data

    await osi_plugin.process_datagram(payload, "node_a")

    assert len(received_data) == 1
    data, src_node, port = received_data[0]
    assert data == tp4_data
    assert src_node == "node_a"
    assert port == 0x84

@pytest.mark.asyncio
async def test_esis_routing(osi_plugin):
    received_data = []

    async def mock_esis_handler(data: bytes, src_node: str, port: int):
        received_data.append((data, src_node, port))

    # Register ES-IS handler
    osi_plugin.register_upper_layer(NLPID_ESIS, mock_esis_handler)

    esis_header_bytes = ESISHeader.build({
        "nlpid": NLPID_ESIS,
        "length_indicator": 10,
        "version": 1,
        "id_length": 0,
        "type": 2,
        "holding_time": 100,
        "checksum": 0,
        "source_address_length": 1,
        "source_address": b"\x01",
        "options": b""
    })

    await osi_plugin.process_datagram(esis_header_bytes, "node_b")

    assert len(received_data) == 1
    data, src_node, port = received_data[0]
    assert data == esis_header_bytes
    assert src_node == "node_b"
    assert port == NLPID_ESIS

@pytest.mark.asyncio
async def test_isis_routing(osi_plugin):
    received_data = []

    async def mock_isis_handler(data: bytes, src_node: str, port: int):
        received_data.append((data, src_node, port))

    # Register IS-IS handler
    osi_plugin.register_upper_layer(NLPID_ISIS, mock_isis_handler)

    isis_header_bytes = ISISHeader.build({
        "nlpid": NLPID_ISIS,
        "length_indicator": 8,
        "version": 1,
        "id_length": 0,
        "pdu_type": 1,
        "version2": 1,
        "reserved": 0,
        "max_area_addresses": 3,
        "variable_part": b""
    })

    await osi_plugin.process_datagram(isis_header_bytes, "node_c")

    assert len(received_data) == 1
    data, src_node, port = received_data[0]
    assert data == isis_header_bytes
    assert src_node == "node_c"
    assert port == NLPID_ISIS
