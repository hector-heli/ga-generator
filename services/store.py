"""Persistencia de guías en SQLite.

El catálogo curricular tendrá su propio esquema relacional más adelante. Por
ahora cada guía se guarda como un documento JSON normalizado (compatible con
``docx_builder``) y la base de datos aporta identidad, orden y marcas de tiempo.
"""

import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import config

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS guides (
    id TEXT PRIMARY KEY,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_guides_updated_at ON guides (updated_at DESC);
"""

_INITIALIZED = set()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def database_path():
    return Path(config.GUIDES_DB)


def _connect():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = str(path)
    if key not in _INITIALIZED:
        connection = sqlite3.connect(path)
        try:
            connection.executescript(SCHEMA)
            connection.commit()
        finally:
            connection.close()
        _INITIALIZED.add(key)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def _db():
    connection = _connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def valid_id(guide_id):
    return bool(_ID_RE.fullmatch(str(guide_id or "")))


def init_db():
    with _db():
        pass


def _serialize(guide):
    return json.dumps(guide, ensure_ascii=False, separators=(",", ":"))


def create_guide(guide):
    guide_id = uuid.uuid4().hex
    now = _now()
    with _db() as connection:
        connection.execute(
            "INSERT INTO guides (id, data_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (guide_id, _serialize(guide), now, now),
        )
    return guide_id


def save_guide(guide_id, guide):
    if not valid_id(guide_id):
        raise ValueError("Identificador de guía inválido.")
    now = _now()
    with _db() as connection:
        cursor = connection.execute(
            "UPDATE guides SET data_json = ?, updated_at = ? WHERE id = ?",
            (_serialize(guide), now, guide_id),
        )
        if cursor.rowcount == 0:
            connection.execute(
                "INSERT INTO guides (id, data_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (guide_id, _serialize(guide), now, now),
            )
    return guide_id


def get_guide(guide_id):
    if not valid_id(guide_id):
        return None
    with _db() as connection:
        row = connection.execute(
            "SELECT data_json FROM guides WHERE id = ?", (guide_id,)
        ).fetchone()
    if row is None:
        return None
    try:
        return json.loads(row["data_json"])
    except (json.JSONDecodeError, TypeError):
        return None


def delete_guide(guide_id):
    if not valid_id(guide_id):
        return False
    with _db() as connection:
        cursor = connection.execute("DELETE FROM guides WHERE id = ?", (guide_id,))
    return cursor.rowcount > 0


def list_guides():
    with _db() as connection:
        rows = connection.execute(
            "SELECT id, data_json, created_at, updated_at FROM guides "
            "ORDER BY updated_at DESC"
        ).fetchall()
    guides = []
    for row in rows:
        try:
            data = json.loads(row["data_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        guides.append(
            {
                "id": row["id"],
                "guide": data,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    return guides
