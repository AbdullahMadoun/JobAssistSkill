"""Prompt preparation and response parsing for job requirement extraction."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from ..prompts.loader import PromptLoader, get_prompt_loader


class JobParser:
    """Prepare PARSE_JOB prompts for the agent and parse its JSON reply."""

    def __init__(self, prompt_loader: Optional[PromptLoader] = None):
        self.prompt_loader = prompt_loader or get_prompt_loader()

    def prepare_prompt(self, job_text: str) -> Dict[str, str]:
        """Build the system and user prompt package for job parsing."""
        if not job_text or not job_text.strip():
            raise ValueError("job_text is required")
        return {
            "system": self.prompt_loader.PARSE_JOB_SYSTEM,
            "user": self.prompt_loader.PARSE_JOB_USER(job_text),
        }

    def parse_response(self, response_text: str, job_text: str = "") -> Dict[str, Any]:
        """Parse the agent's JSON response into a normalized schema."""
        if not response_text or not response_text.strip():
            return self._empty_result("Empty response")

        try:
            parsed = json.loads(self._strip_code_fences(response_text))
        except json.JSONDecodeError as exc:
            return self._empty_result(f"JSON parse error: {exc}")

        parsed.setdefault("company", "")
        parsed.setdefault("title", "")
        parsed.setdefault("seniority", "unknown")
        parsed.setdefault("required_skills", [])
        parsed.setdefault("preferred_skills", [])
        parsed.setdefault("responsibilities", [])
        parsed.setdefault("industry_keywords", [])
        parsed.setdefault("soft_skills", [])
        parsed.setdefault("education", "")
        parsed.setdefault("experience_years", "")
        parsed.setdefault(
            "keyword_taxonomy",
            {
                "hard_skills": [],
                "tools": [],
                "certifications": [],
                "domain_knowledge": [],
            },
        )
        parsed["raw_text"] = job_text[:5000] if job_text else parsed.get("raw_text", "")
        return parsed

    def _empty_result(self, error: str) -> Dict[str, Any]:
        return {
            "company": "",
            "title": "",
            "seniority": "unknown",
            "required_skills": [],
            "preferred_skills": [],
            "responsibilities": [],
            "industry_keywords": [],
            "soft_skills": [],
            "education": "",
            "experience_years": "",
            "keyword_taxonomy": {
                "hard_skills": [],
                "tools": [],
                "certifications": [],
                "domain_knowledge": [],
            },
            "raw_text": "",
            "error": error,
        }

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()


def get_job_parser() -> JobParser:
    """Return the default job parser helper."""
    return JobParser()
