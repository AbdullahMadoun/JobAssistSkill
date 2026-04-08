"""Prompt preparation and deterministic application of CV edits."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from ..prompts.loader import PromptLoader, get_prompt_loader


class CVReplacer:
    """Prepare REPLACE prompts for the agent and apply the resulting edits."""

    def __init__(self, prompt_loader: Optional[PromptLoader] = None):
        self.prompt_loader = prompt_loader or get_prompt_loader()

    def prepare_prompt(
        self,
        cv_latex: str,
        alignment: Dict[str, Any],
        stories: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """Build the replace prompt package."""
        if not cv_latex or not cv_latex.strip():
            raise ValueError("cv_latex is required")
        if not alignment:
            raise ValueError("alignment is required")
        prompt_options = dict(options or {})
        if not prompt_options.get("inventory"):
            prompt_options["inventory"] = self._build_inventory(cv_latex)
        if "totalItemCount" not in prompt_options:
            prompt_options["totalItemCount"] = len(prompt_options.get("inventory", []))
        if "targetItemEditCount" not in prompt_options:
            prompt_options["targetItemEditCount"] = max(1, int(prompt_options["totalItemCount"] * 0.35)) if prompt_options["totalItemCount"] else 0
        if "rewriteCoverage" not in prompt_options and prompt_options["totalItemCount"]:
            prompt_options["rewriteCoverage"] = round(prompt_options["targetItemEditCount"] / prompt_options["totalItemCount"], 2)
        return {
            "system": self.prompt_loader.REPLACE_SYSTEM,
            "user": self.prompt_loader.build_replace_user(
                latex=cv_latex,
                alignment=alignment,
                stories=stories or [],
                options=prompt_options,
            ),
        }

    def parse_response(self, response_text: str) -> List[Dict[str, Any]]:
        """Parse the agent's JSON response into normalized replacement items."""
        if not response_text or not response_text.strip():
            return []

        try:
            parsed = json.loads(self._strip_code_fences(response_text))
        except json.JSONDecodeError:
            return []

        if isinstance(parsed, dict):
            if "changes" in parsed:
                parsed = parsed["changes"]
            elif "items" in parsed:
                parsed = parsed["items"]
            else:
                parsed = [parsed]

        changes: List[Dict[str, Any]] = []
        for change in parsed:
            if not isinstance(change, dict):
                continue
            normalized = {
                "original_text": change.get("original_text", ""),
                "edited_text": change.get("edited_text", ""),
                "change_type": change.get("change_type", "edit"),
                "reason": change.get("reason", ""),
                "keywords_added": change.get("keywords_added", []),
                "keyword_impact_score": change.get("keyword_impact_score", 0.5),
            }
            if normalized["change_type"] == "keep" or (
                normalized["original_text"] and normalized["edited_text"]
            ):
                changes.append(normalized)
        return changes

    def apply_changes(self, cv_latex: str, changes: List[Dict[str, Any]]) -> str:
        """Apply exact-substring replacements to the CV."""
        if not changes:
            return cv_latex

        result = cv_latex
        ordered: List[tuple[int, Dict[str, Any]]] = []
        for change in changes:
            original = change.get("original_text", "")
            if not original:
                continue
            position = result.find(original)
            if position >= 0:
                ordered.append((position, change))

        ordered.sort(key=lambda item: item[0], reverse=True)
        for _, change in ordered:
            if change.get("change_type") == "keep":
                continue
            original = change.get("original_text", "")
            edited = change.get("edited_text", "")
            if original and edited and original in result:
                result = result.replace(original, edited, 1)
        return result

    def _build_inventory(self, cv_latex: str) -> List[Dict[str, Any]]:
        inventory: List[Dict[str, Any]] = []
        for line_number, line in enumerate(cv_latex.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(r"\item"):
                inventory.append(
                    {
                        "line_number": line_number,
                        "original_text": stripped,
                        "rewrite_goal": "Strengthen relevance, specificity, and truthful impact.",
                    }
                )
        return inventory

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


def get_cv_replacer() -> CVReplacer:
    """Return the default replacer helper."""
    return CVReplacer()
