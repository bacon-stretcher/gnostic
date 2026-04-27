from abc import ABC, abstractmethod
from typing import Callable, Any, Dict

class ProtocolPlugin(ABC):
    """Abstract base class for all protocol plugins."""

    def __init__(self) -> None:
        self._registered_handlers: Dict[int, Callable[..., Any]] = {}

    @abstractmethod
    async def process_datagram(self, payload: bytes, src_node: str) -> None:
        """
        Process an incoming datagram payload.

        Args:
            payload: The binary payload of the datagram.
            src_node: The source node identifier.
        """
        pass

    @abstractmethod
    def register_upper_layer(self, port: int, callback: Callable[[bytes, str, int], Any]) -> None:
        """
        Register a callback for an upper-layer protocol or port.

        Args:
            port: The port or protocol number to register.
            callback: The async callback function to handle incoming data for this port.
        """
        pass
