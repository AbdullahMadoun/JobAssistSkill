"""Agent-driven CV tailoring workflow helpers."""

from __future__ import annotations

import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .alignment import CVAlignment, get_alignment_analyzer
from .cover_letter import CoverLetterGenerator, get_cover_letter_generator
from .job_parser import JobParser, get_job_parser
from .replacer import CVReplacer, get_cv_replacer


@dataclass
class TailoringContext:
    """Initial tailoring bundle the agent uses to start staged prompt work."""

    job_requirements: Dict[str, Any]
    parse_job_prompt: Dict[str, str]
    cv_latex: str
    alignment_prompt: str
    replace_prompt: Optional[str] = None
    suggested_changes: Optional[List[Dict[str, Any]]] = None
    tailoring_session_id: str = ""
    artifact_dir: str = "./output"
    user_profile: Dict[str, Any] = field(default_factory=dict)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    quality_checks: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)


@dataclass
class TailoringResult:
    """Result from the deterministic tailoring preparation stage."""

    success: bool
    context: Optional[TailoringContext] = None
    latex_path: Optional[str] = None
    context_path: Optional[str] = None
    error: Optional[str] = None


class CVTailoringPipeline:
    """Prepare staged prompt assets and apply agent-authored changes."""

    def __init__(
        self,
        job_parser: Optional[JobParser] = None,
        alignment_analyzer: Optional[CVAlignment] = None,
        cv_replacer: Optional[CVReplacer] = None,
        cover_letter_generator: Optional[CoverLetterGenerator] = None,
    ):
        self.job_parser = job_parser or get_job_parser()
        self.alignment_analyzer = alignment_analyzer or get_alignment_analyzer()
        self.cv_replacer = cv_replacer or get_cv_replacer()
        self.cover_letter_generator = cover_letter_generator or get_cover_letter_generator()

    def prepare(
        self,
        job_text: str,
        cv_latex: str,
        output_dir: str = "./output",
        session_id: Optional[str] = None,
    ) -> TailoringResult:
        """Create the initial parse bundle for the agent."""
        if session_id is None:
            session_id = str(uuid.uuid4())[:8]

        try:
            output_root = Path(output_dir)
            output_root.mkdir(parents=True, exist_ok=True)

            latex_path = output_root / f"cv_{session_id}.tex"
            context_path = output_root / f"context_{session_id}.json"
            latex_path.write_text(cv_latex, encoding="utf-8")

            parse_package = self.job_parser.prepare_prompt(job_text)
            context = TailoringContext(
                job_requirements={
                    "text": job_text[:5000],
                    "system_prompt": parse_package["system"],
                    "parse_prompt": parse_package["user"],
                },
                parse_job_prompt=parse_package,
                cv_latex=cv_latex,
                alignment_prompt=(
                    "Next step: run `python main.py tailor alignment --parsed-job <parsed_job.json> "
                    f"--cv-file {latex_path}` after the agent completes PARSE_JOB."
                ),
                tailoring_session_id=session_id,
                artifact_dir=str(output_root),
                quality_checks=[
                    "Do not invent facts, metrics, certifications, or years of experience.",
                    "Prefer truthful keyword alignment over keyword stuffing.",
                    "Keep original LaTeX structure valid so the CV can still compile.",
                    "Prioritize bullets with the highest job relevance when choosing edits.",
                ],
                next_steps=[
                    "Use job_requirements.system_prompt and job_requirements.parse_prompt to produce parsed_job.json.",
                    f"Run `python main.py tailor alignment --parsed-job <parsed_job.json> --cv-file {latex_path}`.",
                    f"Run `python main.py tailor replace --alignment <alignment.json> --cv-file {latex_path}`.",
                    f"Run `python main.py tailor apply --context {context_path} --alignment <alignment.json> --changes <changes.json>`.",
                ],
            )
            context_path.write_text(
                json_dumps(asdict(context)),
                encoding="utf-8",
            )

            return TailoringResult(
                success=True,
                context=context,
                latex_path=str(latex_path),
                context_path=str(context_path),
            )
        except Exception as exc:
            return TailoringResult(success=False, error=str(exc))

    def build_alignment_prompt(self, parsed_job: Dict[str, Any], cv_latex: str) -> Dict[str, str]:
        """Compatibility wrapper for building the alignment prompt package."""
        return self.alignment_analyzer.prepare_prompt(parsed_job, cv_latex)

    def build_replace_prompt(
        self,
        cv_latex: str,
        alignment: Dict[str, Any],
        stories: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """Compatibility wrapper for building the replacement prompt package."""
        return self.cv_replacer.prepare_prompt(
            cv_latex=cv_latex,
            alignment=alignment,
            stories=stories,
            options=options,
        )

    def build_cover_letter_prompt(
        self,
        parsed_job: Dict[str, Any],
        cv_latex: str,
        alignment: Optional[Dict[str, Any]] = None,
        job: Optional[Dict[str, Any]] = None,
        user_story: str = "",
        template: str = "",
    ) -> Dict[str, str]:
        """Compatibility wrapper for building the cover-letter prompt package."""
        return self.cover_letter_generator.prepare_prompt(
            parsed_job=parsed_job,
            cv_latex=cv_latex,
            alignment=alignment,
            job=job,
            user_story=user_story,
            template=template,
        )

    def apply_llm_results(
        self,
        context: TailoringContext,
        alignment_analysis: Dict[str, Any],
        suggested_changes: List[Dict[str, Any]],
        cv_latex: str,
        output_dir: str = "./output",
    ) -> str:
        """Apply agent-authored edit objects and save tailored LaTeX."""
        result_latex = cv_latex
        for change in suggested_changes:
            if change.get("change_type") == "edit":
                original = change.get("original_text", "")
                edited = change.get("edited_text", "")
                if original and edited and original in result_latex:
                    result_latex = result_latex.replace(original, edited, 1)

        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        output_path = output_root / f"cv_{context.tailoring_session_id}_tailored.tex"
        output_path.write_text(result_latex, encoding="utf-8")
        return str(output_path)

    def apply_llm_results_from_payload(
        self,
        payload: Dict[str, Any],
        alignment_analysis: Dict[str, Any],
        suggested_changes: List[Dict[str, Any]],
        output_path: Optional[str] = None,
    ) -> str:
        """Apply agent-authored edits from a saved context payload."""
        context = TailoringContext(**payload)
        result_latex = self.apply_llm_results(
            context=context,
            alignment_analysis=alignment_analysis,
            suggested_changes=suggested_changes,
            cv_latex=context.cv_latex,
            output_dir=Path(output_path).parent.as_posix() if output_path else context.artifact_dir,
        )
        if output_path:
            final_output = Path(output_path)
            final_output.parent.mkdir(parents=True, exist_ok=True)
            final_output.write_text(Path(result_latex).read_text(encoding="utf-8"), encoding="utf-8")
            return str(final_output)
        return result_latex


def prepare_tailoring(
    job_text: str,
    cv_latex: str,
    output_dir: str = "./output",
    **_: Any,
) -> TailoringResult:
    """Convenience wrapper for initial tailoring preparation."""
    pipeline = CVTailoringPipeline()
    return pipeline.prepare(job_text, cv_latex, output_dir)


def json_dumps(payload: Dict[str, Any]) -> str:
    import json

    return json.dumps(payload, indent=2, ensure_ascii=False)
