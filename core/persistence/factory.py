from core.persistence.exceptions import (
    PersistenceBackendNotImplementedError,
    UnsupportedPersistenceBackendError,
)
from core.persistence.interfaces import PositionRepository
from core.persistence.memory import MemoryPositionRepository


class PersistenceFactory:
    """Factory for persistence backends."""

    @staticmethod
    def create_position_repository(backend: str = "memory") -> PositionRepository:
        """Create position repository for selected backend."""

        normalized_backend = backend.lower().strip()

        if normalized_backend == "memory":
            return MemoryPositionRepository()

        if normalized_backend == "postgres":
            raise PersistenceBackendNotImplementedError(
                "PostgreSQL position repository is planned but not implemented in v1.6.1"
            )

        raise UnsupportedPersistenceBackendError(
            f"Unsupported persistence backend: {backend!r}"
        )