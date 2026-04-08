"""Prompt preparation and response parsing for CV alignment analysis."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..prompts.loader import PromptLoader, get_prompt_loader


class CVAlignment:
    """Prepare ANALYZE_ALIGNMENT prompts for the agent and parse the reply."""

    def __init__(self, prompt_loader: Optional[PromptLoader] = None):
        self.prompt_loader = prompt_loader or get_prompt_loader()

    def prepare_prompt(self, parsed_job: Dict[str, Any], cv_latex: str) -> Dict[str, str]:
        """Build the prompt package for CV alignment analysis."""
        if not parsed_job:
            raise ValueError("parsed_job is required")
        if not cv_latex or not cv_latex.strip():
            raise ValueError("cv_latex is required")
        return {
            "system": self.prompt_loader.ANALYZE_ALIGNMENT_SYSTEM,
            "user": self.prompt_loader.ANALYZE_ALIGNMENT_USER(parsed_job, cv_latex),
        }

    def parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse and normalize the agent's JSON response."""
        if not response_text or not response_text.strip():
            return self._empty_result("Empty response")

        try:
            analysis = json.loads(self._strip_code_fences(response_text))
        except json.JSONDecodeError as exc:
            return self._empty_result(f"JSON parse error: {exc}")

        analysis.setdefault("overall_score", 0)
        analysis.setdefault("overall_verdict", "")
        analysis.setdefault("sections", [])
        analysis.setdefault("missing_from_cv", [])
        analysis.setdefault("strongest_matches", [])
        analysis.setdefault("recommended_emphasis", [])
        analysis.setdefault("priority_gaps", analysis.get("missing_from_cv", []))
        analysis.setdefault("evidence_candidates", analysis.get("strongest_matches", []))
        return analysis

    def batch_prepare(self, parsed_jobs: List[Dict[str, Any]], cv_latex: str) -> List[Dict[str, str]]:
        """Build prompt packages for multiple parsed jobs."""
        return [self.prepare_prompt(job, cv_latex) for job in parsed_jobs]

    @staticmethod
    def _empty_result(error: str) -> Dict[str, Any]:
        return {
            "overall_score": 0,
            "overall_verdict": "",
            "sections": [],
            "missing_from_cv": [],
            "strongest_matches": [],
            "recommended_emphasis": [],
            "priority_gaps": [],
            "evidence_candidates": [],
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


def get_alignment_analyzer() -> CVAlignment:
    """Return the default alignment helper."""
    return CVAlignment()
