"""
Job Parser - Parses job postings into structured requirements.

Uses the PARSE_JOB prompt to extract structured requirements from
free-text job postings.
"""

import json
import logging
from typing import Any, Dict, Optional

from ..prompts.loader import PromptLoader, get_prompt_loader
from .llm_client import LLMClient, get_llm_client

logger = logging.getLogger(__name__)


class JobParser:
    """
    Parses job postings into structured requirements.
    
    Uses LLM to extract structured data from job posting text,
    identifying required skills, responsibilities, qualifications, etc.
    
    Usage:
        parser = JobParser()
        result = parser.parse(job_text="We're hiring a senior Python engineer...")
        
        # Access parsed requirements:
        print(result["required_skills"])
        print(result["title"])
    """
    
    def __init__(
        self,
        prompt_loader: Optional[PromptLoader] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        """
        Initialize JobParser.
        
        Args:
            prompt_loader: PromptLoader instance (uses default if None)
            llm_client: LLMClient instance (uses default if None)
        """
        self.prompt_loader = prompt_loader or get_prompt_loader()
        self.llm_client = llm_client or get_llm_client()
    
    def parse(self, job_text: str) -> Dict[str, Any]:
        """
        Parse a job posting into structured requirements.
        
        Args:
            job_text: The full job posting text (from LinkedIn, company website, etc.)
            
        Returns:
            Dict containing parsed job requirements with keys:
                - title: Job title
                - company: Company name (if found)
                - location: Job location
                - required_skills: List of required technical/soft skills
                - preferred_skills: List of nice-to-have skills
                - responsibilities: List of main responsibilities
                - qualifications: List of qualifications/requirements
                - education: Education requirements
                - experience_years: Years of experience required
                - raw_text: Original text (preserved for reference)
        """
        if not job_text or not job_text.strip():
            return self._empty_result("Job text is empty")
        
        try:
            system_prompt = self.prompt_loader.PARSE_JOB_SYSTEM
            user_prompt = self.prompt_loader.PARSE_JOB_USER(job_text)
            
            response = self.llm_client.complete_with_json(
                messages=[{"role": "user", "content": user_prompt}],
                system=system_prompt,
            )
            
            if not response.success:
                logger.error(f"Job parsing failed: {response.error}")
                return self._empty_result(f"LLM error: {response.error}")
            
            try:
                parsed = json.loads(response.content)
                parsed["raw_text"] = job_text[:5000]  # Preserve original
                return parsed
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from LLM response: {e}")
                return self._empty_result(f"JSON parse error: {e}")
                
        except Exception as e:
            logger.exception("Job parsing failed unexpectedly")
            return self._empty_result(str(e))
    
    def _empty_result(self, error: str) -> Dict[str, Any]:
        """Return an empty/error result structure."""
        return {
            "title": "",
            "company": "",
            "location": "",
            "required_skills": [],
            "preferred_skills": [],
            "responsibilities": [],
            "qualifications": [],
            "education": "",
            "experience_years": 0,
            "raw_text": "",
            "error": error,
        }
    
    def parse_multiple(self, job_texts: list) -> list:
        """
        Parse multiple job postings.
        
        Args:
            job_texts: List of job posting texts
            
        Returns:
            List of parsed job requirement dicts
        """
        results = []
        for text in job_texts:
            results.append(self.parse(text))
        return results


def get_job_parser() -> JobParser:
    """Get a default JobParser instance."""
    return JobParser()
