import asyncio
from typing import Callable, Any, Dict, Optional
from retro_net.protocols.base import ProtocolPlugin
from .clnp import CLNPHeader, NLPID_CLNP, NLPID_ESIS, NLPID_ISIS
from .tp4 import TP4Header
from .esis import ESISHeader
from .isis import ISISHeader

class OSIPlugin(ProtocolPlugin):
    """
    OSI Protocol Stack Plugin. Handles CLNP routing and dispatches to
    upper layer protocols (TP4) or routing protocols (ES-IS, IS-IS).
    """

    def __init__(self, node_ref: Any) -> None:
        super().__init__()
        self.node = node_ref

        # NLPID handlers mapping
        self._registered_handlers: Dict[int, Callable[[bytes, str], Any]] = {}

    def register_upper_layer(self, port: int, callback: Callable[[bytes, str, int], Any]) -> None:
        """
        Register a callback for an upper-layer protocol based on NLPID.
        Note: The callback signature defined in ProtocolPlugin passes `port` (int)
        which we will interpret as the NLPID.
        """
        self._registered_handlers[port] = callback

    async def process_datagram(self, payload: bytes, src_node: str) -> None:
        """
        Process an incoming datagram payload.
        In the OSI model, this first level is often the Network Layer (CLNP, ES-IS, IS-IS).
        """
        if not payload:
            return

        # The first byte of the OSI network layer packet is the NLPID
        nlpid = payload[0]

        try:
            if nlpid == NLPID_CLNP:
                await self._handle_clnp(payload, src_node)
            elif nlpid == NLPID_ESIS:
                await self._handle_esis(payload, src_node)
            elif nlpid == NLPID_ISIS:
                await self._handle_isis(payload, src_node)
            else:
                print(f"OSI Parse error: Unknown NLPID 0x{nlpid:02x}")
        except Exception as e:
            print(f"OSI Parse error: {e}")

    async def _handle_clnp(self, payload: bytes, src_node: str) -> None:
        """Handle CLNP datagrams and route to upper layers."""
        parsed_header = CLNPHeader.parse(payload)

        # In a full implementation, we'd process the destination address
        # and route if we are an IS, or pass to upper layer if we are the destination ES.

        # Extract payload data (skip the CLNP header)
        header_length = parsed_header.length_indicator
        data = payload[header_length:]

        # The transport layer usually sits on top of CLNP.
        # In this minimal setup, if there's data and TP4 is registered, we pass it up.
        # Often the NLPID for the upper layer isn't explicitly in the CLNP header
        # (unlike IP where 'protocol' is in the header), but rather the Transport
        # layer infers it or it's known based on connection.
        # For our purposes, we'll assume the payload belongs to TP4 if a handler is registered.

        tp4_nlpid = 0x84 # Let's use 0x84 as our internal TP4 port/NLPID representation
        if tp4_nlpid in self._registered_handlers:
            handler = self._registered_handlers[tp4_nlpid]
            if asyncio.iscoroutinefunction(handler):
                await handler(data, src_node, tp4_nlpid)
            else:
                handler(data, src_node, tp4_nlpid)

    async def _handle_esis(self, payload: bytes, src_node: str) -> None:
        """Handle ES-IS routing protocol datagrams."""
        # For now, just parse and pass to the registered ES-IS handler
        if NLPID_ESIS in self._registered_handlers:
            handler = self._registered_handlers[NLPID_ESIS]
            if asyncio.iscoroutinefunction(handler):
                await handler(payload, src_node, NLPID_ESIS)
            else:
                handler(payload, src_node, NLPID_ESIS)
        else:
            # Just parse to verify it's valid if no handler
            ESISHeader.parse(payload)

    async def _handle_isis(self, payload: bytes, src_node: str) -> None:
        """Handle IS-IS routing protocol datagrams."""
        # For now, just parse and pass to the registered IS-IS handler
        if NLPID_ISIS in self._registered_handlers:
            handler = self._registered_handlers[NLPID_ISIS]
            if asyncio.iscoroutinefunction(handler):
                await handler(payload, src_node, NLPID_ISIS)
            else:
                handler(payload, src_node, NLPID_ISIS)
        else:
            # Just parse to verify it's valid if no handler
            ISISHeader.parse(payload)
