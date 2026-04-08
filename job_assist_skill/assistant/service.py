"""Agent-facing service layer for scraping, tailoring, and email drafting."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional

from .. import keywords as kw
from ..scraper import BrowserManager, HiringPostSearcher, JobScraper, JobSearchScraper

from .email.mailto_client import MailtoClient
from .memory import PreferenceMemory
from .pipeline.email_generator import ApplicationEmail, EmailGenerator
from .pipeline.latex_compiler import LaTeXCompiler
from .pipeline.tailoring import CVTailoringPipeline

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _csv_to_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


@dataclass
class SearchCandidate:
    """Normalized search result returned from either LinkedIn stream."""

    source: Literal["jobs", "posts"]
    url: str
    query_role: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    locations: List[str] = field(default_factory=list)
    text: str = ""
    snippet: str = ""
    posted_date: str = ""
    author: str = ""
    contact_emails: List[str] = field(default_factory=list)
    detail_level: str = ""
    match_score: int = 0
    quality_flags: List[str] = field(default_factory=list)
    next_action: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CareerAssistant:
    """Stable, agent-friendly interface over the deterministic repo capabilities."""

    def __init__(
        self,
        memory_path: Optional[str] = None,
        output_dir: str = "output",
    ):
        self.repo_root = _repo_root()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.memory = PreferenceMemory(memory_path)

    def validate_setup(self) -> Dict[str, bool]:
        """Validate local prerequisites without touching external APIs."""
        memory = self.memory.to_dict()
        session_path = self._resolve_repo_file(memory["files"]["linkedin_session"])
        cv_path = self._resolve_repo_file(memory["files"]["cv_path"])
        return {
            "session_file": session_path.exists(),
            "cv_template": cv_path.exists(),
            "pdflatex": shutil.which("pdflatex") is not None,
            "playwright": True,
        }

    def get_blocking_inputs(self) -> List[Dict[str, str]]:
        """Return missing setup items the agent should ask the user about."""
        memory = self.memory.to_dict()
        profile = memory.get("profile", {})
        files = memory.get("files", {})
        blockers: List[Dict[str, str]] = []

        name = str(profile.get("name", "") or "").strip()
        if not name:
            blockers.append(
                {
                    "key": "profile.name",
                    "reason": "candidate_name_missing",
                    "question": "What full candidate name should I use for CV and application drafts?",
                }
            )

        email = str(profile.get("email", "") or "").strip()
        if not email:
            blockers.append(
                {
                    "key": "profile.email",
                    "reason": "candidate_email_missing",
                    "question": "What email address should I use for application drafts and mailto links?",
                }
            )

        cv_path_value = str(files.get("cv_path", "") or "").strip()
        if not cv_path_value:
            blockers.append(
                {
                    "key": "files.cv_path",
                    "reason": "cv_template_missing",
                    "question": "What is the path to the LaTeX CV template (.tex) I should use?",
                }
            )
        elif not self._resolve_repo_file(cv_path_value).exists():
            blockers.append(
                {
                    "key": "files.cv_path",
                    "reason": "cv_template_not_found",
                    "question": f"I could not find the saved CV template at {cv_path_value}. What .tex file should I use instead?",
                }
            )

        session_path_value = str(files.get("linkedin_session", "") or "").strip()
        if not session_path_value:
            blockers.append(
                {
                    "key": "files.linkedin_session",
                    "reason": "linkedin_session_missing",
                    "question": "Do you already have a saved LinkedIn session JSON, or should I run the login flow and save one?",
                }
            )
        elif not self._resolve_repo_file(session_path_value).exists():
            blockers.append(
                {
                    "key": "files.linkedin_session",
                    "reason": "linkedin_session_not_found",
                    "question": f"I could not find the saved LinkedIn session at {session_path_value}. Should I use a different session file or run login again?",
                }
            )

        return blockers

    def get_setup_report(self) -> Dict[str, Any]:
        """Return a machine-readable readiness report for the agent."""
        checks = self.validate_setup()
        blockers = self.get_blocking_inputs()
        return {
            "ready_for_search": checks["session_file"] and not any(
                blocker["key"] == "files.linkedin_session" for blocker in blockers
            ),
            "ready_for_tailoring": checks["cv_template"] and not any(
                blocker["key"] == "files.cv_path" for blocker in blockers
            ),
            "ready_for_email": not any(
                blocker["key"] in {"profile.name", "profile.email"} for blocker in blockers
            ),
            "checks": checks,
            "blocking_inputs": blockers,
            "suggested_agent_actions": [
                "Ask the user the listed blocking questions before continuing." if blockers else "No blocking questions. Continue with search or tailoring.",
                "Run `python main.py login` only if the saved LinkedIn session is missing or invalid.",
            ],
        }

    def resolve_cv_path(self, cv_path: Optional[str] = None) -> Path:
        """Resolve the CV template path using explicit input or memory."""
        chosen = cv_path or self.memory.get_value("files.cv_path", "cv_template.tex")
        resolved = self._resolve_repo_file(chosen)
        if not resolved.exists():
            raise FileNotFoundError(f"CV template not found: {resolved}")
        return resolved

    def resolve_session_path(self, session_path: Optional[str] = None) -> Path:
        """Resolve the LinkedIn session path using explicit input or memory."""
        chosen = session_path or self.memory.get_value("files.linkedin_session", "linkedin_session.json")
        resolved = self._resolve_repo_file(chosen)
        if not resolved.exists():
            raise FileNotFoundError(
                f"LinkedIn session file not found: {resolved}. Run `python main.py login` first."
            )
        return resolved

    async def search(
        self,
        *,
        roles: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        companies: Optional[List[str]] = None,
        stream: str = "both",
        limit: int = 10,
        min_posts: int = 3,
        timeout: int = 60,
        max_hours_age: int = 24,
        session_path: Optional[str] = None,
        headless: bool = True,
        expand_job_details: bool = True,
        email_only_posts: bool = False,
    ) -> List[SearchCandidate]:
        """Run either search stream or both and return normalized results."""
        if stream not in {"posts", "jobs", "both"}:
            raise ValueError("stream must be one of: posts, jobs, both")

        role_terms = self._expand_roles(roles or self.memory.get_value("search.roles", []))
        location_terms = self._expand_locations(locations or self.memory.get_value("search.locations", []))
        company_terms = companies or self.memory.get_value("search.companies", [])

        if not role_terms:
            raise ValueError("At least one role or freeform query is required")

        resolved_session = self.resolve_session_path(session_path)

        candidates: List[SearchCandidate] = []
        post_stream_timeout = max(15, min(timeout + 10, 90))
        job_stream_timeout = (
            max(20, min((timeout + 5) * max(1, min(limit, 5)), 180))
            if expand_job_details
            else max(15, min(timeout + 10, 90))
        )
        async with BrowserManager(headless=headless, stealth=True) as browser:
            await browser.load_session(str(resolved_session))
            await asyncio.sleep(2)

            if stream in {"posts", "both"}:
                try:
                    post_results = await self._await_with_timeout(
                        self._search_posts(
                            browser=browser,
                            roles=role_terms,
                            locations=location_terms,
                            companies=company_terms,
                            limit=limit,
                            min_posts=min_posts,
                            timeout=timeout,
                            max_hours_age=max_hours_age,
                            email_only_posts=email_only_posts,
                        ),
                        timeout=post_stream_timeout,
                    )
                    candidates.extend(post_results)
                except asyncio.TimeoutError:
                    logger.warning("Post stream exceeded timeout and was skipped.")

            if stream in {"jobs", "both"}:
                try:
                    job_results = await self._await_with_timeout(
                        self._search_jobs(
                            browser=browser,
                            roles=role_terms,
                            locations=location_terms,
                            limit=limit,
                            timeout=timeout,
                            expand_job_details=expand_job_details,
                        ),
                        timeout=job_stream_timeout,
                    )
                    candidates.extend(job_results)
                except asyncio.TimeoutError:
                    logger.warning("Job stream exceeded timeout and was skipped.")

        deduped = self._dedupe_candidates(candidates)
        ranked = sorted(
            deduped,
            key=lambda candidate: (candidate.match_score, len(candidate.text), candidate.source == "jobs"),
            reverse=True,
        )
        self.memory.remember_search(
            roles=role_terms,
            locations=location_terms,
            companies=company_terms,
            stream=stream,
            limit=limit,
            max_hours_age=max_hours_age,
        )
        return ranked[:limit]

    def save_search_results(self, results: List[SearchCandidate], output_path: str) -> Path:
        """Save normalized search results to JSON for the agent to inspect later."""
        path = self._resolve_repo_file(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [candidate.to_dict() for candidate in results]
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def prepare_tailoring(
        self,
        *,
        job_text: str,
        cv_path: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        """Prepare the initial tailoring context bundle."""
        resolved_cv = self.resolve_cv_path(cv_path)
        cv_latex = resolved_cv.read_text(encoding="utf-8")
        pipeline = CVTailoringPipeline()
        result = pipeline.prepare(
            job_text=job_text,
            cv_latex=cv_latex,
            output_dir=output_dir or str(self.output_dir),
        )
        if result.success and result.context:
            result.context.user_profile = self.memory.get_value("profile", {}) or {}
            result.context.user_preferences = self.memory.get_value("preferences", {}) or {}
            if result.context_path:
                Path(result.context_path).write_text(
                    json.dumps(asdict(result.context), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
        return result

    def apply_tailoring(
        self,
        *,
        context_path: str,
        alignment_path: str,
        changes_path: str,
        output_path: Optional[str] = None,
    ) -> Path:
        """Apply agent-authored changes to a CV and save the tailored LaTeX."""
        context_data = json.loads(Path(context_path).read_text(encoding="utf-8"))
        alignment_data = json.loads(Path(alignment_path).read_text(encoding="utf-8"))
        changes_data = json.loads(Path(changes_path).read_text(encoding="utf-8"))
        pipeline = CVTailoringPipeline()
        tailored_path = pipeline.apply_llm_results_from_payload(
            payload=context_data,
            alignment_analysis=alignment_data,
            suggested_changes=changes_data,
            output_path=output_path,
        )
        return Path(tailored_path)

    def compile_cv(self, latex_file: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Compile a LaTeX CV into PDF."""
        resolved_latex = self._resolve_repo_file(latex_file)
        latex = resolved_latex.read_text(encoding="utf-8")
        compiler = LaTeXCompiler()
        final_output = output_path or str(resolved_latex.with_suffix(".pdf"))
        return compiler.compile_one_page(latex, final_output)

    def generate_email(
        self,
        *,
        job_title: str,
        company: str,
        location: str = "",
        recipient_email: str = "",
        recipient_name: str = "",
        cv_path: Optional[str] = None,
        cover_letter_path: Optional[str] = None,
        output_path: Optional[str] = None,
        open_mailto: bool = False,
    ) -> ApplicationEmail:
        """Create a local draft email without any external provider."""
        generator = EmailGenerator()
        sender_name = (
            self.memory.get_value("application.sender_name")
            or self.memory.get_value("profile.name")
            or "Candidate"
        )
        sender_email = (
            self.memory.get_value("application.sender_email")
            or self.memory.get_value("profile.email")
            or ""
        )
        user_summary = self.memory.get_value("application.default_summary", "")
        signature = self.memory.get_value("application.signature", "")

        email = generator.generate_application_email(
            job={
                "title": job_title,
                "company": company,
                "location": location,
            },
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            sender_name=sender_name,
            sender_email=sender_email,
            cv_path=cv_path,
            cover_letter_path=cover_letter_path,
            user_summary=user_summary,
            signature=signature,
        )

        mailto_client = MailtoClient(user_name=sender_name, user_email=sender_email)
        email.mailto_url = mailto_client.create_mailto_url(
            to=recipient_email,
            subject=email.subject,
            body=email.body,
            cc=email.cc or "",
            bcc=email.bcc or "",
        )
        if open_mailto:
            mailto_client.open_email(
                to=recipient_email,
                subject=email.subject,
                body=email.body,
                cc=email.cc or "",
                attachment_path=cv_path or "",
            )

        if output_path:
            output = self._resolve_repo_file(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(
                    {
                        "subject": email.subject,
                        "body": email.body,
                        "to": email.to,
                        "cc": email.cc,
                        "bcc": email.bcc,
                        "attachments": email.attachments,
                        "mailto_url": email.mailto_url,
                        "warnings": email.warnings,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

        return email

    def _resolve_repo_file(self, path_like: str) -> Path:
        path = Path(path_like)
        if path.is_absolute():
            return path
        return self.repo_root / path

    def _expand_roles(self, roles: List[str]) -> List[str]:
        expanded: List[str] = []
        for role in roles:
            if role in kw.ROLES:
                expanded.extend(kw.ROLES[role][:3])
            else:
                expanded.append(role)
        return _dedupe_preserve_order(expanded)

    def _expand_locations(self, locations: List[str]) -> List[str]:
        expanded: List[str] = []
        for location in locations:
            if location in kw.LOCATIONS:
                expanded.extend(kw.LOCATIONS[location][:2])
            else:
                expanded.append(location)
        return _dedupe_preserve_order(expanded)

    async def _search_posts(
        self,
        *,
        browser: BrowserManager,
        roles: List[str],
        locations: List[str],
        companies: List[str],
        limit: int,
        min_posts: int,
        timeout: int,
        max_hours_age: int,
        email_only_posts: bool,
    ) -> List[SearchCandidate]:
        searcher = HiringPostSearcher(browser.page)
        posts = await searcher.search_for_hiring(
            roles=roles[:5],
            companies=companies or None,
            locations=locations or None,
            posts_per_query=limit,
            min_posts=max(1, min(2, min_posts)),
            max_time_per_query=timeout,
            delay_between_queries=2.0,
            max_hours_age=max_hours_age,
            email_only=email_only_posts,
        )
        results: List[SearchCandidate] = []
        for post in posts:
            results.append(
                SearchCandidate(
                    source="posts",
                    url=post.linkedin_url or "",
                    query_role=roles[0] if roles else "",
                    title="Hiring Post",
                    company=post.company_name or "",
                    location=", ".join(post.locations or []),
                    locations=post.locations or [],
                    text=post.text or "",
                    posted_date=post.posted_date or "",
                    author=post.author_name or "",
                    contact_emails=post.contact_emails or [],
                    detail_level="expanded" if post.text else "summary",
                    raw_data=post.to_dict(),
                )
            )
            results[-1] = self._finalize_candidate(results[-1], roles=roles)
        return results

    async def _search_jobs(
        self,
        *,
        browser: BrowserManager,
        roles: List[str],
        locations: List[str],
        limit: int,
        timeout: int,
        expand_job_details: bool,
    ) -> List[SearchCandidate]:
        searcher = JobSearchScraper(browser.page)
        detail_scraper = JobScraper(browser.page) if expand_job_details else None
        results: List[SearchCandidate] = []
        search_locations = locations or [""]

        for role in roles[:3]:
            for location in search_locations[:3]:
                try:
                    urls = await self._await_with_timeout(
                        searcher.search(
                            keywords=role,
                            location=location or None,
                            limit=max(3, min(limit, 10)),
                        ),
                        timeout=max(6, min(timeout, 12)),
                    )
                except asyncio.TimeoutError:
                    continue
                for url in urls:
                    candidate = SearchCandidate(
                        source="jobs",
                        url=url,
                        query_role=role,
                        title=role,
                        company="",
                        location=location,
                        locations=[location] if location else [],
                        text="",
                        posted_date="",
                        detail_level="url_only",
                        raw_data={"linkedin_url": url},
                    )
                    if detail_scraper is not None:
                        try:
                            job = await self._await_with_timeout(
                                detail_scraper.scrape(url),
                                timeout=max(12, min(timeout + 2, 20)),
                            )
                            candidate.title = job.job_title or candidate.title
                            candidate.company = job.company or ""
                            candidate.location = job.location or candidate.location
                            candidate.locations = [job.location] if job.location else candidate.locations
                            candidate.text = job.job_description or ""
                            candidate.posted_date = job.posted_date or ""
                            candidate.detail_level = "expanded" if candidate.text else "summary"
                            candidate.raw_data = job.to_dict()
                        except (asyncio.TimeoutError, Exception):
                            pass
                    candidate = self._finalize_candidate(candidate, roles=roles)
                    results.append(candidate)
                    if len(results) >= limit:
                        return results
        return results

    def _dedupe_candidates(self, candidates: List[SearchCandidate]) -> List[SearchCandidate]:
        seen = set()
        deduped: List[SearchCandidate] = []
        for candidate in candidates:
            key = candidate.url or json.dumps(candidate.raw_data, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
        return deduped

    async def _await_with_timeout(self, coroutine, timeout: int):
        task = asyncio.create_task(coroutine)
        try:
            return await asyncio.wait_for(task, timeout=timeout)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except BaseException:
                pass
            raise

    def _finalize_candidate(self, candidate: SearchCandidate, *, roles: List[str]) -> SearchCandidate:
        candidate.location = self._clean_location(candidate.location, candidate.company)
        candidate.locations = [self._clean_location(location, candidate.company) for location in candidate.locations if location]
        candidate.contact_emails = _dedupe_preserve_order(candidate.contact_emails)
        clean_text = " ".join((candidate.text or "").split())
        candidate.snippet = clean_text[:240]
        if not candidate.snippet:
            parts = [
                candidate.title,
                candidate.company,
                candidate.location,
                candidate.posted_date,
                candidate.contact_emails[0] if candidate.contact_emails else "",
            ]
            candidate.snippet = " | ".join(part for part in parts if part)[:240]
        candidate.match_score, candidate.quality_flags = self._score_candidate(candidate, roles)
        if candidate.contact_emails:
            candidate.next_action = "generate_mailto_application"
        elif clean_text:
            candidate.next_action = "prepare_tailoring"
        elif candidate.source == "jobs":
            candidate.next_action = "open_job_url_for_description"
        else:
            candidate.next_action = "inspect_post_url_manually"
        return candidate

    def _clean_location(self, location: str, company: str) -> str:
        cleaned = " ".join((location or "").split())
        company_clean = " ".join((company or "").split())
        if company_clean and cleaned.startswith(company_clean):
            cleaned = cleaned[len(company_clean):].strip(" ,-")
        return cleaned

    def _score_candidate(self, candidate: SearchCandidate, roles: List[str]) -> tuple[int, List[str]]:
        score = 0
        flags: List[str] = []
        haystack = " ".join(
            [
                candidate.query_role,
                candidate.title,
                candidate.company,
                candidate.location,
                candidate.text,
            ]
        ).lower()

        for role in roles:
            role_lower = role.lower()
            tokens = [token for token in role_lower.replace("/", " ").split() if len(token) > 2]
            if role_lower in haystack or any(token in haystack for token in tokens):
                score += 25
                flags.append(f"matched:{role}")
                break

        if candidate.company:
            score += 15
            flags.append("has_company")
        if candidate.location:
            score += 10
            flags.append("has_location")
        if candidate.posted_date:
            score += 10
            flags.append("has_posted_date")
        if candidate.author:
            score += 5
            flags.append("has_author")
        if candidate.contact_emails:
            score += 15
            flags.append("has_contact_email")
        if len(candidate.text) >= 200:
            score += 20
            flags.append("rich_text")
        elif candidate.text:
            score += 10
            flags.append("has_text")
        else:
            flags.append("thin_text")
            if candidate.source == "jobs":
                flags.append("no_description")

        if candidate.detail_level:
            flags.append(f"detail:{candidate.detail_level}")
        if candidate.source == "jobs" and candidate.text:
            score += 10
            flags.append("expanded_job_details")
        elif candidate.source == "jobs" and candidate.detail_level == "url_only":
            score -= 10
            flags.append("url_only_job")
        elif candidate.source == "posts":
            score += 5
            flags.append("hiring_post_signal")

        return min(score, 100), flags
