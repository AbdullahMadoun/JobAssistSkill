"""
CV Alignment Analyzer - Analyzes CV against job requirements.

Uses the ANALYZE_ALIGNMENT prompt to compare a CV against parsed
job requirements and identify gaps, strengths, and improvement areas.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from ..prompts.loader import PromptLoader, get_prompt_loader
from .llm_client import LLMClient, get_llm_client

logger = logging.getLogger(__name__)


class CVAlignment:
    """
    Analyzes CV alignment with job requirements.
    
    Compares a candidate's CV LaTeX against parsed job requirements
    to identify:
    - Overall alignment score
    - Missing skills/keywords
    - Existing strengths
    - Suggestions for improvement
    
    Usage:
        analyzer = CVAlignment()
        result = analyzer.analyze(parsed_job, cv_latex)
        
        print(result["overall_score"])
        print(result["missing_keywords"])
    """
    
    def __init__(
        self,
        prompt_loader: Optional[PromptLoader] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        """
        Initialize CVAlignment analyzer.
        
        Args:
            prompt_loader: PromptLoader instance (uses default if None)
            llm_client: LLMClient instance (uses default if None)
        """
        self.prompt_loader = prompt_loader or get_prompt_loader()
        self.llm_client = llm_client or get_llm_client()
    
    def analyze(
        self,
        parsed_job: Dict[str, Any],
        cv_latex: str,
    ) -> Dict[str, Any]:
        """
        Analyze CV alignment with job requirements.
        
        Args:
            parsed_job: Parsed job requirements from JobParser
            cv_latex: The candidate's CV in LaTeX format
            
        Returns:
            Dict containing alignment analysis with keys:
                - overall_score: Float score (0.0 to 1.0)
                - section_scores: Dict of section-to-score mappings
                - matched_keywords: List of keywords found in both
                - missing_keywords: List of required keywords missing from CV
                - strength_bullets: List of CV bullets that strongly match
                - weakness_bullets: List of CV bullets that need improvement
                - suggestions: List of improvement suggestions
        """
        if not parsed_job:
            return self._empty_result("Parsed job requirements are empty")
        
        if not cv_latex or not cv_latex.strip():
            return self._empty_result("CV LaTeX is empty")
        
        try:
            system_prompt = self.prompt_loader.ANALYZE_ALIGNMENT_SYSTEM
            user_prompt = self.prompt_loader.ANALYZE_ALIGNMENT_USER(parsed_job, cv_latex)
            
            response = self.llm_client.complete_with_json(
                messages=[{"role": "user", "content": user_prompt}],
                system=system_prompt,
            )
            
            if not response.success:
                logger.error(f"Alignment analysis failed: {response.error}")
                return self._empty_result(f"LLM error: {response.error}")
            
            try:
                analysis = json.loads(response.content)
                # Ensure required keys exist
                analysis.setdefault("overall_score", 0.0)
                analysis.setdefault("section_scores", {})
                analysis.setdefault("matched_keywords", [])
                analysis.setdefault("missing_keywords", [])
                analysis.setdefault("strength_bullets", [])
                analysis.setdefault("weakness_bullets", [])
                analysis.setdefault("suggestions", [])
                return analysis
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from LLM response: {e}")
                return self._empty_result(f"JSON parse error: {e}")
                
        except Exception as e:
            logger.exception("Alignment analysis failed unexpectedly")
            return self._empty_result(str(e))
    
    def _empty_result(self, error: str) -> Dict[str, Any]:
        """Return an empty/error result structure."""
        return {
            "overall_score": 0.0,
            "section_scores": {},
            "matched_keywords": [],
            "missing_keywords": [],
            "strength_bullets": [],
            "weakness_bullets": [],
            "suggestions": [],
            "error": error,
        }
    
    def batch_analyze(
        self,
        parsed_jobs: List[Dict[str, Any]],
        cv_latex: str,
    ) -> List[Dict[str, Any]]:
        """
        Analyze CV alignment against multiple job postings.
        
        Args:
            parsed_jobs: List of parsed job requirements
            cv_latex: The candidate's CV in LaTeX format
            
        Returns:
            List of alignment analysis dicts (one per job)
        """
        results = []
        for job in parsed_jobs:
            results.append(self.analyze(job, cv_latex))
        return results


def get_alignment_analyzer() -> CVAlignment:
    """Get a default CVAlignment analyzer instance."""
    return CVAlignment()
