"""
Async client for the D&D 5e API (dnd5eapi.co).
No API key required. Responses are cached in memory for the lifetime of the process.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, request

logger = logging.getLogger(__name__)

BASE_URL = "https://www.dnd5eapi.co/api"

_cache: Dict[str, Any] = {}
_lists: Dict[str, List[Dict]] = {}


def to_index(name: str) -> str:
    """Convert a display name to a dnd5eapi index slug."""
    return name.lower().strip().replace(" ", "-").replace("'", "").replace(",", "").replace("/", "-")


def modifier(score: int) -> str:
    """Return a formatted ability modifier string like +3 or -1."""
    mod = (score - 10) // 2
    return f"+{mod}" if mod >= 0 else str(mod)


# ── Core fetch ────────────────────────────────────────────────────────────────

def _fetch_sync(path: str) -> Dict[str, Any]:
    if path in _cache:
        return _cache[path]

    url = f"{BASE_URL}/{path.lstrip('/')}"
    req = request.Request(url, headers={"Accept": "application/json"})
    try:
        with request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as e:
        if e.code == 404:
            _cache[path] = {}
            return {}
        raise RuntimeError(f"D&D 5e API error {e.code} — {path}") from e
    except Exception as e:
        raise RuntimeError(f"D&D 5e API request failed: {e}") from e

    _cache[path] = data
    return data


async def fetch(path: str) -> Dict[str, Any]:
    return await asyncio.to_thread(_fetch_sync, path)


# ── List / search ─────────────────────────────────────────────────────────────

async def _get_list(endpoint: str) -> List[Dict]:
    if endpoint in _lists:
        return _lists[endpoint]
    data = await fetch(endpoint)
    results = data.get("results", [])
    _lists[endpoint] = results
    return results


async def search(endpoint: str, query: str) -> List[Tuple[str, str]]:
    """Return (name, index) tuples from endpoint whose name contains query."""
    items = await _get_list(endpoint)
    q = query.lower()
    return [(item["name"], item["index"]) for item in items if q in item["name"].lower()][:25]


# ── Resource getters ──────────────────────────────────────────────────────────

async def get_monster(index: str) -> Optional[Dict[str, Any]]:
    data = await fetch(f"monsters/{index}")
    return data if data else None


async def get_spell(index: str) -> Optional[Dict[str, Any]]:
    data = await fetch(f"spells/{index}")
    return data if data else None


async def get_equipment(index: str) -> Optional[Dict[str, Any]]:
    data = await fetch(f"equipment/{index}")
    return data if data else None


async def get_race(name: str) -> Optional[Dict[str, Any]]:
    data = await fetch(f"races/{to_index(name)}")
    return data if data else None


async def get_class(name: str) -> Optional[Dict[str, Any]]:
    data = await fetch(f"classes/{to_index(name)}")
    return data if data else None


async def get_class_level(class_name: str, level: int) -> Optional[Dict[str, Any]]:
    """Return level-specific class data including spell slots if applicable."""
    data = await fetch(f"classes/{to_index(class_name)}/levels/{level}")
    return data if data else None
