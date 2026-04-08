"""Prompt preparation and response parsing for agent-written cover letters."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from ..prompts.loader import PromptLoader, get_prompt_loader


class CoverLetterGenerator:
    """Prepare COVER_LETTER prompts for the agent and parse the reply."""

    def __init__(self, prompt_loader: Optional[PromptLoader] = None):
        self.prompt_loader = prompt_loader or get_prompt_loader()

    def prepare_prompt(
        self,
        parsed_job: Dict[str, Any],
        cv_latex: str,
        alignment: Optional[Dict[str, Any]] = None,
        job: Optional[Dict[str, Any]] = None,
        user_story: str = "",
        template: str = "",
    ) -> Dict[str, str]:
        """Build the prompt package for a tailored cover letter."""
        if not parsed_job:
            raise ValueError("parsed_job is required")
        if not cv_latex or not cv_latex.strip():
            raise ValueError("cv_latex is required")
        return {
            "system": self.prompt_loader.COVER_LETTER_SYSTEM,
            "user": self.prompt_loader.build_cover_letter_user(
                parsed_req=parsed_job,
                latex=cv_latex,
                alignment=alignment or {},
                job=job,
                user_story=user_story,
                template=template,
            ),
        }

    def parse_response(self, response_text: str) -> str:
        """Extract the usable body text from the agent's response."""
        if not response_text or not response_text.strip():
            return ""

        cleaned = self._strip_code_fences(response_text)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            return cleaned

        if isinstance(payload, dict):
            if "body_latex" in payload and payload["body_latex"]:
                body = payload["body_latex"]
                if isinstance(body, list):
                    return "\n\n".join(str(item) for item in body if item)
                return str(body)
            for key in ("body", "content", "cover_letter"):
                if key in payload and payload[key]:
                    return str(payload[key])
        return cleaned

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


def get_cover_letter_generator() -> CoverLetterGenerator:
    """Return the default cover-letter helper."""
    return CoverLetterGenerator()
