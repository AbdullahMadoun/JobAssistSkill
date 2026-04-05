"""User preferences with silent learning for Career Assistant."""

import json
import os
from pathlib import Path
from typing import Optional


class Preferences:
    """Stores user preferences with silent auto-save on updates."""
    
    def __init__(
        self,
        cv_path: str = "",
        name: str = "",
        email: str = "",
        preferred_locations: list = None,
        avoided_locations: list = None,
        preferred_skills: list = None,
        avoided_companies: list = None,
        config_path: str = None,
    ):
        self.cv_path = cv_path
        self.name = name
        self.email = email
        self.preferred_locations = preferred_locations or []
        self.avoided_locations = avoided_locations or []
        self.preferred_skills = preferred_skills or []
        self.avoided_companies = avoided_companies or []
        self._config_path = config_path or os.path.join(
            os.path.dirname(__file__), "preferences.json"
        )
    
    def load(self) -> "Preferences":
        """Load preferences from JSON file."""
        path = Path(self._config_path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.__dict__.update(data)
        return self
    
    def save(self) -> None:
        """Save preferences to JSON file."""
        path = Path(self._config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, indent=2)
    
    def update_from_decision(self, decision: dict) -> None:
        """Update preferences from a user decision (silent auto-save)."""
        if "preferred_locations" in decision:
            self.preferred_locations = decision["preferred_locations"]
        if "avoided_locations" in decision:
            self.avoided_locations = decision["avoided_locations"]
        if "preferred_skills" in decision:
            self.preferred_skills = decision["preferred_skills"]
        if "avoided_companies" in decision:
            self.avoided_companies = decision["avoided_companies"]
        self.save()  # Silent auto-save
    
    def get_search_preferences(self) -> dict:
        """Return dict for filtering job searches."""
        return {
            "preferred_locations": self.preferred_locations,
            "avoided_locations": self.avoided_locations,
            "preferred_skills": self.preferred_skills,
            "avoided_companies": self.avoided_companies,
        }
