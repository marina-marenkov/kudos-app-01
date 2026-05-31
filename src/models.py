from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB_ENV_VAR = "KUDOS_DB_PATH"
DEFAULT_DB_FILENAME = "kudos.db"


def _resolve_db_path(db_path: str | Path | None = None) -> str | Path:
    if db_path is not None:
        if str(db_path) == ":memory:":
            return ":memory:"
        return Path(db_path).expanduser().resolve()

    env_path = os.getenv(DEFAULT_DB_ENV_VAR)
    if env_path:
        if env_path == ":memory:":
            return ":memory:"
        return Path(env_path).expanduser().resolve()

    return Path(DEFAULT_DB_FILENAME).resolve()


def _get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(_resolve_db_path(db_path))
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: str | Path | None = None) -> None:
    with _get_connection(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS kudos (
                id INTEGER PRIMARY KEY,
                from_user TEXT,
                to_user TEXT,
                message TEXT,
                category TEXT,
                created_at TIMESTAMP
            )
            """
        )
        connection.commit()


def give_kudos(
    from_user: str,
    to_user: str,
    message: str,
    category: str = "general",
    created_at: datetime | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    init_db(db_path)
    timestamp = (created_at or datetime.now(timezone.utc)).isoformat()

    with _get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO kudos (from_user, to_user, message, category, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (from_user, to_user, message, category, timestamp),
        )
        row = connection.execute(
            """
            SELECT id, from_user, to_user, message, category, created_at
            FROM kudos
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
        connection.commit()

    return dict(row) if row is not None else {}


def get_kudos_for_user(
    username: str,
    limit: int | None = None,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    init_db(db_path)

    base_query = (
        """
        SELECT id, from_user, to_user, message, category, created_at
        FROM kudos
        WHERE to_user = ?
        ORDER BY created_at DESC, id DESC
        """
    )
    params: tuple[Any, ...]
    if limit is not None:
        base_query += " LIMIT ?"
        params = (username, limit)
    else:
        params = (username,)

    with _get_connection(db_path) as connection:
        rows = connection.execute(base_query, params).fetchall()

    return [dict(row) for row in rows]


def get_leaderboard(
    limit: int = 10,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    init_db(db_path)

    with _get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT to_user, COUNT(*) AS kudos_count
            FROM kudos
            GROUP BY to_user
            ORDER BY kudos_count DESC, to_user ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_recent(
    limit: int = 10,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    init_db(db_path)

    with _get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, from_user, to_user, message, category, created_at
            FROM kudos
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]
