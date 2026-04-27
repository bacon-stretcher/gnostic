class RetroNetException(Exception):
    """Base exception for RetroNet"""
    pass

class ProtocolError(RetroNetException):
    """Raised when there is an error in protocol processing"""
    pass

class ServiceError(RetroNetException):
    """Raised when there is an error in a service plugin"""
    pass

class ConnectionError(RetroNetException):
    """Raised when there is a connection issue"""
    pass
