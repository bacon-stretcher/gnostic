from abc import ABC, abstractmethod

class ServicePlugin(ABC):
    """Abstract base class for all service plugins."""

    @abstractmethod
    async def start(self) -> None:
        """Starts the service."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stops the service."""
        pass
