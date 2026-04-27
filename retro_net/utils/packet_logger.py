import json
import base64
from typing import Dict, Any

class PacketLogger:
    """Helper to dump JSON/Hex for debugging."""

    @staticmethod
    def log_json(message: Dict[str, Any], prefix: str = "") -> None:
        """Logs a message as formatted JSON."""
        formatted_json = json.dumps(message, indent=2)
        print(f"{prefix}JSON Dump:\n{formatted_json}")

    @staticmethod
    def log_datagram_hex(payload: bytes, prefix: str = "") -> None:
        """Logs a binary payload as a hex dump."""
        hex_dump = ' '.join(f'{b:02x}' for b in payload)
        print(f"{prefix}Hex Dump:\n{hex_dump}")

    @staticmethod
    def log_base64_encoded_hex(encoded_payload: str, prefix: str = "") -> None:
        """Decodes a base64 payload and logs it as a hex dump."""
        try:
            payload = base64.b64decode(encoded_payload)
            PacketLogger.log_datagram_hex(payload, prefix)
        except Exception as e:
            print(f"{prefix}Failed to decode base64 payload: {e}")
