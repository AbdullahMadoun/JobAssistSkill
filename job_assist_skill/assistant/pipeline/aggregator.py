"""
Multi-Source Job Candidate Aggregator.

Collects job candidates from:
1. LinkedIn job search
2. LinkedIn post search (hiring posts)
3. Google dorking (site:linkedin.com "hiring")

Deduplicates and normalizes results into JobCandidate model.
"""

import asyncio
import hashlib
import re
from datetime import datetime
from typing import Dict, List, Optional, Set, Literal
from dataclasses import dataclass, field
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


@dataclass
class JobCandidate:
    """
    Normalized job candidate from any source.
    """
    source: Literal["linkedin_jobs", "linkedin_posts", "google_dork"]
    url: str
    candidate_id: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    snippet: str = ""
    linkedin_url: str = ""
    collected_at: datetime = field(default_factory=datetime.now)
    llm_score: float = 0.0
    status: Literal["pending", "approved", "rejected", "applied"] = "pending"
    raw_data: Dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.candidate_id:
            self.candidate_id = self._generate_id()

    def _generate_id(self) -> str:
        """Generate unique ID from URL."""
        url_hash = hashlib.md5(self.url.encode()).hexdigest()[:12]
        return f"{self.source}_{url_hash}"

    @property
    def display_title(self) -> str:
        """Human-readable title."""
        if self.title:
            return f"{self.title} at {self.company}" if self.company else self.title
        if self.company:
            return f"Hiring post from {self.company}"
        return "Unknown position"


