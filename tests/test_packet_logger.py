import json
import base64
import pytest
from retro_net.utils.packet_logger import PacketLogger

def test_log_json(capsys):
    data = {"key": "value", "nested": {"a": 1}}
    prefix = "[TEST] "
    PacketLogger.log_json(data, prefix)

    captured = capsys.readouterr()
    expected_json = json.dumps(data, indent=2)
    assert f"{prefix}JSON Dump:\n{expected_json}\n" == captured.out

def test_log_json_no_prefix(capsys):
    data = {"hello": "world"}
    PacketLogger.log_json(data)

    captured = capsys.readouterr()
    expected_json = json.dumps(data, indent=2)
    assert f"JSON Dump:\n{expected_json}\n" == captured.out

def test_log_datagram_hex(capsys):
    payload = b"\x01\x02\x03\xff\x00"
    prefix = "[HEX] "
    PacketLogger.log_datagram_hex(payload, prefix)

    captured = capsys.readouterr()
    assert f"{prefix}Hex Dump:\n01 02 03 ff 00\n" == captured.out

def test_log_datagram_hex_no_prefix(capsys):
    payload = b"\xde\xad\xbe\xef"
    PacketLogger.log_datagram_hex(payload)

    captured = capsys.readouterr()
    assert f"Hex Dump:\nde ad be ef\n" == captured.out

def test_log_base64_encoded_hex_success(capsys):
    payload = b"hello world"
    encoded = base64.b64encode(payload).decode('utf-8')
    prefix = "[B64] "
    PacketLogger.log_base64_encoded_hex(encoded, prefix)

    captured = capsys.readouterr()
    # "hello world" in hex is 68 65 6c 6c 6f 20 77 6f 72 6c 64
    assert f"{prefix}Hex Dump:\n68 65 6c 6c 6f 20 77 6f 72 6c 64\n" == captured.out

def test_log_base64_encoded_hex_failure(capsys):
    # Base64 strings must have length that is a multiple of 4,
    # and a single character (not multiple of 4) often fails.
    invalid_b64 = "A"
    prefix = "[FAIL] "
    PacketLogger.log_base64_encoded_hex(invalid_b64, prefix)

    captured = capsys.readouterr()
    assert f"{prefix}Failed to decode base64 payload:" in captured.out
