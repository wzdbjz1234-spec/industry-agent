"""Small transaction boundary used by durable adapters.

The domain does not know about SQLAlchemy sessions.  This context manager is the
single seam where an application use case can atomically write state and an Outbox
record using one database transaction.
"""

from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any, Protocol, Self


class TransactionProvider(Protocol):
    def begin(self) -> AbstractContextManager[Any]:
        """Start a transaction that commits on normal exit and rolls back on error."""


class Transaction(AbstractContextManager[Any]):
    def __init__(self, provider: TransactionProvider) -> None:
        self._provider = provider
        self._context: AbstractContextManager[Any] | None = None
        self._connection: Any = None

    def __enter__(self) -> Self:
        self._context = self._provider.begin()
        self._connection = self._context.__enter__()
        return self

    @property
    def connection(self) -> Any:
        if self._connection is None:
            raise RuntimeError("transaction has not been entered")
        return self._connection

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        assert self._context is not None
        return self._context.__exit__(exc_type, exc_value, traceback)
