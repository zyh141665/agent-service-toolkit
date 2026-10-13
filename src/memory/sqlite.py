from contextlib import AbstractAsyncContextManager

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.sqlite.aio import AsyncSqliteStore

from core.settings import settings


def get_sqlite_saver() -> AbstractAsyncContextManager[AsyncSqliteSaver]:
    """Initialize and return a SQLite saver instance."""
    return AsyncSqliteSaver.from_conn_string(settings.SQLITE_DB_PATH)


def get_sqlite_store() -> AbstractAsyncContextManager[AsyncSqliteStore]:
    """Initialize a persistent SQLite store for long-term memory."""
    return AsyncSqliteStore.from_conn_string(settings.SQLITE_DB_PATH)
