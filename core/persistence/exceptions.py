class PersistenceError(Exception):
    """Base exception for persistence layer errors."""


class EntityNotFoundError(PersistenceError):
    """Raised when requested entity does not exist."""


class UnsupportedPersistenceBackendError(PersistenceError):
    """Raised when persistence backend is not supported."""


class PersistenceBackendNotImplementedError(PersistenceError):
    """Raised when backend exists but is not implemented yet."""