from __future__ import annotations

import json
import logging
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Full, LifoQueue
from threading import Lock
from typing import Any, Callable, Protocol

from app.core.config import Settings
from app.services.task_modes import normalize_mode_type
from app.utils.common import canonical_json

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:  # pragma: no cover - exercised only when dependency is missing at runtime
    pymysql = None
    DictCursor = None


logger = logging.getLogger(__name__)
TASK_TABLE = "article_tasks"
RESULT_TABLE = "article_task_results"
SCHEMA_SQL_PATH = Path(__file__).resolve().parents[2] / "database" / "mysql_schema.template.sql"


class TaskRepository(Protocol):
    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def get_task(self, task_id: int) -> dict[str, Any] | None: ...

    def list_tasks(self, limit: int = 10, mode_types: list[int] | None = None) -> list[dict[str, Any]]: ...

    def find_reusable_task(
        self,
        *,
        category: str,
        keyword: str,
        mode_type: int,
        info: str,
        task_context: dict[str, Any],
        language: str,
        word_limit: int,
        access_tier: str,
        provider: str = "openai",
    ) -> dict[str, Any] | None: ...

    def update_task(self, task_id: int, **fields: Any) -> None: ...

    def save_result(self, task_id: int, article: dict[str, Any]) -> dict[str, Any]: ...

    def get_result(self, task_id: int) -> dict[str, Any] | None: ...


def build_task_repository(settings: Settings) -> TaskRepository:
    if settings.mysql_host and settings.mysql_user:
        try:
            return MySQLTaskRepository(settings)
        except Exception:
            if settings.mysql_fallback_to_memory:
                logger.exception(
                    "Failed to initialize MySQL task repository; falling back to in-memory task storage."
                )
                return MemoryTaskRepository()
            raise
    return MemoryTaskRepository()


