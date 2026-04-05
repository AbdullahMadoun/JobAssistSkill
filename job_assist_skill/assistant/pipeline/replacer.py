"""
CV Replacer - Generates and applies targeted changes to CV.

Uses the REPLACE prompt to generate critical changes that improve
CV alignment with job requirements. Only makes critical changes
to avoid over-tailoring.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from ..prompts.loader import PromptLoader, get_prompt_loader
from .llm_client import LLMClient, get_llm_client

logger = logging.getLogger(__name__)


class CVReplacer:
    """
    Generates and applies targeted CV changes for job alignment.
    
    Uses the REPLACE prompt to suggest and apply only critical changes
    that meaningfully improve CV-to-job alignment. Avoids over-editing
    to maintain authenticity.
    
    Usage:
        replacer = CVReplacer()
        
        # Generate suggested changes
        changes = replacer.generate_changes(cv_latex, alignment)
        print(f"Generated {len(changes)} changes")
        
        # Apply changes to CV
        new_cv = replacer.apply_changes(cv_latex, changes)
    """
    
    def __init__(
        self,
        prompt_loader: Optional[PromptLoader] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        """
        Initialize CVReplacer.
        
        Args:
            prompt_loader: PromptLoader instance (uses default if None)
            llm_client: LLMClient instance (uses default if None)
        """
        self.prompt_loader = prompt_loader or get_prompt_loader()
        self.llm_client = llm_client or get_llm_client()
    
    def generate_changes(
        self,
        cv_latex: str,
        alignment: Dict[str, Any],
        stories: Optional[List[Dict]] = None,
        options: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate targeted CV changes based on alignment analysis.
        
        Args:
            cv_latex: The candidate's CV in LaTeX format
            alignment: Alignment analysis from CVAlignment.analyze()
            stories: Optional vault experience stories to draw from
            options: Optional parameters:
                - rewriteCoverage: Target fraction of bullets to rewrite (0.0-1.0)
                - mustEditLineNumbers: List of line numbers that must be edited
                - preferredEditLineNumbers: List of preferred lines to edit
                - exhaustiveInventory: If True, only use text from source
                
        Returns:
            List of change dicts, each containing:
                - original_text: The original LaTeX text to replace
                - edited_text: The new LaTeX text
                - change_type: "edit", "keep", or "add"
                - reason: Why this change was suggested
                - keywords_added: List of keywords this change adds
        """
        if not cv_latex or not cv_latex.strip():
            logger.warning("CV LaTeX is empty, returning no changes")
            return []
        
        if not alignment:
            logger.warning("Alignment analysis is empty, returning no changes")
            return []
        
        try:
            system_prompt = self.prompt_loader.REPLACE_SYSTEM
            user_prompt = self.prompt_loader.build_replace_user(
                latex=cv_latex,
                alignment=alignment,
                stories=stories or [],
                options=options or {},
            )
            
            response = self.llm_client.complete_with_json(
                messages=[{"role": "user", "content": user_prompt}],
                system=system_prompt,
            )
            
            if not response.success:
                logger.error(f"Change generation failed: {response.error}")
                return []
            
            try:
                changes = json.loads(response.content)
                # Ensure it's a list
                if isinstance(changes, dict):
                    # Some prompts return a dict with changes array
                    if "changes" in changes:
                        changes = changes["changes"]
                    elif "items" in changes:
                        changes = changes["items"]
                    else:
                        changes = [changes]
                
                # Validate and clean each change
                validated_changes = []
                for change in changes:
                    if self._is_valid_change(change):
                        validated_changes.append(self._normalize_change(change))
                
                return validated_changes
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from LLM response: {e}")
                return []
                
        except Exception as e:
            logger.exception("Change generation failed unexpectedly")
            return []
    
    def apply_changes(
        self,
        cv_latex: str,
        changes: List[Dict[str, Any]],
    ) -> str:
        """
        Apply generated changes to CV LaTeX.
        
        Args:
            cv_latex: Original CV LaTeX content
            changes: List of change dicts from generate_changes()
            
        Returns:
            Modified CV LaTeX string with changes applied
        """
        if not changes:
            return cv_latex
        
        result = cv_latex
        
        # Sort changes by the position of original_text in the document
        # to avoid offset issues when applying multiple changes
        sorted_changes = []
        for change in changes:
            original = change.get("original_text", "")
            if not original:
                continue
            
            # Find position in the document
            pos = result.find(original)
            if pos >= 0:
                sorted_changes.append((pos, change))
        
        # Sort by position in reverse order (apply from end to start)
        sorted_changes.sort(key=lambda x: x[0], reverse=True)
        
        for pos, change in sorted_changes:
            original = change.get("original_text", "")
            edited = change.get("edited_text", "")
            change_type = change.get("change_type", "edit")
            
            if change_type == "keep":
                continue
            
            if original and edited and original in result:
                result = result.replace(original, edited, 1)
                logger.debug(f"Applied change: {original[:50]}... -> {edited[:50]}...")
        
        return result
    
    def apply_critical_changes_only(
        self,
        cv_latex: str,
        changes: List[Dict[str, Any]],
        critical_threshold: float = 0.7,
    ) -> str:
        """
        Apply only highly critical changes based on keyword impact score.
        
        Args:
            cv_latex: Original CV LaTeX content
            changes: List of change dicts from generate_changes()
            critical_threshold: Minimum keyword impact score (0.0-1.0) to apply
            
        Returns:
            Modified CV LaTeX with only critical changes applied
        """
        critical_changes = [
            c for c in changes
            if c.get("change_type") != "keep"
            and c.get("keyword_impact_score", 1.0) >= critical_threshold
        ]
        return self.apply_changes(cv_latex, critical_changes)
    
    def _is_valid_change(self, change: Dict[str, Any]) -> bool:
        """Check if a change dict has the required structure."""
        if not isinstance(change, dict):
            return False
        
        # Must have either original_text or change_type == "keep"
        if change.get("change_type") == "keep":
            return True
        
        original = change.get("original_text", "")
        edited = change.get("edited_text", "")
        
        return bool(original and edited)
    
    def _normalize_change(self, change: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a change dict to ensure all required fields."""
        return {
            "original_text": change.get("original_text", ""),
            "edited_text": change.get("edited_text", ""),
            "change_type": change.get("change_type", "edit"),
            "reason": change.get("reason", ""),
            "keywords_added": change.get("keywords_added", []),
            "keyword_impact_score": change.get("keyword_impact_score", 0.5),
        }


def get_cv_replacer() -> CVReplacer:
    """Get a default CVReplacer instance."""
    return CVReplacer()
