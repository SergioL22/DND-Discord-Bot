import json
import logging
from typing import Dict, List, Optional

from utils.character_sheet import CharacterSheet
from utils.db import _lock, get_connection

logger = logging.getLogger(__name__)


class CharacterDatabase:
    """Character persistence backed by SQLite. Public API is unchanged."""

    def __init__(self, file_path: str = "data/characters.json"):
        # file_path kept for API compatibility with existing callers
        self._conn = get_connection()

    def _key(self, owner_id: str, name: str) -> tuple:
        return str(owner_id), name.lower().strip()

    def save_character(self, character: CharacterSheet) -> None:
        owner_id, name_key = self._key(character.owner_id, character.name)
        with _lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO characters (owner_id, name_key, data) VALUES (?, ?, ?)",
                (owner_id, name_key, json.dumps(character.to_dict())),
            )
            self._conn.commit()

    def get_character(self, owner_id: str, character_name: str) -> Optional[CharacterSheet]:
        owner_id, name_key = self._key(owner_id, character_name)
        row = self._conn.execute(
            "SELECT data FROM characters WHERE owner_id = ? AND name_key = ?",
            (owner_id, name_key),
        ).fetchone()
        if row is None:
            return None
        return CharacterSheet.from_dict(json.loads(row["data"]))

    def get_all_characters(self, owner_id: str) -> List[CharacterSheet]:
        rows = self._conn.execute(
            "SELECT data FROM characters WHERE owner_id = ? ORDER BY name_key",
            (str(owner_id),),
        ).fetchall()
        chars = []
        for row in rows:
            try:
                chars.append(CharacterSheet.from_dict(json.loads(row["data"])))
            except Exception as e:
                logger.warning("Failed to load character: %s", e)
        return chars

    def delete_character(self, owner_id: str, character_name: str) -> bool:
        owner_id, name_key = self._key(owner_id, character_name)
        with _lock:
            cursor = self._conn.execute(
                "DELETE FROM characters WHERE owner_id = ? AND name_key = ?",
                (owner_id, name_key),
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def character_exists(self, owner_id: str, character_name: str) -> bool:
        owner_id, name_key = self._key(owner_id, character_name)
        return self._conn.execute(
            "SELECT 1 FROM characters WHERE owner_id = ? AND name_key = ?",
            (owner_id, name_key),
        ).fetchone() is not None

    def get_all_character_names(self, owner_id: str) -> List[str]:
        return [c.name for c in self.get_all_characters(owner_id)]

    def update_character(self, character: CharacterSheet) -> bool:
        if not self.character_exists(character.owner_id, character.name):
            return False
        self.save_character(character)
        return True

    def count_characters(self, owner_id: str) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM characters WHERE owner_id = ?",
            (str(owner_id),),
        ).fetchone()[0]

    def get_all_data(self) -> Dict[str, Dict]:
        rows = self._conn.execute(
            "SELECT owner_id, name_key, data FROM characters"
        ).fetchall()
        return {
            f"{r['owner_id']}:{r['name_key']}": json.loads(r["data"])
            for r in rows
        }

    def backup(self, backup_path: str) -> None:
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(self.get_all_data(), f, indent=2, ensure_ascii=False)


_db_instance: Optional[CharacterDatabase] = None


def get_database(file_path: str = "data/characters.json") -> CharacterDatabase:
    global _db_instance
    if _db_instance is None:
        _db_instance = CharacterDatabase(file_path)
    return _db_instance
