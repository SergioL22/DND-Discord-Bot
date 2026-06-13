import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = "data/dnd.db"

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def get_connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        with _lock:
            if _conn is None:
                Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
                _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
                _conn.row_factory = sqlite3.Row
                _init_tables(_conn)
    return _conn


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS characters (
            owner_id  TEXT NOT NULL,
            name_key  TEXT NOT NULL,
            data      TEXT NOT NULL,
            PRIMARY KEY (owner_id, name_key)
        );
        CREATE TABLE IF NOT EXISTS ai_dm_sessions (
            channel_id   TEXT PRIMARY KEY,
            session_data TEXT NOT NULL,
            updated_at   INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS campaign_saves (
            guild_id     TEXT NOT NULL,
            name_key     TEXT NOT NULL,
            name         TEXT NOT NULL,
            saved_by     TEXT NOT NULL,
            saved_at     INTEGER NOT NULL,
            session_data TEXT NOT NULL,
            PRIMARY KEY (guild_id, name_key)
        );
        CREATE TABLE IF NOT EXISTS party_members (
            guild_id   TEXT NOT NULL,
            owner_id   TEXT NOT NULL,
            name_key   TEXT NOT NULL,
            PRIMARY KEY (guild_id, owner_id, name_key)
        );
        CREATE TABLE IF NOT EXISTS combat_encounters (
            channel_id TEXT PRIMARY KEY,
            data       TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        );
    """)
    conn.commit()
    _migrate_json(conn)


# ── One-time JSON migration ──────────────────────────────────────────────────

def _migrate_json(conn: sqlite3.Connection) -> None:
    _migrate_characters(conn)
    _migrate_sessions(conn)
    _migrate_campaigns(conn)


def _migrate_characters(conn: sqlite3.Connection) -> None:
    legacy = Path("data/characters.json")
    if not legacy.exists():
        return
    if conn.execute("SELECT COUNT(*) FROM characters").fetchone()[0] > 0:
        return
    try:
        data = json.loads(legacy.read_text(encoding="utf-8"))
        for key, char_data in data.items():
            if ":" in key:
                owner_id, name_key = key.split(":", 1)
            else:
                owner_id = str(char_data.get("owner_id", ""))
                name_key = key
            conn.execute(
                "INSERT OR IGNORE INTO characters (owner_id, name_key, data) VALUES (?, ?, ?)",
                (owner_id, name_key.lower().strip(), json.dumps(char_data)),
            )
        conn.commit()
        logger.info("Migrated %d character(s) from JSON to SQLite.", len(data))
    except Exception as e:
        logger.warning("Could not migrate characters.json: %s", e)


def _migrate_sessions(conn: sqlite3.Connection) -> None:
    legacy = Path("data/ai_dm_sessions.json")
    if not legacy.exists():
        return
    if conn.execute("SELECT COUNT(*) FROM ai_dm_sessions").fetchone()[0] > 0:
        return
    try:
        data = json.loads(legacy.read_text(encoding="utf-8"))
        for channel_id, session in data.items():
            conn.execute(
                "INSERT OR IGNORE INTO ai_dm_sessions (channel_id, session_data, updated_at) VALUES (?, ?, ?)",
                (channel_id, json.dumps(session, ensure_ascii=False), int(time.time())),
            )
        conn.commit()
        logger.info("Migrated %d AI DM session(s) from JSON to SQLite.", len(data))
    except Exception as e:
        logger.warning("Could not migrate ai_dm_sessions.json: %s", e)


def _migrate_campaigns(conn: sqlite3.Connection) -> None:
    legacy = Path("data/campaigns.json")
    if not legacy.exists():
        return
    if conn.execute("SELECT COUNT(*) FROM campaign_saves").fetchone()[0] > 0:
        return
    try:
        data = json.loads(legacy.read_text(encoding="utf-8"))
        for save in data.values():
            guild_id = str(save.get("guild_id", ""))
            name = save.get("name", "")
            conn.execute(
                """INSERT OR IGNORE INTO campaign_saves
                   (guild_id, name_key, name, saved_by, saved_at, session_data)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (guild_id, name.strip().lower(), name.strip(),
                 str(save.get("saved_by", "")), int(save.get("saved_at", time.time())),
                 json.dumps(save.get("session", {}), ensure_ascii=False)),
            )
        conn.commit()
        logger.info("Migrated %d campaign save(s) from JSON to SQLite.", len(data))
    except Exception as e:
        logger.warning("Could not migrate campaigns.json: %s", e)


# ── AI DM Sessions ───────────────────────────────────────────────────────────

def session_get(channel_id: int) -> Optional[Dict[str, Any]]:
    row = get_connection().execute(
        "SELECT session_data FROM ai_dm_sessions WHERE channel_id = ?",
        (str(channel_id),),
    ).fetchone()
    return json.loads(row["session_data"]) if row else None


def session_save(channel_id: int, session: Dict[str, Any]) -> None:
    now = int(time.time())
    session["updated_at"] = now
    with _lock:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO ai_dm_sessions (channel_id, session_data, updated_at) VALUES (?, ?, ?)",
            (str(channel_id), json.dumps(session, ensure_ascii=False), now),
        )
        conn.commit()


