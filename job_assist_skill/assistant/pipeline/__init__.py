"""Pipeline modules for career assistant."""

from .latex_compiler import LaTeXCompiler, get_compiler
from .email_generator import EmailGenerator, ApplicationEmail, get_email_generator
from .aggregator import JobCandidate, MultiSourceAggregator
from .tailoring import CVTailoringPipeline, TailoringContext, TailoringResult, prepare_tailoring

# New pipeline modules
from .job_parser import JobParser, get_job_parser
from .alignment import CVAlignment, get_alignment_analyzer
from .replacer import CVReplacer, get_cv_replacer
from .cover_letter import CoverLetterGenerator, get_cover_letter_generator

# CV Diff Viewer
from .cv_diff_viewer import CVDiffViewer, DiffChange, create_diff_viewer

__all__ = [
    # Tailoring
    "CVTailoringPipeline",
    "TailoringContext",
    "TailoringResult",
    "prepare_tailoring",
    # LaTeX
    "LaTeXCompiler",
    "get_compiler",
    # Email
    "EmailGenerator",
    "ApplicationEmail",
    "get_email_generator",
    # Aggregator
    "JobCandidate",
    "MultiSourceAggregator",
    # Job Parser
    "JobParser",
    "get_job_parser",
    # Alignment
    "CVAlignment",
    "get_alignment_analyzer",
    # CV Replacer
    "CVReplacer",
    "get_cv_replacer",
    # Cover Letter
    "CoverLetterGenerator",
    "get_cover_letter_generator",
    # CV Diff
    "CVDiffViewer",
    "DiffChange",
    "create_diff_viewer",
]
