import json
import base64
import pytest
from retro_net.utils.packet_logger import PacketLogger

@pytest.mark.parametrize("data, prefix", [
    ({"key": "value", "nested": {"a": 1}}, "[TEST] "),
    ({"hello": "world"}, ""),
    ({}, "EMPTY "),
    ({}, ""),
])
def test_log_json(capsys, data, prefix):
    PacketLogger.log_json(data, prefix)
    captured = capsys.readouterr()
    expected_json = json.dumps(data, indent=2)
    assert f"{prefix}JSON Dump:\n{expected_json}\n" == captured.out

def test_log_json_error(capsys):
    """Test log_json with non-serializable object."""
    # set is not JSON serializable
    data = {"key": {1, 2, 3}}
    with pytest.raises(TypeError):
        PacketLogger.log_json(data)

@pytest.mark.parametrize("payload, prefix, expected_hex", [
    (b"\x01\x02\x03\xff\x00", "[HEX] ", "01 02 03 ff 00"),
    (b"\xde\xad\xbe\xef", "", "de ad be ef"),
    (b"", "EMPTY ", ""),
    (b"", "", ""),
])
def test_log_datagram_hex(capsys, payload, prefix, expected_hex):
    PacketLogger.log_datagram_hex(payload, prefix)
    captured = capsys.readouterr()
    assert f"{prefix}Hex Dump:\n{expected_hex}\n" == captured.out

@pytest.mark.parametrize("payload, prefix", [
    (b"hello world", "[B64] "),
    (b"test", ""),
    (b"", "EMPTY "),
])
def test_log_base64_encoded_hex_success(capsys, payload, prefix):
    encoded = base64.b64encode(payload).decode('utf-8')
    PacketLogger.log_base64_encoded_hex(encoded, prefix)

    captured = capsys.readouterr()
    expected_hex = ' '.join(f'{b:02x}' for b in payload)
    assert f"{prefix}Hex Dump:\n{expected_hex}\n" == captured.out

@pytest.mark.parametrize("invalid_b64, prefix", [
    ("A", "[FAIL] "),
    ("A" * 5, "LONG_FAIL "),
])
def test_log_base64_encoded_hex_failure(capsys, invalid_b64, prefix):
    PacketLogger.log_base64_encoded_hex(invalid_b64, prefix)
    captured = capsys.readouterr()
    assert f"{prefix}Failed to decode base64 payload:" in captured.out