class MemoryTaskRepository:
    def __init__(self) -> None:
        self._lock = Lock()
        self._next_id = 1
        self._tasks: dict[int, dict[str, Any]] = {}
        self._results: dict[int, dict[str, Any]] = {}

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            task_id = self._next_id
            self._next_id += 1
            now = _utcnow_iso()
            task = {
                "task_id": task_id,
                **payload,
                "cache_hit": False,
                "error_message": None,
                "created_at": now,
                "updated_at": now,
                "completed_at": None,
            }
            self._tasks[task_id] = task
            return deepcopy(task)

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(int(task_id))
            return deepcopy(task) if task else None

    def list_tasks(self, limit: int = 10, mode_types: list[int] | None = None) -> list[dict[str, Any]]:
        with self._lock:
            allowed_mode_types = {normalize_mode_type(item) for item in mode_types or []}
            items = sorted(self._tasks.values(), key=lambda item: int(item.get("task_id", 0)), reverse=True)
            rows: list[dict[str, Any]] = []
            for task in items:
                if allowed_mode_types and normalize_mode_type(task.get("mode_type")) not in allowed_mode_types:
                    continue
                row = deepcopy(task)
                result = self._results.get(int(task.get("task_id", 0)))
                if result:
                    row["article_title"] = result.get("article_title")
                    row["meta_title"] = result.get("meta_title")
                    row["meta_description"] = result.get("meta_description")
                    row["generation_mode"] = result.get("generation_mode")
                    row["image_generation_mode"] = result.get("image_generation_mode")
                    row["has_result"] = True
                else:
                    row["has_result"] = False
                rows.append(row)
                if len(rows) >= max(1, int(limit)):
                    break
            return rows

    def find_reusable_task(
        self,
        *,
        category: str,
        keyword: str,
        mode_type: int,
        info: str,
        task_context: dict[str, Any],
        language: str,
        word_limit: int,
        access_tier: str,
        provider: str = "openai",
    ) -> dict[str, Any] | None:
        with self._lock:
            matches = [
                task
                for task in self._tasks.values()
                if task.get("category") == category
                and task.get("keyword") == keyword
                and int(task.get("mode_type", 1)) == int(mode_type)
                and task.get("info") == info
                and canonical_json(task.get("task_context") or {}) == canonical_json(task_context or {})
                and task.get("language") == language
                and int(task.get("word_limit", 1200)) == int(word_limit)
                and str(task.get("access_tier") or "standard") == access_tier
                and str(task.get("provider") or "openai") == (provider or "openai")
                and task.get("status") == "completed"
                and int(task.get("task_id", 0)) in self._results
            ]
            if not matches:
                return None
            matches.sort(key=lambda item: int(item.get("task_id", 0)), reverse=True)
            return deepcopy(matches[0])

    def update_task(self, task_id: int, **fields: Any) -> None:
        with self._lock:
            task = self._tasks[int(task_id)]
            task.update(fields)
            task["updated_at"] = _utcnow_iso()

    def save_result(self, task_id: int, article: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            now = _utcnow_iso()
            record = {
                "task_id": int(task_id),
                "article_title": article.get("title"),
                "meta_title": article.get("meta_title"),
                "meta_description": article.get("meta_description"),
                "generation_mode": article.get("generation_mode"),
                "image_generation_mode": article.get("image_generation_mode"),
                "article": deepcopy(article),
                "created_at": self._results.get(int(task_id), {}).get("created_at", now),
                "updated_at": now,
            }
            self._results[int(task_id)] = record
            return deepcopy(record)

    def get_result(self, task_id: int) -> dict[str, Any] | None:
        with self._lock:
            record = self._results.get(int(task_id))
            return deepcopy(record) if record else None


class MySQLTaskRepository:
    def __init__(self, settings: Settings) -> None:
        if pymysql is None:
            raise RuntimeError("PyMySQL is required when MYSQL_HOST / MYSQL_USER are configured.")
        self.settings = settings
        self.database_name = settings.mysql_database or settings.mysql_user
        if not self.database_name:
            raise RuntimeError("MYSQL_DATABASE or MYSQL_USER is required for MySQL task storage.")
        self.pool_size = max(1, int(getattr(settings, "mysql_pool_size", 8)))
        self._connection_pool: LifoQueue[Any] = LifoQueue(maxsize=self.pool_size)
        self._ensure_database()
        self._ensure_tables()
        self._ensure_task_columns()

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = _utcnow_db()

        def _operation(connection: Any) -> int:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {TASK_TABLE} (
                        category,
                        keyword,
                        mode_type,
                        info,
                        task_context_json,
                        language,
                        provider,
                        word_limit,
                        force_refresh,
                        include_cover,
                        content_image_count,
                        access_tier,
                        cache_key,
                        status,
                        cache_hit,
                        error_message,
                        created_at,
                        updated_at,
                        completed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        payload["category"],
                        payload["keyword"],
                        int(payload.get("mode_type", 1)),
                        payload["info"],
                        canonical_json(payload.get("task_context") or {}),
                        payload["language"],
                        payload.get("provider", "openai"),
                        int(payload.get("word_limit", 1200)),
                        int(bool(payload["force_refresh"])),
                        int(payload["include_cover"]),
                        int(payload["content_image_count"]),
                        payload["access_tier"],
                        payload["cache_key"],
                        payload["status"],
                        int(bool(payload.get("cache_hit", False))),
                        payload.get("error_message"),
                        now,
                        now,
                        None,
                    ),
                )
                return int(cursor.lastrowid)

        task_id = self._run_with_retry(_operation)
        task = self.get_task(task_id)
        if not task:
            raise RuntimeError("Failed to create task row in MySQL.")
        return task

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        def _operation(connection: Any) -> dict[str, Any] | None:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT * FROM {TASK_TABLE} WHERE id = %s LIMIT 1",
                    (int(task_id),),
                )
                return cursor.fetchone()

        row = self._run_with_retry(_operation)
        return _serialize_task_row(row) if row else None

    def list_tasks(self, limit: int = 10, mode_types: list[int] | None = None) -> list[dict[str, Any]]:
        def _operation(connection: Any) -> list[dict[str, Any]]:
            with connection.cursor() as cursor:
                allowed_mode_types = [normalize_mode_type(item) for item in mode_types or []]
                where_clause = ""
                values: list[Any] = []
                if allowed_mode_types:
                    placeholders = ", ".join(["%s"] * len(allowed_mode_types))
                    where_clause = f"WHERE t.mode_type IN ({placeholders})"
                    values.extend(allowed_mode_types)
                values.append(max(1, int(limit)))
                cursor.execute(
                    f"""
                    SELECT
                        t.*,
                        r.article_title,
                        r.meta_title,
                        r.meta_description,
                        r.generation_mode,
                        r.image_generation_mode
                    FROM {TASK_TABLE} AS t
                    LEFT JOIN {RESULT_TABLE} AS r ON r.task_id = t.id
                    {where_clause}
                    ORDER BY t.id DESC
                    LIMIT %s
                    """,
                    values,
                )
                return cursor.fetchall() or []

        rows = self._run_with_retry(_operation)
        return [_serialize_task_row(row) for row in rows]

    def find_reusable_task(
        self,
        *,
        category: str,
        keyword: str,
        mode_type: int,
        info: str,
        task_context: dict[str, Any],
        language: str,
        word_limit: int,
        access_tier: str,
        provider: str = "openai",
    ) -> dict[str, Any] | None:
        def _operation(connection: Any) -> dict[str, Any] | None:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT t.*
                    FROM {TASK_TABLE} AS t
                    INNER JOIN {RESULT_TABLE} AS r ON r.task_id = t.id
                    WHERE t.category = %s
                      AND t.keyword = %s
                      AND t.mode_type = %s
                      AND t.info = %s
                      AND t.task_context_json = %s
                      AND t.language = %s
                      AND t.word_limit = %s
                      AND t.access_tier = %s
                      AND t.provider = %s
                      AND t.status = 'completed'
                    ORDER BY t.id DESC
                    LIMIT 1
                    """,
                    (
                        category,
                        keyword,
                        int(mode_type),
                        info,
                        canonical_json(task_context or {}),
                        language,
                        int(word_limit),
                        access_tier,
                        provider or "openai",
                    ),
                )
                return cursor.fetchone()

        row = self._run_with_retry(_operation)
        return _serialize_task_row(row) if row else None

    def update_task(self, task_id: int, **fields: Any) -> None:
        if not fields:
            return
        assignments: list[str] = []
        values: list[Any] = []
        for key, value in fields.items():
            assignments.append(f"{key} = %s")
            if key in {"force_refresh", "cache_hit"}:
                values.append(int(bool(value)))
            elif key in {"include_cover", "content_image_count"} and value is not None:
                values.append(int(value))
            elif key == "completed_at" and isinstance(value, str):
                values.append(_iso_to_db_datetime(value))
            else:
                values.append(value)
        assignments.append("updated_at = %s")
        values.append(_utcnow_db())
        values.append(int(task_id))

        def _operation(connection: Any) -> None:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {TASK_TABLE} SET {', '.join(assignments)} WHERE id = %s",
                    values,
                )

        self._run_with_retry(_operation)

    def save_result(self, task_id: int, article: dict[str, Any]) -> dict[str, Any]:
        now = _utcnow_db()
        article_json = json.dumps(article, ensure_ascii=False)

        def _operation(connection: Any) -> None:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {RESULT_TABLE} (
                        task_id,
                        article_title,
                        meta_title,
                        meta_description,
                        generation_mode,
                        image_generation_mode,
                        article_json,
                        created_at,
                        updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        article_title = VALUES(article_title),
                        meta_title = VALUES(meta_title),
                        meta_description = VALUES(meta_description),
                        generation_mode = VALUES(generation_mode),
                        image_generation_mode = VALUES(image_generation_mode),
                        article_json = VALUES(article_json),
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        int(task_id),
                        article.get("title"),
                        article.get("meta_title"),
                        article.get("meta_description"),
                        article.get("generation_mode"),
                        article.get("image_generation_mode"),
                        article_json,
                        now,
                        now,
                    ),
                )

        self._run_with_retry(_operation)
        result = self.get_result(task_id)
        if not result:
            raise RuntimeError("Failed to persist task result in MySQL.")
        return result

    def get_result(self, task_id: int) -> dict[str, Any] | None:
        def _operation(connection: Any) -> dict[str, Any] | None:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT * FROM {RESULT_TABLE} WHERE task_id = %s LIMIT 1",
                    (int(task_id),),
                )
                return cursor.fetchone()

        row = self._run_with_retry(_operation)
        return _serialize_result_row(row) if row else None

    def _build_connect_params(self, *, use_database: bool = True) -> dict[str, Any]:
        params: dict[str, Any] = {
            "host": self.settings.mysql_host,
            "port": int(self.settings.mysql_port),
            "user": self.settings.mysql_user,
            "password": self.settings.mysql_password,
            "charset": self.settings.mysql_charset,
            "connect_timeout": int(self.settings.mysql_connect_timeout),
            "read_timeout": int(self.settings.mysql_read_timeout),
            "write_timeout": int(self.settings.mysql_write_timeout),
            "cursorclass": DictCursor,
            "autocommit": True,
        }
        if use_database:
            params["database"] = self.database_name
        return params

    def _connect_new(self, *, use_database: bool = True):
        params = self._build_connect_params(use_database=use_database)
        retry_count = max(1, int(self.settings.mysql_retry_count))
        retry_delay = max(0.1, float(self.settings.mysql_retry_delay_seconds))
        for attempt in range(1, retry_count + 1):
            try:
                return pymysql.connect(**params)
            except Exception as exc:
                should_retry = (
                    pymysql is not None
                    and isinstance(exc, (pymysql.err.OperationalError, pymysql.err.InterfaceError))
                    and attempt < retry_count
                )
                if not should_retry:
                    raise
                logger.warning(
                    "MySQL connection failed (attempt %s/%s): %s",
                    attempt,
                    retry_count,
                    exc,
                )
                time.sleep(retry_delay)
        raise RuntimeError("Unable to establish MySQL connection after retries.")

    def _borrow_connection(self, *, use_database: bool = True):
        if not use_database:
            return self._connect_new(use_database=False)
        try:
            connection = self._connection_pool.get_nowait()
        except Empty:
            connection = self._connect_new(use_database=True)
        try:
            connection.ping(reconnect=True)
        except Exception:
            self._safe_close(connection)
            connection = self._connect_new(use_database=True)
        return connection

    def _release_connection(self, connection: Any, *, reusable: bool, use_database: bool = True) -> None:
        if connection is None:
            return
        if not use_database or not reusable:
            self._safe_close(connection)
            return
        try:
            self._connection_pool.put_nowait(connection)
        except Full:
            self._safe_close(connection)

    def _run_with_retry(
        self,
        operation: Callable[[Any], Any],
        *,
        use_database: bool = True,
    ) -> Any:
        retry_count = max(1, int(self.settings.mysql_retry_count))
        retry_delay = max(0.1, float(self.settings.mysql_retry_delay_seconds))
        for attempt in range(1, retry_count + 1):
            connection = self._borrow_connection(use_database=use_database)
            reusable = use_database
            try:
                return operation(connection)
            except Exception as exc:
                if self._is_retriable_error(exc) and attempt < retry_count:
                    reusable = False
                    logger.warning(
                        "MySQL operation failed (attempt %s/%s): %s",
                        attempt,
                        retry_count,
                        exc,
                    )
                    time.sleep(retry_delay)
                    continue
                raise
            finally:
                self._release_connection(connection, reusable=reusable, use_database=use_database)

        raise RuntimeError("Unable to complete MySQL operation after retries.")

    def _is_retriable_error(self, exc: Exception) -> bool:
        return (
            pymysql is not None
            and isinstance(exc, (pymysql.err.OperationalError, pymysql.err.InterfaceError))
        )

    @staticmethod
    def _safe_close(connection: Any) -> None:
        if connection is None:
            return
        try:
            connection.close()
        except Exception:
            pass

    def _ensure_database(self) -> None:
        try:
            connection = self._connect_new()
            self._safe_close(connection)
            return
        except pymysql.err.OperationalError as exc:
            if exc.args and exc.args[0] != 1049:
                raise

        safe_database_name = self.database_name.replace("`", "")

        def _operation(connection: Any) -> None:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{safe_database_name}` "
                    f"CHARACTER SET {self.settings.mysql_charset} COLLATE {self.settings.mysql_charset}_unicode_ci"
                )

        self._run_with_retry(_operation, use_database=False)

    def _ensure_tables(self) -> None:
        schema_sql = SCHEMA_SQL_PATH.read_text(encoding="utf-8").format(
            database_name=self.database_name.replace("`", ""),
            charset=self.settings.mysql_charset,
        )
        statements = [statement.strip() for statement in schema_sql.split(";") if statement.strip()]

        def _operation(connection: Any) -> None:
            with connection.cursor() as cursor:
                for statement in statements:
                    if statement.upper().startswith("CREATE DATABASE"):
                        continue
                    cursor.execute(statement)

        self._run_with_retry(_operation)

    def _ensure_task_columns(self) -> None:
        def _column_exists(connection: Any, column_name: str) -> bool:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 1
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = %s
                      AND TABLE_NAME = %s
                      AND COLUMN_NAME = %s
                    LIMIT 1
                    """,
                    (self.database_name, TASK_TABLE, column_name),
                )
                return bool(cursor.fetchone())

        def _column_metadata(connection: Any, column_name: str) -> dict[str, Any] | None:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = %s
                      AND TABLE_NAME = %s
                      AND COLUMN_NAME = %s
                    LIMIT 1
                    """,
                    (self.database_name, TASK_TABLE, column_name),
                )
                return cursor.fetchone()

        if not self._run_with_retry(lambda conn: _column_exists(conn, "word_limit")):
            logger.warning("MySQL column `%s.word_limit` is missing; adding it automatically.", TASK_TABLE)

            def _add_word_limit(connection: Any) -> None:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        ALTER TABLE {TASK_TABLE}
                        ADD COLUMN word_limit INT UNSIGNED NOT NULL DEFAULT 1200
                        COMMENT 'Target text length limit (excluding image content)'
                        AFTER language
                        """
                    )

            self._run_with_retry(_add_word_limit)

        if not self._run_with_retry(lambda conn: _column_exists(conn, "provider")):
            logger.warning("MySQL column `%s.provider` is missing; adding it automatically.", TASK_TABLE)

            def _add_provider(connection: Any) -> None:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        ALTER TABLE {TASK_TABLE}
                        ADD COLUMN provider VARCHAR(128) NOT NULL DEFAULT 'openai'
                        COMMENT 'Resolved execution target, for example azure:gpt-5.4-pro'
                        AFTER language
                        """
                    )

            self._run_with_retry(_add_provider)
        else:
            provider_metadata = self._run_with_retry(lambda conn: _column_metadata(conn, "provider"))
            provider_data_type = str((provider_metadata or {}).get("DATA_TYPE") or "").lower()
            provider_max_length = (provider_metadata or {}).get("CHARACTER_MAXIMUM_LENGTH")
            if provider_data_type in {"varchar", "char"} and _as_int(provider_max_length, 0) < 64:
                logger.warning("MySQL column `%s.provider` is too short; expanding it automatically.", TASK_TABLE)

                def _expand_provider_column(connection: Any) -> None:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            f"""
                            ALTER TABLE {TASK_TABLE}
                            MODIFY COLUMN provider VARCHAR(128) NOT NULL DEFAULT 'openai'
                            COMMENT 'Resolved execution target, for example azure:gpt-5.4-pro'
                            """
                        )

                self._run_with_retry(_expand_provider_column)

        if not self._run_with_retry(lambda conn: _column_exists(conn, "task_context_json")):
            logger.warning("MySQL column `%s.task_context_json` is missing; adding it automatically.", TASK_TABLE)

            def _add_task_context_json(connection: Any) -> None:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        ALTER TABLE {TASK_TABLE}
                        ADD COLUMN task_context_json LONGTEXT NOT NULL
                        COMMENT 'Normalized task context as JSON'
                        AFTER info
                        """
                    )
                    cursor.execute(
                        f"""
                        UPDATE {TASK_TABLE}
                        SET task_context_json = '{{}}'
                        WHERE task_context_json IS NULL OR task_context_json = ''
                        """
                    )

            self._run_with_retry(_add_task_context_json)

        if not self._run_with_retry(lambda conn: _column_exists(conn, "mode_type")):
            logger.warning("MySQL column `%s.mode_type` is missing; adding it automatically.", TASK_TABLE)

            def _add_mode_type(connection: Any) -> None:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        ALTER TABLE {TASK_TABLE}
                        ADD COLUMN mode_type TINYINT UNSIGNED NOT NULL DEFAULT 1
                        COMMENT '1 keyword article, 2 outline article, 3 outline planner'
                        AFTER keyword
                        """
                    )

            self._run_with_retry(_add_mode_type)

        keyword_metadata = self._run_with_retry(lambda conn: _column_metadata(conn, "keyword"))
        keyword_data_type = str((keyword_metadata or {}).get("DATA_TYPE") or "").lower()
        keyword_max_length = (keyword_metadata or {}).get("CHARACTER_MAXIMUM_LENGTH")
        if keyword_data_type in {"varchar", "char"} and _as_int(keyword_max_length, 0) < 4096:
            logger.warning("MySQL column `%s.keyword` is too short for outline mode; expanding it automatically.", TASK_TABLE)

            def _expand_keyword_column(connection: Any) -> None:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        ALTER TABLE {TASK_TABLE}
                        MODIFY COLUMN keyword TEXT NOT NULL
                        COMMENT 'Keyword or outline source text depending on mode_type'
                        """
                    )

            self._run_with_retry(_expand_keyword_column)


