"""Persistent user preference memory for agent-driven workflows."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


DEFAULT_MEMORY: Dict[str, Any] = {
    "profile": {
        "name": "",
        "email": "",
        "phone": "",
        "location": "",
        "headline": "",
    },
    "files": {
        "cv_path": "cv_template.tex",
        "linkedin_session": "linkedin_session.json",
    },
    "search": {
        "stream": "both",
        "limit": 10,
        "max_hours_age": 24,
        "roles": [],
        "locations": [],
        "companies": [],
    },
    "preferences": {
        "target_roles": [],
        "preferred_locations": [],
        "avoided_locations": [],
        "preferred_companies": [],
        "avoided_companies": [],
        "skills": [],
        "notes": [],
    },
    "application": {
        "sender_name": "",
        "sender_email": "",
        "signature": "",
        "default_summary": "",
    },
}


class PreferenceMemory:
    """JSON-backed memory store for user profile and workflow preferences."""

    def __init__(self, path: Optional[str] = None):
        default_path = _repo_root() / ".job_assist" / "preferences.json"
        self.path = Path(path) if path else default_path
        self.data: Dict[str, Any] = deepcopy(DEFAULT_MEMORY)
        self.load()

    def load(self) -> Dict[str, Any]:
        """Load memory from disk, creating defaults when absent."""
        if self.path.exists():
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            self.data = self._merge_dicts(deepcopy(DEFAULT_MEMORY), loaded)
        else:
            self.save()
        return self.data

    def save(self) -> Path:
        """Persist memory to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return self.path

    def to_dict(self) -> Dict[str, Any]:
        """Return a safe copy of the memory payload."""
        return deepcopy(self.data)

    def update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Deep-merge a payload into the memory store and save it."""
        self.data = self._merge_dicts(self.data, payload)
        self.save()
        return self.to_dict()

    def set_value(self, dotted_key: str, value: Any) -> None:
        """Set a nested value using dotted notation, then save it."""
        parts = dotted_key.split(".")
        cursor = self.data
        for part in parts[:-1]:
            next_value = cursor.get(part)
            if not isinstance(next_value, dict):
                cursor[part] = {}
            cursor = cursor[part]
        cursor[parts[-1]] = value
        self.save()

    def get_value(self, dotted_key: str, default: Any = None) -> Any:
        """Read a nested value using dotted notation."""
        cursor: Any = self.data
        for part in dotted_key.split("."):
            if not isinstance(cursor, dict) or part not in cursor:
                return default
            cursor = cursor[part]
        return cursor

    def remember_search(
        self,
        *,
        roles: Optional[list[str]] = None,
        locations: Optional[list[str]] = None,
        companies: Optional[list[str]] = None,
        stream: Optional[str] = None,
        limit: Optional[int] = None,
        max_hours_age: Optional[int] = None,
    ) -> None:
        """Persist the latest search choices for future runs."""
        payload: Dict[str, Any] = {"search": {}}
        if roles is not None:
            payload["search"]["roles"] = roles
        if locations is not None:
            payload["search"]["locations"] = locations
        if companies is not None:
            payload["search"]["companies"] = companies
        if stream is not None:
            payload["search"]["stream"] = stream
        if limit is not None:
            payload["search"]["limit"] = limit
        if max_hours_age is not None:
            payload["search"]["max_hours_age"] = max_hours_age
        self.update(payload)

    def remember_profile(
        self,
        *,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        location: Optional[str] = None,
        headline: Optional[str] = None,
    ) -> None:
        """Persist explicit user profile fields."""
        payload: Dict[str, Any] = {"profile": {}}
        if name is not None:
            payload["profile"]["name"] = name
            payload.setdefault("application", {})["sender_name"] = name
        if email is not None:
            payload["profile"]["email"] = email
            payload.setdefault("application", {})["sender_email"] = email
        if phone is not None:
            payload["profile"]["phone"] = phone
        if location is not None:
            payload["profile"]["location"] = location
        if headline is not None:
            payload["profile"]["headline"] = headline
        self.update(payload)

    def remember_files(
        self,
        *,
        cv_path: Optional[str] = None,
        linkedin_session: Optional[str] = None,
    ) -> None:
        """Persist frequently used file paths."""
        payload: Dict[str, Any] = {"files": {}}
        if cv_path is not None:
            payload["files"]["cv_path"] = cv_path
        if linkedin_session is not None:
            payload["files"]["linkedin_session"] = linkedin_session
        self.update(payload)

    @staticmethod
    def _merge_dicts(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in incoming.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key] = PreferenceMemory._merge_dicts(base[key], value)
            else:
                base[key] = value
        return base
