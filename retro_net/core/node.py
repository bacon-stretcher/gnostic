import asyncio
import json
import base64
from typing import Optional, Dict, Any
import websockets
from websockets.client import WebSocketClientProtocol

from .exceptions import ConnectionError

class Node:
    """Node representing a participant in the retro network."""

    def __init__(self, switch_uri: str, node_id: str) -> None:
        self.switch_uri: str = switch_uri
        self.node_id: str = node_id
        self.websocket: Optional[WebSocketClientProtocol] = None
        self._running: bool = False

    async def connect(self) -> None:
        """Connects to the central switch."""
        try:
            self.websocket = await websockets.connect(self.switch_uri)
            # Register node on connect
            await self._send_message({"type": "register", "node_id": self.node_id})
        except Exception as e:
            raise ConnectionError(f"Failed to connect to switch at {self.switch_uri}: {e}")

    async def disconnect(self) -> None:
        """Disconnects from the central switch."""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

    async def _send_message(self, message: Dict[str, Any]) -> None:
        """Sends a JSON message to the switch."""
        if not self.websocket:
            raise ConnectionError("Cannot send message: not connected to switch.")
        await self.websocket.send(json.dumps(message))

    async def send_datagram(self, dest_node: str, payload: bytes) -> None:
        """
        Sends a datagram to another node.

        Args:
            dest_node: The destination node ID.
            payload: The binary payload to send.
        """
        encoded_payload = base64.b64encode(payload).decode('utf-8')
        message = {
            "type": "datagram",
            "src": self.node_id,
            "dest": dest_node,
            "payload": encoded_payload
        }
        await self._send_message(message)

    async def _handle_message(self, message_str: str) -> None:
        """Handles an incoming message from the switch."""
        try:
            message = json.loads(message_str)
            msg_type = message.get("type")

            if msg_type == "datagram":
                src = message.get("src")
                encoded_payload = message.get("payload")
                if src and encoded_payload:
                    payload = base64.b64decode(encoded_payload)
                    await self._process_incoming_datagram(payload, src)
            else:
                # Handle other message types or log warning
                pass
        except json.JSONDecodeError:
            pass # Or log error

    async def _process_incoming_datagram(self, payload: bytes, src_node: str) -> None:
        """Processes an incoming datagram (to be implemented/hooked up)."""
        # This should eventually pass the datagram to registered ProtocolPlugins
        pass

    async def run(self) -> None:
        """Main event loop for the node."""
        self._running = True
        await self.connect()

        try:
            if self.websocket:
                async for message in self.websocket:
                    if not self._running:
                        break
                    await self._handle_message(message) # type: ignore
        except websockets.exceptions.ConnectionClosed:
            pass # Or attempt reconnect
        finally:
            await self.disconnect()

    def stop(self) -> None:
        """Stops the node loop."""
        self._running = False