def _utcnow_db() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _serialize_task_row(row: dict[str, Any]) -> dict[str, Any]:
    include_cover = max(0, min(1, _as_int(row.get("include_cover"), 1)))
    content_image_count = max(0, min(3, _as_int(row.get("content_image_count"), 0)))
    word_limit = max(200, min(10000, _as_int(row.get("word_limit"), 1200)))
    payload = {
        "task_id": _as_int(row.get("id"), 0),
        "category": str(row.get("category") or ""),
        "keyword": str(row.get("keyword") or ""),
        "mode_type": normalize_mode_type(_as_int(row.get("mode_type"), 1)),
        "info": str(row.get("info") or ""),
        "task_context": _parse_task_context(row.get("task_context_json")),
        "language": str(row.get("language") or "English"),
        "provider": str(row.get("provider") or "openai"),
        "word_limit": word_limit,
        "force_refresh": _as_bool(row.get("force_refresh"), False),
        "include_cover": include_cover,
        "content_image_count": content_image_count,
        "access_tier": str(row.get("access_tier") or "standard"),
        "cache_key": str(row.get("cache_key") or ""),
        "status": str(row.get("status") or "queued"),
        "cache_hit": _as_bool(row.get("cache_hit"), False),
        "error_message": row.get("error_message"),
        "created_at": _db_datetime_to_iso(row.get("created_at")),
        "updated_at": _db_datetime_to_iso(row.get("updated_at")),
        "completed_at": _db_datetime_to_iso(row.get("completed_at")),
    }
    if "article_title" in row:
        payload["article_title"] = row.get("article_title")
        payload["meta_title"] = row.get("meta_title")
        payload["meta_description"] = row.get("meta_description")
        payload["generation_mode"] = row.get("generation_mode")
        payload["image_generation_mode"] = row.get("image_generation_mode")
        payload["has_result"] = any(
            row.get(field) is not None
            for field in ("article_title", "meta_title", "meta_description", "generation_mode", "image_generation_mode")
        )
    return payload


def _serialize_result_row(row: dict[str, Any]) -> dict[str, Any]:
    article = _parse_article_json(row.get("article_json"))
    return {
        "task_id": _as_int(row.get("task_id"), 0),
        "article_title": row.get("article_title"),
        "meta_title": row.get("meta_title"),
        "meta_description": row.get("meta_description"),
        "generation_mode": row.get("generation_mode"),
        "image_generation_mode": row.get("image_generation_mode"),
        "article": article,
        "created_at": _db_datetime_to_iso(row.get("created_at")),
        "updated_at": _db_datetime_to_iso(row.get("updated_at")),
    }


def _parse_task_context(value: Any) -> dict[str, Any]:
    parsed = _parse_article_json(value)
    return parsed if isinstance(parsed, dict) else {}


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def _parse_article_json(value: Any) -> dict[str, Any] | list[Any] | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8")
        except Exception:
            return None
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            logger.warning("Invalid article_json payload detected; returning null article field.")
            return None
        if isinstance(parsed, (dict, list)):
            return parsed
    return None


def _db_datetime_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    return str(value)


def _iso_to_db_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)
