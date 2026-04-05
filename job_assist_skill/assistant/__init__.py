"""
Career Assistant - OpenCode Skill for automated job search and CV tailoring.

This module is designed to be invoked as an opencode skill.
All LLM processing is handled by opencode; this module provides:
- Job/hiring post discovery via LinkedIn scraper
- CV tailoring preparation (prompts and data preparation)
- LaTeX to PDF compilation
- Email generation via mailto:
- Preferences with silent learning

Usage:
    from job_assist_skill.assistant import CareerAssistant
    
    assistant = CareerAssistant()
    await assistant.search(roles=["software engineer"])
    await assistant.rank_jobs()
    await assistant.tailor_cv(job_index=0)
    assistant.open_email()
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .preferences import Preferences
from .prompts_loader import get_prompt_loader
from .scrapers import HiringPostScraper, JobPostingScraper
from .pipeline import (
    JobParser, CVAlignment, CVReplacer, CoverLetterGenerator,
    LaTeXCompiler, CVDiffViewer, CVTailoringPipeline,
    EmailGenerator,
)
from .pipeline.job_parser import get_job_parser
from .pipeline.alignment import get_alignment_analyzer
from .pipeline.replacer import get_cv_replacer
from .pipeline.latex_compiler import get_compiler
from .pipeline.cv_diff_viewer import create_diff_viewer
from .ranker from job_assist_skill import keywords as kwcorer, JobRanker, get_keyword_scorer, get_job_ranker
from .email.mailto_client import MailtoClient, get_mailto_client

__all__ = [
    "CareerAssistant",
    "Preferences",
    "HiringPostScraper",
    "JobPostingScraper",
    "JobParser",
    "CVAlignment",
    "CVReplacer",
    "CoverLetterGenerator",
    "LaTeXCompiler",
    "CVDiffViewer",
    "CVTailoringPipeline",
    "EmailGenerator",
    "KeywordScorer",
    "JobRanker",
    "MailtoClient",
    "get_prompt_loader",
    "get_job_parser",
    "get_alignment_analyzer",
    "get_cv_replacer",
    "get_compiler",
    "create_diff_viewer",
    "get_keyword_scorer",
    "get_job_ranker",
    "get_mailto_client",
]


class CareerAssistant:
    """
    Main skill interface for Career Assistant.
    
    Usage:
        assistant = CareerAssistant()
        
        # Search for jobs
        await assistant.search(roles=["software engineer"], locations=["Remote"])
        
        # See ranked jobs
        assistant.print_ranked_jobs()
        
        # Tailor CV for a job
        await assistant.tailor_cv(job_index=0)
        
        # Open email
        assistant.open_email()
    """
    
    def __init__(
        self,
        cv_path: str = None,
        config_path: str = None,
        output_dir: str = "output",
    ):
        """
        Initialize Career Assistant.
        
        Args:
            cv_path: Path to user's CV LaTeX file
            config_path: Path to preferences JSON file
            output_dir: Directory for generated files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.preferences = Preferences(config_path=config_path)
        self.preferences.load()
        
        if cv_path and Path(cv_path).exists():
            self.preferences.cv_path = cv_path
            self.preferences.save()
        
        self._posts = []
        self._parsed_jobs = []
        self._ranked_jobs = []
        self._current_job_index = None
        self._tailored_cv = None
        self._email_data = None
        
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all pipeline components."""
        self.job_parser = get_job_parser()
        self.alignment_analyzer = get_alignment_analyzer()
        self.cv_replacer = get_cv_replacer()
        self.latex_compiler = get_compiler()
        self.diff_viewer = create_diff_viewer()
        self.keyword_scorer = get_keyword_scorer()
        self.mailto = get_mailto_client(
            self.preferences.name,
            self.preferences.email,
        )
        
        self.validation_status = self.validate_setup()
    
    def validate_setup(self) -> Dict[str, bool]:
        """Validate that all requirements are met."""
        import shutil
        import subprocess
        
        status = {
            "pdflatex": shutil.which("pdflatex") is not None,
            "session": Path("linkedin_session.json").exists(),
            "python": True, # Running now
        }
        
        # Verbose checking for pdflatex if missing
        if not status["pdflatex"]:
            try:
                # Check for miktex specifically if on Windows
                res = subprocess.run(["miktex", "--version"], capture_output=True)
                if res.returncode == 0:
                    status["pdflatex"] = True
            except:
                pass
                
        return status
    
    def load_cv(self) -> str:
        """Load user's CV LaTeX."""
        cv_path = self.preferences.cv_path
        if not cv_path or not Path(cv_path).exists():
            cv_path = Path("cv.tex")
        
        if not cv_path.exists():
            raise FileNotFoundError(f"CV not found: {cv_path}")
        
        return Path(cv_path).read_text(encoding="utf-8")
    
    async def search(
        self,
        roles: List[str] = None,
        locations: List[str] = None,
        max_hours_age: int = 24,
        posts_per_query: int = 10,
        stream: str = "both",
    ) -> List[Dict]:
        """
        Search LinkedIn for jobs/hiring posts.
        
        Args:
            roles: Role keywords to search
            locations: Location keywords
            max_hours_age: Only posts from last N hours
            posts_per_query: Max posts per query
            stream: 'posts', 'jobs', or 'both'
            
        Returns:
            List of found jobs
        """
        from job_assist_skill.scraper import BrowserManager
        
        self._posts = []
        self._parsed_jobs = []
        self._ranked_jobs = []
        
        roles = roles or ["software engineer"]
        locations = locations or ["Remote"]
        
        if not self.validation_status["session"]:
            print("ERROR: linkedin_session.json not found. Run 'python main.py login' first.")
            return []
            
        async with BrowserManager(stealth=True) as browser:
            try:
                await browser.load_session("linkedin_session.json")
            except Exception as e:
                print(f"ERROR loading session: {e}")
                return []
            
            if stream in ["posts", "both"]:
                post_scraper = HiringPostScraper(browser.page)
                posts = await post_scraper.search(
                    roles=roles,
                    locations=locations,
                    max_hours_age=max_hours_age,
                    posts_per_query=posts_per_query,
                )
                self._posts.extend(posts)
            
            if stream in ["jobs", "both"]:
                job_scraper = JobPostingScraper(browser.page)
                for role in roles[:3]:
                    for loc in locations[:2]:
                        jobs = await job_scraper.search(
                            keywords=role,
                            location=loc,
                            limit=posts_per_query,
                        )
                        self._posts.extend(jobs)
        
        self._deduplicate_posts()
        return self._posts
    
    def _deduplicate_posts(self):
        """Remove duplicate posts by URL."""
        seen = set()
        unique = []
        for post in self._posts:
            url = getattr(post, 'linkedin_url', None) or getattr(post, 'url', None)
            if url and url not in seen:
                seen.add(url)
                unique.append(post)
        self._posts = unique
    
    def parse_jobs(self) -> List[Dict]:
        """
        Parse job postings into structured requirements.
        
        Returns:
            List of parsed job requirements
        """
        self._parsed_jobs = []
        
        for post in self._posts:
            text = getattr(post, 'text', None) or ""
            if len(text) < 50:
                continue
            
            parsed = self.job_parser.parse(text)
            parsed["_source_post"] = post
            parsed["_url"] = getattr(post, 'linkedin_url', None) or getattr(post, 'url', None)
            parsed["_author"] = getattr(post, 'author_name', None) or ""
            self._parsed_jobs.append(parsed)
        
        return self._parsed_jobs
    
    def rank_jobs(self) -> List[Dict]:
        """
        Rank parsed jobs by keyword match score.
        
        Returns:
            Ranked list of jobs with scores
        """
        if not self._parsed_jobs:
            self.parse_jobs()
        
        user_skills = self._extract_user_skills()
        self.keyword_scorer.update_user_skills(user_skills)
        
        self._ranked_jobs = self.keyword_scorer.rank_jobs(self._parsed_jobs)
        
        for i, item in enumerate(self._ranked_jobs):
            item["job"]["_rank"] = i + 1
        
        return self._ranked_jobs
    
    def _extract_user_skills(self) -> List[str]:
        """Extract skills from user's CV."""
        try:
            cv = self.load_cv()
            import re
            skills_section = re.search(r'\\skills{(.*?)}', cv, re.DOTALL)
            if skills_section:
                items = re.findall(r'\\item\s+(.+?)(?:\\|$)', skills_section.group(1))
                return [item.strip() for item in items if item.strip()]
        except:
            pass
        return self.preferences.preferred_skills or []
    
    def print_ranked_jobs(self, limit: int = 10) -> None:
        """Print ranked jobs to console."""
        if not self._ranked_jobs:
            self.rank_jobs()
        
        print()
        print("=" * 70)
        print("  JOBS RANKED BY KEYWORD MATCH")
        print("=" * 70)
        
        for item in self._ranked_jobs[:limit]:
            job = item["job"]
            score = item["match_score"]
            
            author = job.get("_author", "")
            title = job.get("title", "Unknown")
            company = job.get("company", "")
            url = job.get("_url", "")
            required = job.get("required_skills", [])
            
            print(f"\n[{item['job']['_rank']}] [{score}%] {title} @ {company}")
            if author:
                print(f"    Posted by: {author}")
            if required:
                print(f"    Required: {', '.join(required[:5])}")
            if url:
                print(f"    URL: {url[:70]}...")
    
    async def tailor_cv(
        self,
        job_index: int = 0,
        show_diff: bool = True,
    ) -> Dict[str, Any]:
        """
        Tailor CV for a specific job.
        
        Args:
            job_index: Index of job in ranked list
            show_diff: Whether to show diff and wait for approval
            
        Returns:
            Tailoring result with tailored CV
        """
        if not self._ranked_jobs:
            self.rank_jobs()
        
        if job_index >= len(self._ranked_jobs):
            raise IndexError(f"Job index {job_index} out of range")
        
        self._current_job_index = job_index
        job = self._ranked_jobs[job_index]["job"]
        
        cv_latex = self.load_cv()
        parsed_job = job
        
        alignment = self.alignment_analyzer.analyze(parsed_job, cv_latex)
        
        changes = self.cv_replacer.generate_changes(cv_latex, alignment)
        
        critical_changes = [
            c for c in changes
            if c.get("importance", "").lower() == "critical"
            and c.get("change_type") != "keep"
        ]
        
        tailored_cv = self.cv_replacer.apply_changes(cv_latex, critical_changes)
        
        self._tailored_cv = tailored_cv
        self._current_job = job
        self._current_alignment = alignment
        self._current_changes = critical_changes
        
        if show_diff:
            self._show_diff_for_approval()
        
        return {
            "original_cv": cv_latex,
            "tailored_cv": tailored_cv,
            "changes": critical_changes,
            "alignment": alignment,
        }
    
    def _show_diff_for_approval(self) -> None:
        """Show diff and get user approval."""
        job = self._current_job
        alignment = self._current_alignment
        changes = self._current_changes
        
        score_before = int(alignment.get("overall_score", 0))
        score_after = int(alignment.get("alignment_improvement", {}).get("after", score_before))
        
        diff = self.diff_viewer.show_diff(
            original_cv=self.load_cv(),
            tailored_cv=self._tailored_cv,
            changes=changes,
            job_title=job.get("title", ""),
            company=job.get("company", ""),
            score_before=score_before,
            score_after=score_after,
        )
        
        self.diff_viewer.print_diff(diff)
        
        response = self.diff_viewer.ask_approval()
        
        if response in ["n", "no"]:
            self._tailored_cv = self.load_cv()
        elif response == "edit":
            print("Edit mode not yet implemented - using suggested changes")
        elif response in ["y", "yes"]:
            pass
        else:
            print(f"Unknown response '{response}' - using suggested changes")
    
    def compile_pdf(self, cv_latex: str = None, output_name: str = None) -> str:
        """
        Compile CV to PDF.
        
        Args:
            cv_latex: CV LaTeX (uses current if None)
            output_name: Output filename
            
        Returns:
            Path to compiled PDF
        """
        cv = cv_latex or self._tailored_cv or self.load_cv()
        
        if not output_name:
            company = self._current_job.get("company", "cv") if self._current_job else "cv"
            output_name = f"{company.replace(' ', '_')}_cv.pdf"
        
        output_path = self.output_dir / output_name
        result = self.latex_compiler.compile_one_page(cv, str(output_path))
        
        if result.get("success"):
            return str(output_path)
        else:
            raise RuntimeError(f"PDF compilation failed: {result.get('issues')}")
    
    def create_email(self, to: str, subject: str = None, body: str = None) -> Dict:
        """
        Create email data.
        
        Args:
            to: Recipient email
            subject: Email subject (auto-generated if None)
            body: Email body (auto-generated if None)
            
        Returns:
            Email data dict
        """
        if not subject:
            job = self._current_job or {}
            # ELITE DATA VALIDATION: Reject generic mock strings
            raw_title = job.get("title", "")
            title = raw_title if raw_title and "Position" not in raw_title else "AI Engineering"
            
            raw_company = job.get("company", "")
            company = raw_company if raw_company and "Company_" not in raw_company else ""
            
            subject = f"Application for {title}"
            if company:
                subject += f" at {company}"
        
        if not body:
            job = self._current_job or {}
            body = self.mailto.format_email_body(
                job_title=job.get("title", ""),
                company=job.get("company", ""),
                recruiter_name=job.get("_author", ""),
            )
        
        pdf_path = None
        try:
            pdf_path = self.compile_pdf()
        except:
            pass
        
        self._email_data = {
            "to": to,
            "subject": subject,
            "body": body,
            "attachment": pdf_path,
        }
        
        return self._email_data
    
    def open_email(self, to: str = None) -> bool:
        """
        Open email client with pre-filled email.
        
        Args:
            to: Recipient email (prompts if None)
            
        Returns:
            True if successful
        """
        if not to:
            to = input("Enter recipient email: ").strip()
        
        if not self._email_data:
            job = self._current_job or {}
            title = job.get("title", "Position")
            company = job.get("company", "")
            self.create_email(to=to)
        
        email_data = self._email_data
        
        return self.mailto.open_email(
            to=to or email_data.get("to", ""),
            subject=email_data.get("subject", ""),
            body=email_data.get("body", ""),
            attachment_path=email_data.get("attachment"),
        )
    
    def save_email_json(self, filepath: str = None) -> str:
        """Save email data to JSON."""
        if not filepath:
            filepath = self.output_dir / "email.json"
        
        if not self._email_data:
            raise ValueError("No email data. Call create_email() first.")
        
        return self.mailto.save_email_json(
            filepath=str(filepath),
            **self._email_data,
        )
    
    def update_preferences_from_decision(
        self,
        decision: str,
        job_index: int = None,
    ) -> None:
        """
        Update preferences based on user decision.
        
        Args:
            decision: 'approved' or 'rejected'
            job_index: Index of job (uses current if None)
        """
        if job_index is None:
            job_index = self._current_job_index
        
        if job_index is not None and job_index < len(self._ranked_jobs):
            job = self._ranked_jobs[job_index]["job"]
            
            decision_data = {
                "preferred_locations": job.get("locations", []),
                "preferred_skills": job.get("required_skills", []),
            }
            
            self.preferences.update_from_decision(decision_data)
    
    def get_onboarding_prompt(self) -> str:
        """Get onboarding prompt for new users."""
        return """
=== Career Assistant - First Time Setup ===

I need a few things to get started:

1. Your CV (LaTeX format)
   - Path to your CV file (e.g., ./my_cv.tex)
   - Or provide your skills list

2. Your name and email
   - For the application emails

3. Job preferences (optional)
   - Preferred locations (Remote, Dubai, Riyadh, etc.)
   - Role types you're interested in

Once set up, just say "find me jobs" and I'll:
1. Search LinkedIn for relevant hiring posts
2. Rank them by keyword match to your skills
3. Tailor your CV for each one you approve
4. Help you send application emails

Let's get started!
"""


def create_assistant(**kwargs) -> CareerAssistant:
    """Create and return a CareerAssistant instance."""
    return CareerAssistant(**kwargs)
