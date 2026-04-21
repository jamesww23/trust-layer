"""Custom exceptions for the aitrustlayer SDK."""


class TrustLayerError(Exception):
    """Base exception for all trust layer errors."""
    pass


class ConnectionError(TrustLayerError):
    """Raised when unable to connect to the trust layer server."""
    pass


class ServerError(TrustLayerError):
    """Raised when the server returns a 5xx error."""
    pass


class ClientError(TrustLayerError):
    """Raised when there's a client-side error (4xx)."""
    pass


class ValidationError(ClientError):
    """Raised when request validation fails."""
    pass


class NotFoundError(ClientError):
    """Raised when a requested resource is not found (404)."""
    pass


class AuthenticationError(ClientError):
    """Raised when authentication fails."""
    pass


class ConflictError(ClientError):
    """Raised when there's a conflict (e.g., agent already exists)."""
    pass


class TrustGateError(ClientError):
    """Raised when trust gate blocks delegation."""
    pass


class FeedbackRequired(ClientError):
    """Raised when mandatory feedback is required before delegation."""
    pass


class TimeoutError(TrustLayerError):
    """Raised when request times out."""
    pass