class MultiSourceAggregator:
    """
    Aggregates job candidates from multiple sources.

    Usage:
        aggregator = MultiSourceAggregator(page, feedback_store)
        candidates = await aggregator.collect(
            roles=["software engineer"],
            companies=["microsoft"],
            locations=["San Francisco"],
        )
    """

    def __init__(
        self,
        page,  # Playwright page
        feedback_store=None,  # FeedbackStore instance
        max_per_source: int = 15,
    ):
        """
        Initialize aggregator.

        Args:
            page: Playwright page object
            feedback_store: Optional FeedbackStore for filtering already-seen candidates
            max_per_source: Maximum candidates to collect per source
        """
        self.page = page
        self.feedback_store = feedback_store
        self.max_per_source = max_per_source

    async def collect(
        self,
        roles: Optional[List[str]] = None,
        companies: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        include_jobs: bool = True,
        include_posts: bool = True,
        include_google: bool = True,
    ) -> List[JobCandidate]:
        """
        Collect job candidates from all enabled sources.

        Args:
            roles: Job titles/roles to search for
            companies: Companies to search
            locations: Locations to include
            include_jobs: Include LinkedIn job search
            include_posts: Include LinkedIn post search
            include_google: Include Google dorking

        Returns:
            Deduplicated list of JobCandidates
        """
        all_candidates: List[JobCandidate] = []
        seen_ids: Set[str] = set()

        if include_jobs:
            jobs = await self._collect_linkedin_jobs(roles, locations)
            for c in jobs:
                if c.candidate_id not in seen_ids:
                    seen_ids.add(c.candidate_id)
                    all_candidates.append(c)

        if include_posts:
            posts = await self._collect_linkedin_posts(roles, companies)
            for c in posts:
                if c.candidate_id not in seen_ids:
                    seen_ids.add(c.candidate_id)
                    all_candidates.append(c)

        if include_google:
            dorks = await self._collect_google_dorks(roles, companies)
            for c in dorks:
                if c.candidate_id not in seen_ids:
                    seen_ids.add(c.candidate_id)
                    all_candidates.append(c)

        if self.feedback_store:
            all_candidates = self._filter_known_decisions(all_candidates)

        return all_candidates

    async def _collect_linkedin_jobs(
        self,
        roles: Optional[List[str]],
        locations: Optional[List[str]],
    ) -> List[JobCandidate]:
        """Collect from LinkedIn job search."""
        try:
            from job_assist_skill.scraper import JobSearchScraper, JobScraper

            scraper = JobSearchScraper(self.page)
            candidates = []

            search_roles = roles[:3] if roles else ["software engineer"]
            search_locs = locations[:2] if locations else ["Remote"]

            for role in search_roles:
                for loc in search_locs:
                    try:
                        job_urls = await scraper.search(
                            keywords=role,
                            location=loc,
                            limit=self.max_per_source // 2,
                        )

                        for url in job_urls:
                            candidate = JobCandidate(
                                source="linkedin_jobs",
                                url=url,
                                title=role,
                                location=loc,
                                linkedin_url=url,
                            )
                            candidates.append(candidate)

                            await asyncio.sleep(1)

                    except Exception as e:
                        logger.warning(f"Job search error for {role}/{loc}: {e}")

            return candidates

        except Exception as e:
            logger.error(f"Error collecting LinkedIn jobs: {e}")
            return []

    async def _collect_linkedin_posts(
        self,
        roles: Optional[List[str]],
        companies: Optional[List[str]],
    ) -> List[JobCandidate]:
        """Collect from LinkedIn post search."""
        try:
            from job_assist_skill.scraper import HiringPostSearcher

            searcher = HiringPostSearcher(self.page)
            posts = await searcher.search_for_hiring(
                roles=roles,
                companies=companies,
                locations=None,
                posts_per_query=self.max_per_source // 3,
            )

            candidates = []
            for post in posts:
                if post.linkedin_url:
                    company = self._extract_company_from_post(post.text or "")

                    candidate = JobCandidate(
                        source="linkedin_posts",
                        url=post.linkedin_url,
                        title=self._extract_role_from_post(post.text or "", company),
                        company=company,
                        snippet=post.text[:200] if post.text else "",
                        linkedin_url=post.linkedin_url,
                        raw_data={"post_text": post.text, "reactions": post.reactions_count},
                    )
                    candidates.append(candidate)

            return candidates

        except Exception as e:
            logger.error(f"Error collecting LinkedIn posts: {e}")
            return []

    async def _collect_google_dorks(
        self,
        roles: Optional[List[str]],
        companies: Optional[List[str]],
    ) -> List[JobCandidate]:
        """Collect from Google dorking."""
        try:
            candidates = []

            queries = self._build_dork_queries(roles, companies)

            for query in queries[:5]:
                try:
                    results = await self._search_google(query)
                    for result in results:
                        candidate = JobCandidate(
                            source="google_dork",
                            url=result['url'],
                            title=result.get('title', ''),
                            snippet=result.get('snippet', ''),
                            linkedin_url=result['url'],
                            raw_data={'query': query},
                        )
                        candidates.append(candidate)

                    await asyncio.sleep(3)

                except Exception as e:
                    logger.warning(f"Google dork error for query '{query}': {e}")

            return candidates

        except Exception as e:
            logger.error(f"Error collecting Google dorks: {e}")
            return []

    async def _search_google(self, query: str) -> List[Dict]:
        """Search Google and extract LinkedIn results."""
        results = []

        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"

        try:
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)

            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
            await asyncio.sleep(1)

            search_results = await self.page.query_selector_all("div.g")

            for result in search_results[:10]:
                try:
                    link_elem = await result.query_selector("a")
                    if not link_elem:
                        continue

                    href = await link_elem.get_attribute("href")
                    if not href or 'linkedin.com' not in href:
                        continue

                    title_elem = await result.query_selector("h3")
                    title = await title_elem.inner_text() if title_elem else ""

                    snippet_elem = await result.query_selector("div[data-sncf]")
                    snippet = await snippet_elem.inner_text() if snippet_elem else ""

                    parsed = urlparse(href)
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

                    results.append({
                        'url': clean_url,
                        'title': title,
                        'snippet': snippet[:200],
                    })

                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"Google search error: {e}")

        return results

    def _build_dork_queries(
        self,
        roles: Optional[List[str]],
        companies: Optional[List[str]],
    ) -> List[str]:
        """Build Google dorking queries."""
        queries = []

        if roles:
            for role in roles[:3]:
                queries.append(f'site:linkedin.com "{role}" "hiring"')
                queries.append(f'site:linkedin.com "{role}" "we\'re hiring"')
                queries.append(f'site:linkedin.com "{role}" "open position"')

        if companies:
            for company in companies[:3]:
                queries.append(f'site:linkedin.com/company "{company}" "hiring"')
                queries.append(f'site:linkedin.com "{company}" "join our team"')

        queries.append('site:linkedin.com "we\'re hiring" "remote"')
        queries.append('site:linkedin.com "now hiring" "software"')

        return list(dict.fromkeys(queries))

    def _extract_company_from_post(self, text: str) -> str:
        """Extract company name from post text."""
        lines = text.split('\n')
        for line in lines[:3]:
            line = line.strip()
            if line and len(line) < 100 and not line.startswith('http'):
                return line
        return ""

    def _extract_role_from_post(self, text: str, company: str) -> str:
        """Extract job role from post text."""
        text_lower = text.lower()

        role_patterns = [
            r'(?:hiring|looking for|seeking)\s+(?:a\s+)?(.+?)(?:\s+at\s+|\s+to\s+|\s+for\s+)',
            r'(?:join our team|we\'re hiring)\s+(?:as\s+)?(?:a\s+)?(.+?)(?:\s+at\s+|\s+,)',
            r'(?:open|available)\s+(?:position\s+)?(?:for\s+)?(?:a\s+)?(.+?)(?:\s+at\s+|\s+in\s+)',
        ]

        for pattern in role_patterns:
            match = re.search(pattern, text_lower)
            if match:
                role = match.group(1).strip()
                if len(role) > 3 and len(role) < 80:
                    return role.title()

        return "Hiring"

    def _filter_known_decisions(self, candidates: List[JobCandidate]) -> List[JobCandidate]:
        """Filter out candidates that were already approved/rejected."""
        if not self.feedback_store:
            return candidates

        filtered = []
        for c in candidates:
            if self.feedback_store.is_candidate_approved(c.candidate_id):
                c.status = "approved"
            elif self.feedback_store.is_candidate_rejected(c.candidate_id):
                c.status = "rejected"
            filtered.append(c)

        return filtered