def session_delete(channel_id: int) -> bool:
    with _lock:
        conn = get_connection()
        cursor = conn.execute(
            "DELETE FROM ai_dm_sessions WHERE channel_id = ?", (str(channel_id),)
        )
        conn.commit()
    return cursor.rowcount > 0


# ── Campaign Saves ───────────────────────────────────────────────────────────

def campaign_save(guild_id: int, name: str, saved_by: str, session: Dict[str, Any]) -> None:
    with _lock:
        conn = get_connection()
        conn.execute(
            """INSERT OR REPLACE INTO campaign_saves
               (guild_id, name_key, name, saved_by, saved_at, session_data)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(guild_id), name.strip().lower(), name.strip(), str(saved_by),
             int(time.time()), json.dumps(session, ensure_ascii=False)),
        )
        conn.commit()


def campaign_get(guild_id: int, name: str) -> Optional[Dict[str, Any]]:
    row = get_connection().execute(
        "SELECT name, saved_by, saved_at, session_data FROM campaign_saves WHERE guild_id = ? AND name_key = ?",
        (str(guild_id), name.strip().lower()),
    ).fetchone()
    if row is None:
        return None
    return {
        "name": row["name"],
        "guild_id": str(guild_id),
        "saved_by": row["saved_by"],
        "saved_at": row["saved_at"],
        "session": json.loads(row["session_data"]),
    }


def campaign_list(guild_id: int) -> List[Dict[str, Any]]:
    rows = get_connection().execute(
        "SELECT name, saved_by, saved_at, session_data FROM campaign_saves WHERE guild_id = ? ORDER BY saved_at DESC",
        (str(guild_id),),
    ).fetchall()
    return [
        {
            "name": r["name"],
            "guild_id": str(guild_id),
            "saved_by": r["saved_by"],
            "saved_at": r["saved_at"],
            "session": json.loads(r["session_data"]),
        }
        for r in rows
    ]


def campaign_delete(guild_id: int, name: str) -> bool:
    with _lock:
        conn = get_connection()
        cursor = conn.execute(
            "DELETE FROM campaign_saves WHERE guild_id = ? AND name_key = ?",
            (str(guild_id), name.strip().lower()),
        )
        conn.commit()
    return cursor.rowcount > 0


def campaign_names(guild_id: int) -> List[str]:
    rows = get_connection().execute(
        "SELECT name FROM campaign_saves WHERE guild_id = ? ORDER BY name_key",
        (str(guild_id),),
    ).fetchall()
    return [r["name"] for r in rows]


# ── Party Members ────────────────────────────────────────────────────────────

def party_add(guild_id: int, owner_id: str, character_name: str) -> bool:
    """Add a character to the guild party. Returns False if already in party."""
    name_key = character_name.lower().strip()
    with _lock:
        conn = get_connection()
        existing = conn.execute(
            "SELECT 1 FROM party_members WHERE guild_id = ? AND owner_id = ? AND name_key = ?",
            (str(guild_id), str(owner_id), name_key),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            "INSERT INTO party_members (guild_id, owner_id, name_key) VALUES (?, ?, ?)",
            (str(guild_id), str(owner_id), name_key),
        )
        conn.commit()
    return True


def party_remove(guild_id: int, owner_id: str, character_name: str) -> bool:
    name_key = character_name.lower().strip()
    with _lock:
        conn = get_connection()
        cursor = conn.execute(
            "DELETE FROM party_members WHERE guild_id = ? AND owner_id = ? AND name_key = ?",
            (str(guild_id), str(owner_id), name_key),
        )
        conn.commit()
    return cursor.rowcount > 0


def party_list(guild_id: int) -> List[Dict[str, str]]:
    """Return list of {owner_id, name_key} dicts for the guild party."""
    rows = get_connection().execute(
        "SELECT owner_id, name_key FROM party_members WHERE guild_id = ? ORDER BY owner_id, name_key",
        (str(guild_id),),
    ).fetchall()
    return [{"owner_id": r["owner_id"], "name_key": r["name_key"]} for r in rows]


def party_clear(guild_id: int) -> int:
    with _lock:
        conn = get_connection()
        cursor = conn.execute("DELETE FROM party_members WHERE guild_id = ?", (str(guild_id),))
        conn.commit()
    return cursor.rowcount


# ── Combat Encounters ────────────────────────────────────────────────────────

def encounter_save(channel_id: int, data: Dict[str, Any]) -> None:
    now = int(time.time())
    with _lock:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO combat_encounters (channel_id, data, updated_at) VALUES (?, ?, ?)",
            (str(channel_id), json.dumps(data), now),
        )
        conn.commit()


def encounter_get(channel_id: int) -> Optional[Dict[str, Any]]:
    row = get_connection().execute(
        "SELECT data FROM combat_encounters WHERE channel_id = ?",
        (str(channel_id),),
    ).fetchone()
    return json.loads(row["data"]) if row else None


def encounter_delete(channel_id: int) -> bool:
    with _lock:
        conn = get_connection()
        cursor = conn.execute(
            "DELETE FROM combat_encounters WHERE channel_id = ?", (str(channel_id),)
        )
        conn.commit()
    return cursor.rowcount > 0
