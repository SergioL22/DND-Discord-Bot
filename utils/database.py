"""
Database utility for managing character data persistence
Handles loading, saving, and querying character sheets from JSON storage
"""
import json
import os
from typing import Dict, List, Optional
from pathlib import Path
from utils.character_sheet import CharacterSheet


class CharacterDatabase:
    """Manages character data persistence using JSON file storage"""
    
    def __init__(self, file_path: str = "data/characters.json"):
        self.file_path = file_path
        self._ensure_file_exists()
    
    def _ensure_file_exists(self) -> None:
        """Create the data directory and file if they don't exist"""
        path = Path(self.file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if not path.exists():
            path.write_text('{}')
    
    def _load_data(self) -> Dict[str, Dict]:
        """Load all character data from JSON file"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _save_data(self, data: Dict[str, Dict]) -> None:
        """Save all character data to JSON file"""
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _generate_key(self, owner_id: str, character_name: str) -> str:
        """Generate a unique key for a character"""
        return f"{owner_id}:{character_name.lower().strip()}"
    
    def save_character(self, character: CharacterSheet) -> None:
        """Save a character to the database"""
        data = self._load_data()
        key = self._generate_key(character.owner_id, character.name)
        data[key] = character.to_dict()
        self._save_data(data)
    
    def get_character(self, owner_id: str, character_name: str) -> Optional[CharacterSheet]:
        """Retrieve a specific character by owner and name"""
        data = self._load_data()
        key = self._generate_key(owner_id, character_name)
        
        if key not in data:
            return None
        
        return CharacterSheet.from_dict(data[key])
    
    def get_all_characters(self, owner_id: str) -> List[CharacterSheet]:
        """Get all characters owned by a specific user"""
        data = self._load_data()
        characters = []
        
        for key, char_data in data.items():
            if char_data.get('owner_id') == str(owner_id):
                try:
                    characters.append(CharacterSheet.from_dict(char_data))
                except Exception as e:
                    print(f"Warning: Failed to load character {key}: {e}")
        
        return sorted(characters, key=lambda c: c.name.lower())
    
    def delete_character(self, owner_id: str, character_name: str) -> bool:
        """Delete a character from the database. Returns True if deleted, False if not found."""
        data = self._load_data()
        key = self._generate_key(owner_id, character_name)
        
        if key in data:
            del data[key]
            self._save_data(data)
            return True
        return False
    
    def character_exists(self, owner_id: str, character_name: str) -> bool:
        """Check if a character exists"""
        data = self._load_data()
        key = self._generate_key(owner_id, character_name)
        return key in data
    
    def get_all_character_names(self, owner_id: str) -> List[str]:
        """Get just the names of all characters owned by a user"""
        characters = self.get_all_characters(owner_id)
        return [char.name for char in characters]
    
    def update_character(self, character: CharacterSheet) -> bool:
        """Update an existing character. Returns True if updated, False if not found."""
        if not self.character_exists(character.owner_id, character.name):
            return False
        self.save_character(character)
        return True
    
    def count_characters(self, owner_id: str) -> int:
        """Count how many characters a user has"""
        return len(self.get_all_characters(owner_id))
    
    def get_all_data(self) -> Dict[str, Dict]:
        """Get raw data dictionary (for debugging/admin)"""
        return self._load_data()
    
    def backup(self, backup_path: str) -> None:
        """Create a backup copy of the database"""
        data = self._load_data()
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# Global database instance
_db_instance: Optional[CharacterDatabase] = None


def get_database(file_path: str = "data/characters.json") -> CharacterDatabase:
    """Get the global database instance (singleton pattern)"""
    global _db_instance
    if _db_instance is None:
        _db_instance = CharacterDatabase(file_path)
    return _db_instance