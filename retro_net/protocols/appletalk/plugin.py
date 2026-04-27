from typing import Dict, Callable, Any, Optional, List, Tuple
from retro_net.protocols.base import ProtocolPlugin
from .ddp import DDPHeader
from .nbp import NBPHeader, NBP_SOCKET

class AppleTalkPlugin(ProtocolPlugin):
    """
    AppleTalk Protocol Stack. Handles DDP and basic NBP.
    """
    def __init__(self, node_ref: Any) -> None:
        super().__init__()
        self.node = node_ref

        # Upper layer callbacks
        self._registered_handlers: Dict[int, Callable[[bytes, str], Any]] = {}

        # NBP Registry: (object_name, type_name) -> socket
        self.nbp_registry: Dict[Tuple[str, str], int] = {}

        # Register NBP to handle its own traffic
        self.register_upper_layer(NBP_SOCKET, self._handle_nbp)

    def register_upper_layer(self, port: int, callback: Callable[[bytes, str], Any]) -> None:
        self._registered_handlers[port] = callback

    def register_service(self, object_name: str, type_name: str, socket: int) -> None:
        """Register a local service with NBP."""
        self.nbp_registry[(object_name, type_name)] = socket

    async def process_datagram(self, payload: bytes, src_node: str) -> None:
        """Process an incoming DDP datagram."""
        try:
            parsed_header = DDPHeader.parse(payload[:13])
            dest_socket = parsed_header.dest_socket
            data = payload[13:]

            if dest_socket in self._registered_handlers:
                # We need to await the handler if it's an async function,
                # but currently the type says Any. Let's assume it could be async.
                handler = self._registered_handlers[dest_socket]
                import asyncio
                if asyncio.iscoroutinefunction(handler):
                    await handler(data, src_node)
                else:
                    handler(data, src_node)
        except Exception as e:
            # Drop malformed DDP packet
            print(f"DDP Parse error: {e}")

    async def _handle_nbp(self, payload: bytes, src_node: str) -> None:
        """Handle NBP requests."""
        try:
            nbp_packet = NBPHeader.parse(payload)
            function = nbp_packet.flags.function

            if function in ("LkUp", "BrRq"):
                # Lookup or Broadcast Request
                replies = []
                for nbp_tuple in nbp_packet.tuples:
                    # In a real implementation we might support wildcards, but for simplicity:
                    obj_name = nbp_tuple.object_name
                    type_name = nbp_tuple.type_name

                    # Wildcard support
                    for (reg_obj, reg_type), socket in self.nbp_registry.items():
                        if (obj_name == "=" or obj_name == reg_obj) and (type_name == "=" or type_name == reg_type):
                            # Match found
                            reply_tuple = {
                                "network": 0, # Assuming 0 for local network right now
                                "node": 0, # In reality this would be our node's id or address
                                "socket": socket,
                                "enumerator": nbp_tuple.enumerator,
                                "object_name": reg_obj,
                                "type_name": reg_type,
                                "zone_name": "*"
                            }
                            replies.append(reply_tuple)

                if replies:
                    # Send LkUpReply
                    reply_header = {
                        "flags": {
                            "function": "LkUpReply",
                            "tuple_count": len(replies)
                        },
                        "nbp_id": nbp_packet.nbp_id,
                        "tuples": replies
                    }
                    reply_bytes = NBPHeader.build(reply_header)

                    # DDP Header for reply
                    # Swap src and dest
                    # We need the original DDP header to know the src socket
                    # Actually we don't have it here since we stripped it.
                    # Let's say NBP requests always come from NBP socket
                    dest_socket = NBP_SOCKET

                    ddp_reply = {
                        "flags_hop_length": {
                            "reserved": 0,
                            "hop_count": 0,
                            "length": 13 + len(reply_bytes)
                        },
                        "checksum": 0,
                        "dest_network": 0,
                        "src_network": 0,
                        "dest_node": 0, # The destination node byte? Actually src_node is a string in our system.
                        "src_node": 0,
                        "dest_socket": dest_socket,
                        "src_socket": NBP_SOCKET,
                        "type": 2 # NBP
                    }
                    ddp_bytes = DDPHeader.build(ddp_reply)

                    await self.node.send_datagram(src_node, 'appletalk', ddp_bytes + reply_bytes)

        except Exception as e:
            print(f"NBP Parse error: {e}")

    async def broadcast_lookup(self, object_name: str, type_name: str) -> None:
        """Broadcast an NBP lookup to the network."""
        nbp_req = {
            "flags": {
                "function": "BrRq",
                "tuple_count": 1
            },
            "nbp_id": 1, # Should be unique per request, simplified for now
            "tuples": [{
                "network": 0,
                "node": 0,
                "socket": 0,
                "enumerator": 1,
                "object_name": object_name,
                "type_name": type_name,
                "zone_name": "*"
            }]
        }
        nbp_bytes = NBPHeader.build(nbp_req)

        ddp_req = {
            "flags_hop_length": {
                "reserved": 0,
                "hop_count": 0,
                "length": 13 + len(nbp_bytes)
            },
            "checksum": 0,
            "dest_network": 0,
            "src_network": 0,
            "dest_node": 255, # Broadcast node in AppleTalk
            "src_node": 0,
            "dest_socket": NBP_SOCKET,
            "src_socket": NBP_SOCKET,
            "type": 2 # NBP
        }
        ddp_bytes = DDPHeader.build(ddp_req)

        # Broadcast via node (node sends to all if dest_node='*')
        await self.node.send_datagram('*', 'appletalk', ddp_bytes + nbp_bytes)
