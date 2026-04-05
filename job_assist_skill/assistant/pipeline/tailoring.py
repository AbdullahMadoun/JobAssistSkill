"""
CV Tailoring Pipeline - Prepares data for opencode-powered LLM processing.

Does NOT call LLM APIs directly. Instead, prepares structured data and prompts
that can be passed to opencode skills for LLM processing.

Workflow:
1. Parse job requirements from post text (preparation)
2. Prepare alignment analysis data
3. Prepare rewrite prompts with context
4. Output is consumed by opencode skills for actual LLM calls
"""

import json
import logging
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class TailoringContext:
    """Context prepared for opencode to perform CV tailoring."""
    job_requirements: Dict[str, Any]
    cv_latex: str
    alignment_prompt: str
    alignment_analysis: Optional[Dict] = None
    replace_prompt: Optional[str] = None
    suggested_changes: Optional[List[Dict]] = None
    tailoring_session_id: str = ""


@dataclass
class TailoringResult:
    """Result from CV tailoring preparation."""
    success: bool
    context: Optional[TailoringContext] = None
    latex_path: Optional[str] = None
    error: Optional[str] = None


class CVTailoringPipeline:
    """
    Prepares CV tailoring data for opencode LLM processing.

    This class prepares all necessary data and prompts but does NOT
    make LLM calls - that is handled by opencode skills.

    Usage:
        pipeline = CVTailoringPipeline()
        result = pipeline.prepare(
            job_text="We're hiring a senior Python engineer...",
            cv_latex=original_latex,
        )
        # Pass result.context to opencode skills for LLM processing
    """

    def __init__(self):
        """Initialize the tailoring pipeline."""
        self._load_prompts()

    def _load_prompts(self):
        """Load prompts from prompts.js."""
        try:
            from ..prompts.loader import get_prompt_loader
            self.prompt_loader = get_prompt_loader()
        except Exception as e:
            logger.warning(f"Could not load prompts: {e}")
            self.prompt_loader = None

    def prepare(
        self,
        job_text: str,
        cv_latex: str,
        output_dir: str = "./output",
        session_id: Optional[str] = None,
    ) -> TailoringResult:
        """
        Prepare CV tailoring context for opencode processing.

        Args:
            job_text: Job posting text (from LinkedIn post)
            cv_latex: Original CV in LaTeX format
            output_dir: Directory for output files
            session_id: Optional session identifier

        Returns:
            TailoringResult with prepared context for opencode
        """
        import uuid
        
        if session_id is None:
            session_id = str(uuid.uuid4())[:8]

        try:
            latex_path = os.path.join(output_dir, f"cv_{session_id}.tex")
            os.makedirs(output_dir, exist_ok=True)
            Path(latex_path).write_text(cv_latex, encoding='utf-8')

            job_requirements = self._prepare_job_requirements(job_text)
            
            alignment_prompt = self._prepare_alignment_prompt(job_requirements, cv_latex)
            
            context = TailoringContext(
                job_requirements=job_requirements,
                cv_latex=cv_latex,
                alignment_prompt=alignment_prompt,
                tailoring_session_id=session_id,
            )

            return TailoringResult(
                success=True,
                context=context,
                latex_path=latex_path,
            )

        except Exception as e:
            logger.exception("CV tailoring preparation failed")
            return TailoringResult(success=False, error=str(e))

    def _prepare_job_requirements(self, job_text: str) -> Dict[str, Any]:
        """Prepare job requirements prompt for parsing."""
        if self.prompt_loader:
            return {
                "text": job_text[:5000],
                "parse_prompt": self.prompt_loader.PARSE_JOB_USER(job_text),
                "system_prompt": self.prompt_loader.PARSE_JOB_SYSTEM,
            }
        
        return {
            "text": job_text[:5000],
            "parse_prompt": f"<job_posting>\n{job_text}\n</job_posting>\n\nExtract the posting into JSON with: company, title, required_skills, preferred_skills, responsibilities.",
            "system_prompt": "You are a job requirement extractor. Return JSON with company, title, required_skills, preferred_skills, responsibilities, education, experience_years.",
        }

    def _prepare_alignment_prompt(
        self,
        job_requirements: Dict,
        cv_latex: str,
    ) -> str:
        """Prepare alignment analysis prompt."""
        if self.prompt_loader:
            parsed = job_requirements.get("parsed_json", {})
            return self.prompt_loader.ANALYZE_ALIGNMENT_USER(parsed, cv_latex)
        
        return f"<job_requirements>\n{json.dumps(job_requirements.get('parsed_json', {}), indent=2)}\n</job_requirements>\n\n<candidate_cv_latex>\n{cv_latex}\n</candidate_cv_latex>\n\nAnalyze the CV against job requirements. Return JSON with overall_score, sections analysis, and bullet-level review."

    def apply_llm_results(
        self,
        context: TailoringContext,
        alignment_analysis: Dict,
        suggested_changes: List[Dict],
        cv_latex: str,
        output_dir: str = "./output",
    ) -> str:
        """
        Apply LLM-generated results to produce tailored LaTeX.
        
        Args:
            context: Original tailoring context
            alignment_analysis: LLM output from alignment analysis
            suggested_changes: LLM output from rewrite generation
            cv_latex: Original CV LaTeX
            
        Returns:
            Path to tailored LaTeX file
        """
        result_latex = cv_latex
        
        for change in suggested_changes:
            if change.get("change_type") == "edit":
                original = change.get("original_text", "")
                edited = change.get("edited_text", "")
                if original and edited and original in result_latex:
                    result_latex = result_latex.replace(original, edited, 1)

        output_path = os.path.join(output_dir, f"cv_{context.tailoring_session_id}_tailored.tex")
        Path(output_path).write_text(result_latex, encoding='utf-8')
        
        return output_path

    def prepare_replace_prompt(
        self,
        cv_latex: str,
        alignment: Dict,
        parsed_req: Dict,
    ) -> Dict[str, str]:
        """
        Prepare the replace/rewrite prompt for opencode.
        
        Returns dict with 'system' and 'user' prompts ready for LLM.
        """
        if self.prompt_loader:
            return {
                "system": self.prompt_loader.REPLACE_SYSTEM,
                "user": self.prompt_loader.build_replace_user(
                    latex=cv_latex,
                    alignment=alignment,
                    stories=[],
                    options={"rewriteCoverage": 0.4},
                ),
            }
        
        return {
            "system": "You are a CV tailoring engine. Suggest high-value edits to bullets.",
            "user": f"<alignment>\n{json.dumps(alignment)}\n</alignment>\n\n<cv>\n{cv_latex}\n</cv>\n\nSuggest edits as JSON with original_text and edited_text.",
        }


def prepare_tailoring(
    job_text: str,
    cv_latex: str,
    output_dir: str = "./output",
    **kwargs,
) -> TailoringResult:
    """
    Convenience function to prepare CV tailoring.

    Args:
        job_text: Job posting text
        cv_latex: Original CV in LaTeX
        output_dir: Output directory
        **kwargs: Additional args

    Returns:
        TailoringResult
    """
    pipeline = CVTailoringPipeline()
    return pipeline.prepare(job_text, cv_latex, output_dir)
