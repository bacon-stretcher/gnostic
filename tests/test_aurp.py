import pytest
import asyncio
from retro_net.services.aurp import AURPBridgeService

class MockNode:
    def __init__(self):
        self.sent_datagrams = []

    async def send_datagram(self, dest_node: str, protocol: str, payload: bytes) -> None:
        self.sent_datagrams.append((dest_node, protocol, payload))

def test_aurp_domain_identifier_unknown_authority():
    from retro_net.services.aurp import DomainIdentifier
    # Test length 6, authority 2 (unknown), id = 4 bytes
    data = b'\x06\x02\x01\x02\x03\x04'
    parsed = DomainIdentifier.parse(data)
    assert parsed.length == 6
    assert parsed.authority == 2
    assert parsed.identifier == b'\x01\x02\x03\x04'

    # Test unknown authority with 0 payload
    data_empty = b'\x02\x05'
    parsed_empty = DomainIdentifier.parse(data_empty)
    assert parsed_empty.length == 2
    assert parsed_empty.authority == 5
    assert parsed_empty.identifier == b''


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

class UDPReceiverProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.received = asyncio.Queue()

    def datagram_received(self, data, addr):
        self.received.put_nowait((data, addr))

@pytest.mark.asyncio
async def test_aurp_outbound_hook():
    node = MockNode()

    # Start a dummy UDP receiver to capture the sent packet
    loop = asyncio.get_running_loop()
    recv_transport, recv_protocol = await loop.create_datagram_endpoint(
        UDPReceiverProtocol,
        local_addr=('127.0.0.1', 0)
    )
    dest_ip, dest_port = recv_transport.get_extra_info('sockname')

    service = AURPBridgeService(node, port=0)

    # Add the receiver as a peer
    service.add_peer(dest_ip, dest_port)

    await service.start()

    payload = b'test_outbound_hook_payload'

    # Trigger the hook by sending a datagram through the node
    await node.send_datagram('*', 'appletalk', payload)

    # Wait for the packet to be received over UDP
    received_data, addr = await asyncio.wait_for(recv_protocol.received.get(), timeout=1.0)

    header_length = 22
    assert len(received_data) == header_length + len(payload)

    received_payload = received_data[header_length:]
    assert received_payload == payload

    # Check that original send_datagram was also called
    assert len(node.sent_datagrams) == 1
    dest_node, protocol, sent_payload = node.sent_datagrams[0]
    assert dest_node == '*'
    assert protocol == 'appletalk'
    assert sent_payload == payload

    await service.stop()
    recv_transport.close()

    # Verify monkey-patch is restored
    assert node.send_datagram.__name__ == 'send_datagram'


@pytest.mark.asyncio
async def test_aurp_send_packet():
    node = MockNode()

    # Start a dummy UDP receiver to capture the sent packet
    loop = asyncio.get_running_loop()
    recv_transport, recv_protocol = await loop.create_datagram_endpoint(
        UDPReceiverProtocol,
        local_addr=('127.0.0.1', 0)
    )
    dest_ip, dest_port = recv_transport.get_extra_info('sockname')

    service = AURPBridgeService(node, port=0)
    await service.start()

    payload = b'test_outbound_payload'
    service.send_aurp_packet(dest_ip, dest_port, payload)

    # Wait for the packet to be received
    received_data, addr = await asyncio.wait_for(recv_protocol.received.get(), timeout=1.0)

    # DomainIdentifier structure (when authority=1):
    # length (1 byte) + authority (1 byte) + distinguisher (2 bytes) + ip (4 bytes) = 8 bytes total per DI
    # dest_di (8 bytes) + source_di (8 bytes) + version (2 bytes) + reserved (2 bytes) + packet_type (2 bytes) = 22 bytes
    header_length = 22
    assert len(received_data) == header_length + len(payload)

    received_payload = received_data[header_length:]
    assert received_payload == payload

    # check if dest_di ip matches what we sent (offset 4)
    import socket
    expected_dest_ip_bytes = socket.inet_aton(dest_ip)
    assert received_data[4:8] == expected_dest_ip_bytes

    await service.stop()
    recv_transport.close()

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
