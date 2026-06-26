from core.persistence.exceptions import PersistenceBackendNotImplementedError


class PostgresPositionRepository:
    """PostgreSQL position repository placeholder for future implementation."""

    def __init__(self) -> None:
        raise PersistenceBackendNotImplementedError(
            "PostgreSQL position repository is not implemented in v1.6.1"
        )