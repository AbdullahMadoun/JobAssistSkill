"""
Cover Letter Generator - Generates tailored cover letters.

Uses the COVER_LETTER prompt to generate professional cover letters
based on job requirements, CV, and alignment analysis.
"""

import json
import logging
from typing import Any, Dict, Optional

from ..prompts.loader import PromptLoader, get_prompt_loader
from .llm_client import LLMClient, get_llm_client

logger = logging.getLogger(__name__)


class CoverLetterGenerator:
    """
    Generates tailored cover letters for job applications.
    
    Uses the COVER_LETTER prompt to create professional cover letters
    that highlight relevant experience and alignment with job requirements.
    
    Usage:
        generator = CoverLetterGenerator()
        
        cover_letter = generator.generate(parsed_job, cv_latex, alignment)
        print(cover_letter)  # LaTeX content
    """
    
    def __init__(
        self,
        prompt_loader: Optional[PromptLoader] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        """
        Initialize CoverLetterGenerator.
        
        Args:
            prompt_loader: PromptLoader instance (uses default if None)
            llm_client: LLMClient instance (uses default if None)
        """
        self.prompt_loader = prompt_loader or get_prompt_loader()
        self.llm_client = llm_client or get_llm_client()
    
    def generate(
        self,
        parsed_job: Dict[str, Any],
        cv_latex: str,
        alignment: Optional[Dict[str, Any]] = None,
        job: Optional[Dict[str, Any]] = None,
        user_story: str = "",
        template: str = "",
    ) -> str:
        """
        Generate a tailored cover letter.
        
        Args:
            parsed_job: Parsed job requirements from JobParser
            cv_latex: The candidate's CV in LaTeX format
            alignment: Optional alignment analysis from CVAlignment
            job: Optional job metadata (company info, contact, etc.)
            user_story: Optional user story/objectives for personalization
            template: Optional cover letter template LaTeX
            
        Returns:
            Cover letter content in LaTeX format, or empty string on failure
        """
        if not parsed_job:
            logger.warning("Parsed job is empty, cannot generate cover letter")
            return ""
        
        if not cv_latex or not cv_latex.strip():
            logger.warning("CV LaTeX is empty, cannot generate cover letter")
            return ""
        
        try:
            system_prompt = self.prompt_loader.COVER_LETTER_SYSTEM
            user_prompt = self.prompt_loader.build_cover_letter_user(
                parsed_req=parsed_job,
                latex=cv_latex,
                alignment=alignment or {},
                job=job,
                user_story=user_story,
                template=template,
            )
            
            response = self.llm_client.complete_with_json(
                messages=[{"role": "user", "content": user_prompt}],
                system=system_prompt,
            )
            
            if not response.success:
                logger.error(f"Cover letter generation failed: {response.error}")
                return ""
            
            try:
                # Parse the JSON response - some prompts return just content,
                # others return structured data
                result = json.loads(response.content)
                
                if isinstance(result, dict):
                    # Try to extract body content
                    if "body" in result:
                        return result["body"]
                    elif "content" in result:
                        return result["content"]
                    elif "cover_letter" in result:
                        return result["cover_letter"]
                    else:
                        # Return the whole JSON as string for debugging
                        logger.warning("Unexpected JSON structure from LLM")
                        return json.dumps(result, indent=2)
                else:
                    return str(result)
                    
            except json.JSONDecodeError as e:
                # If it's not valid JSON, return the raw content
                logger.warning(f"Could not parse JSON from LLM response: {e}")
                return response.content
                
        except Exception as e:
            logger.exception("Cover letter generation failed unexpectedly")
            return ""
    
    def generate_with_template(
        self,
        parsed_job: Dict[str, Any],
        cv_latex: str,
        template: str,
        alignment: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a cover letter using a specific template.
        
        Args:
            parsed_job: Parsed job requirements
            cv_latex: Candidate's CV LaTeX
            template: Cover letter template LaTeX to use
            alignment: Optional alignment analysis
            
        Returns:
            Cover letter content in LaTeX format
        """
        return self.generate(
            parsed_job=parsed_job,
            cv_latex=cv_latex,
            alignment=alignment,
            template=template,
        )
    
    def extract_letter_components(self, cover_letter: str) -> Dict[str, str]:
        """
        Extract structured components from a cover letter.
        
        Args:
            cover_letter: The generated cover letter LaTeX content
            
        Returns:
            Dict with components:
                - greeting: Opening salutation
                - intro: Introduction paragraph
                - body: Main paragraphs
                - closing: Closing paragraph and sign-off
        """
        components = {
            "greeting": "",
            "intro": "",
            "body": "",
            "closing": "",
        }
        
        if not cover_letter:
            return components
        
        # Simple extraction based on common patterns
        lines = cover_letter.split("\n")
        
        # Find greeting (Dear...)
        for line in lines:
            if line.strip().lower().startswith("dear"):
                components["greeting"] = line.strip()
                break
        
        # Find closing (Sincerely, Best regards, etc.)
        for line in reversed(lines):
            if any(phrase in line.lower() for phrase in ["sincerely", "best regards", "respectfully"]):
                # Get the closing paragraph
                components["closing"] = line.strip()
                break
        
        return components


def get_cover_letter_generator() -> CoverLetterGenerator:
    """Get a default CoverLetterGenerator instance."""
    return CoverLetterGenerator()
