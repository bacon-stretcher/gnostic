import asyncio
import json
from typing import Dict, Set
import websockets
from websockets.server import WebSocketServerProtocol

class Switch:
    """A standalone WebSocket server to route JSON between nodes."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host: str = host
        self.port: int = port
        self.nodes: Dict[str, WebSocketServerProtocol] = {}

    async def handle_client(self, websocket: WebSocketServerProtocol) -> None:
        """Handles a new client connection."""
        node_id = None
        try:
            async for message in websocket:
                try:
                    data = json.loads(message) # type: ignore
                    action = data.get("action")
                    dest_id = data.get("dst_node")

                    if action == "register":
                        node_id = data.get("node_id")
                        if node_id:
                            self.nodes[node_id] = websocket
                            print(f"Node {node_id} registered.")
                    elif dest_id:
                        if dest_id in self.nodes:
                            # Route the message to the destination
                            dest_ws = self.nodes[dest_id]
                            await dest_ws.send(message)
                        else:
                            print(f"Destination {dest_id} not found.")
                except json.JSONDecodeError:
                    print("Received invalid JSON.")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            if node_id and node_id in self.nodes and self.nodes[node_id] == websocket:
                del self.nodes[node_id]
                print(f"Node {node_id} disconnected.")

    async def serve(self) -> None:
        """Starts the WebSocket server."""
        async with websockets.serve(self.handle_client, self.host, self.port):
            print(f"Switch listening on ws://{self.host}:{self.port}")
            await asyncio.Future()  # Run forever

if __name__ == "__main__":
    switch = Switch()
    asyncio.run(switch.serve())
