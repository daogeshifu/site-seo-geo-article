from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services import task_repository


class _DummyConnection:
    def __init__(self, *, fail_ping: bool = False) -> None:
        self.fail_ping = fail_ping
        self.closed = False
        self.ping_calls = 0

    def ping(self, reconnect: bool = False) -> None:
        self.ping_calls += 1
        if self.fail_ping:
            raise RuntimeError("connection lost")

    def close(self) -> None:
        self.closed = True


def _build_mysql_repo_for_unit_test(monkeypatch: pytest.MonkeyPatch) -> task_repository.MySQLTaskRepository:
    monkeypatch.setattr(task_repository.MySQLTaskRepository, "_ensure_database", lambda self: None)
    monkeypatch.setattr(task_repository.MySQLTaskRepository, "_ensure_tables", lambda self: None)
    monkeypatch.setattr(task_repository.MySQLTaskRepository, "_ensure_task_columns", lambda self: None)
    settings = Settings(
        mysql_host="127.0.0.1",
        mysql_user="demo",
        mysql_retry_count=2,
        mysql_retry_delay_seconds=0.01,
        mysql_pool_size=2,
    )
    return task_repository.MySQLTaskRepository(settings)


def test_build_task_repository_falls_back_to_memory_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        mysql_host="127.0.0.1",
        mysql_user="demo",
        mysql_fallback_to_memory=True,
    )

    def failing_mysql_repo(_settings: Settings):
        raise RuntimeError("mysql unavailable")

    monkeypatch.setattr(task_repository, "MySQLTaskRepository", failing_mysql_repo)
    repo = task_repository.build_task_repository(settings)
    assert isinstance(repo, task_repository.MemoryTaskRepository)


def test_build_task_repository_raises_when_fallback_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        mysql_host="127.0.0.1",
        mysql_user="demo",
        mysql_fallback_to_memory=False,
    )

    def failing_mysql_repo(_settings: Settings):
        raise RuntimeError("mysql unavailable")

    monkeypatch.setattr(task_repository, "MySQLTaskRepository", failing_mysql_repo)
    with pytest.raises(RuntimeError, match="mysql unavailable"):
        task_repository.build_task_repository(settings)


def test_serialize_task_row_handles_missing_optional_fields() -> None:
    payload = task_repository._serialize_task_row(
        {
            "id": "2",
            "category": "seo",
            "keyword": "portable charger",
            "info": "Brand: VoltGo",
            "language": None,
            "force_refresh": "0",
            "cache_key": None,
            "status": None,
            "cache_hit": None,
        }
    )

    assert payload["task_id"] == 2
    assert payload["language"] == "English"
    assert payload["include_cover"] == 1
    assert payload["content_image_count"] == 0
    assert payload["status"] == "queued"
    assert payload["cache_hit"] is False


def test_serialize_result_row_handles_invalid_json_payload() -> None:
    payload = task_repository._serialize_result_row(
        {
            "task_id": "9",
            "article_json": "{this is invalid json",
            "created_at": None,
            "updated_at": None,
        }
    )

    assert payload["task_id"] == 9
    assert payload["article"] is None


def test_mysql_pool_reuses_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _build_mysql_repo_for_unit_test(monkeypatch)
    created: list[_DummyConnection] = []

    def fake_connect_new(*, use_database: bool = True):
        connection = _DummyConnection()
        created.append(connection)
        return connection

    monkeypatch.setattr(repo, "_connect_new", fake_connect_new)
    first = repo._borrow_connection()
    repo._release_connection(first, reusable=True)
    second = repo._borrow_connection()

    assert first is second
    assert len(created) == 1
    repo._release_connection(second, reusable=True)


def test_mysql_pool_reconnects_when_cached_connection_is_broken(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _build_mysql_repo_for_unit_test(monkeypatch)
    broken = _DummyConnection(fail_ping=True)
    created: list[_DummyConnection] = []

    def fake_connect_new(*, use_database: bool = True):
        connection = _DummyConnection()
        created.append(connection)
        return connection

    monkeypatch.setattr(repo, "_connect_new", fake_connect_new)
    repo._release_connection(broken, reusable=True)

    connection = repo._borrow_connection()
    assert broken.closed is True
    assert connection is created[0]
    repo._release_connection(connection, reusable=True)


def test_mysql_operation_retries_and_reconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _build_mysql_repo_for_unit_test(monkeypatch)
    connections = [_DummyConnection(), _DummyConnection()]
    released: list[tuple[_DummyConnection, bool]] = []

    monkeypatch.setattr(repo, "_borrow_connection", lambda use_database=True: connections.pop(0))
    monkeypatch.setattr(
        repo,
        "_release_connection",
        lambda connection, reusable, use_database=True: released.append((connection, reusable)),
    )
    monkeypatch.setattr(task_repository.time, "sleep", lambda _: None)

    calls = {"count": 0}

    def flaky_operation(_connection: _DummyConnection) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise task_repository.pymysql.err.OperationalError(2006, "MySQL server has gone away")
        return "ok"

    result = repo._run_with_retry(flaky_operation)
    assert result == "ok"
    assert calls["count"] == 2
    assert released[0][1] is False
    assert released[1][1] is True
