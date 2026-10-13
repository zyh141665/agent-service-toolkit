from unittest.mock import patch

import pytest

from memory.sqlite import get_sqlite_store


@pytest.mark.asyncio
async def test_sqlite_store_persists_across_connections(tmp_path):
    database_path = tmp_path / "memory.db"

    with patch("memory.sqlite.settings.SQLITE_DB_PATH", str(database_path)):
        async with get_sqlite_store() as store:
            await store.setup()
            await store.aput(("user-1",), "birthdate", {"birthdate": "2000-01-02"})

        async with get_sqlite_store() as store:
            await store.setup()
            saved_birthdate = await store.aget(("user-1",), "birthdate")

    assert saved_birthdate is not None
    assert saved_birthdate.value == {"birthdate": "2000-01-02"}
