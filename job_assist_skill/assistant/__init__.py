"""Agent-facing helpers for dual-stream job search and CV tailoring."""

from .memory import PreferenceMemory
from .preferences import Preferences
from .prompts.loader import PromptLoader, get_prompt_loader
from .service import CareerAssistant, SearchCandidate
from .scrapers import HiringPostScraper, JobPostingScraper
from .pipeline import (
    CVDiffViewer,
    CVAlignment,
    CVReplacer,
    CVTailoringPipeline,
    CoverLetterGenerator,
    DiffChange,
    EmailGenerator,
    JobParser,
    LaTeXCompiler,
    TailoringContext,
    TailoringResult,
    create_diff_viewer,
    get_alignment_analyzer,
    get_compiler,
    get_cover_letter_generator,
    get_cv_replacer,
    get_email_generator,
    get_job_parser,
)
from .ranker import JobRanker, KeywordScorer, get_job_ranker, get_keyword_scorer
from .storage import FeedbackStore, get_feedback_store
from .email import MailtoClient, get_mailto_client

__all__ = [
    "CareerAssistant",
    "SearchCandidate",
    "PreferenceMemory",
    "Preferences",
    "PromptLoader",
    "get_prompt_loader",
    "HiringPostScraper",
    "JobPostingScraper",
    "JobParser",
    "CVAlignment",
    "CVReplacer",
    "CoverLetterGenerator",
    "LaTeXCompiler",
    "CVDiffViewer",
    "DiffChange",
    "CVTailoringPipeline",
    "TailoringContext",
    "TailoringResult",
    "EmailGenerator",
    "KeywordScorer",
    "JobRanker",
    "FeedbackStore",
    "MailtoClient",
    "create_diff_viewer",
    "get_job_parser",
    "get_alignment_analyzer",
    "get_cv_replacer",
    "get_compiler",
    "get_cover_letter_generator",
    "get_email_generator",
    "get_keyword_scorer",
    "get_job_ranker",
    "get_feedback_store",
    "get_mailto_client",
]
