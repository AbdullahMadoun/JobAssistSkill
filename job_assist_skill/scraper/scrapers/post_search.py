"""
LinkedIn Post Search Scraper - Production Grade.

Extracts hiring-related content from LinkedIn search results.
Handles both feed posts (urn:li:activity:) and job postings from content search.

Key features:
- Advanced stealth with canvas fingerprinting, WebGL, and automation detection bypass
- Text-based extraction using semantic HTML structure analysis
- Human-like behavior: randomized delays, smooth scrolling, mouse movements
- Configurable min_posts and max_time constraints
- Works with authenticated sessions
"""

import asyncio
import hashlib
import logging
import random
import re
import time
from typing import List, Optional, Set, Callable, Dict, Any
from urllib.parse import urlparse, parse_qs
from playwright.async_api import Page

from ..callbacks import ProgressCallback, SilentCallback
from ..models.post import Post
from ..utils import MetadataCleaner
from .base import BaseScraper

logger = logging.getLogger(__name__)

HIRING_KEYWORDS = [
    "we're hiring", "we are hiring", "now hiring", "join our team",
    "looking for", "open position", "job opening", "hiring soon",
    "career opportunity", "recruiting", "vacancy", "#hiring",
]


class PostSearchScraper(BaseScraper):
    """
    Production-grade scraper for LinkedIn search results.

    Extracts hiring-related content from:
    - Job postings in content search results
    - Feed posts (urn:li:activity:) when available
    - Company posts scraped from specific URLs

    Uses text-based extraction for robustness against DOM changes.
    """

    LOCATION_PATTERNS = [
        r'\b(Riyadh|Jeddah|Dammam|Mecca|Medina|Khobar)\b',
        r'\b(Abu Dhabi|Dubai|Sharjah|Ajman)\b',
        r'\bRemote\b',
        r'\bHybrid\b',
        r'\bOn-site\b',
        r'\b(Kuwait|Qatar|Bahrain|Oman)\b',
        r'\b(USA|UK|Canada|Australia|Germany|France|Spain)\b',
        r'\b(New York|San Francisco|Los Angeles|Seattle|Boston)\b',
        r'\b(London|Manchester|Edinburgh)\b',
        r'\b(Singapore|Hong Kong|Tokyo|Seoul)\b',
        r'\b\d+%\s*(Remote|Hybrid)\b',
        r'\b(WFH|Work from home)\b',
    ]

    TIME_PATTERNS = [
        (r'(\d+)\s*min', 1, 1/60),
        (r'(\d+)\s*hour', 1, 1),
        (r'(\d+)\s*day', 1, 24),
        (r'(\d+)\s*week', 1, 7 * 24),
        (r'(\d+)\s*w', 1, 7 * 24),
        (r'yesterday', 1, 24),
        (r'just now', 0, 0.5),
        (r'last week', 7 * 24, None),
    ]

    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None, max_hours_age: int = 24):
        super().__init__(page, callback or SilentCallback())
        self.max_hours_age = max_hours_age

    async def search(
        self,
        keywords: str,
        limit: int = 25,
        filter_hiring: bool = True,
        min_posts: int = 5,
        max_time_seconds: int = 180,
        scroll_pause_min: float = 0.8,
        scroll_pause_max: float = 1.8,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        max_hours_age: Optional[int] = None,
    ) -> List[Post]:
        """
        Search for hiring-related content.

        Args:
            keywords: Search keywords (e.g., "software engineer hiring")
            limit: Maximum posts to return
            filter_hiring: Only return posts with hiring keywords
            min_posts: Minimum posts to collect before stopping
            max_time_seconds: Hard time limit
            scroll_pause_min: Min pause between scrolls
            scroll_pause_max: Max pause between scrolls
            progress_callback: Progress callback function
            max_hours_age: Only return posts from last N hours (None = no filter)

        Returns:
            List of Post objects
        """
        if max_hours_age is not None:
            self.max_hours_age = max_hours_age
        start_time = time.time()
        search_url = self._build_search_url(keywords)

        await self.callback.on_start("PostSearch", search_url)

        try:
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            logger.warning(f"Navigation issue: {e}")

        await asyncio.sleep(7)

        await self.callback.on_progress("Page loaded", 10)

        seen_urls: Set[str] = set()
        all_posts: List[Post] = []
        scroll_count = 0
        consecutive_empty = 0

        while len(all_posts) < limit:
            elapsed = time.time() - start_time
            if elapsed > max_time_seconds:
                logger.info(f"Time limit reached: {elapsed:.1f}s")
                break

            if len(all_posts) >= min_posts and consecutive_empty >= 2:
                logger.info(f"Got {len(all_posts)} posts, stopping")
                break

            posts = await self._extract_posts_from_page(seen_urls)

            if filter_hiring:
                posts = [p for p in posts if self._is_hiring_post(p.text or "")]

            new_count = 0
            for post in posts:
                if post.linkedin_url and post.linkedin_url not in seen_urls:
                    seen_urls.add(post.linkedin_url)
                    all_posts.append(post)
                    new_count += 1
                    if len(all_posts) >= limit:
                        break

            if new_count == 0:
                consecutive_empty += 1
            else:
                consecutive_empty = 0

            scroll_count += 1

            if progress_callback:
                progress_callback(len(all_posts), limit,
                    f"Scroll {scroll_count}: found {len(all_posts)}, empty={consecutive_empty}")

            if len(all_posts) < limit:
                await self._human_scroll_and_wait(scroll_pause_min, scroll_pause_max)

        await self.callback.on_progress(f"Found {len(all_posts)} posts", 90)
        await self.callback.on_complete("PostSearch", all_posts)

        return all_posts[:limit]

    def _build_search_url(self, keywords: str) -> str:
        """Build LinkedIn content search URL."""
        base = "https://www.linkedin.com/search/results/content/"
        from urllib.parse import urlencode
        return f"{base}?{urlencode({'keywords': keywords})}"

    async def _extract_posts_from_page(self, seen_urls: Set[str]) -> List[Post]:
        """Extract posts using text-based semantic analysis."""
        posts_data = await self.page.evaluate(self._EXTRACTION_JS)

        posts: List[Post] = []
        for data in posts_data:
            url = data.get('url', '')
            text = data.get('text', '')
            time_text = data.get('timeText', '')

            if not text or len(text) < 30 or not url:
                continue

            if url in seen_urls:
                continue

            if not self._is_recent_enough(time_text):
                continue

            locations = self._extract_locations(text)

            # Extract author name from URL if not found or generic
            author_name = data.get('authorName', '')
            if MetadataCleaner.is_generic_author(author_name) and url:
                author_name = MetadataCleaner.extract_name_from_url(url)

            author_url = data.get('authorUrl', '')
            if not author_url and url:
                author_url = self._extract_profile_url_from_post_url(url)

            # Clean URN from URL if possible
            urn = data.get('urn')
            if not urn and '/feed/update/urn:li:activity:' in url:
                urn = url.split(':')[-1].strip('/')

            post = Post(
                linkedin_url=url,
                urn=urn,
                text=text[:3000],
                posted_date=time_text,
                reactions_count=self._parse_count(data.get('reactions', '')),
                comments_count=self._parse_count(data.get('comments', '')),
                reposts_count=self._parse_count(data.get('reposts', '')),
                image_urls=data.get('images', []),
                author_name=author_name,
                author_url=author_url,
                company_name=MetadataCleaner.clean_company_name(data.get('companyName', '')),
                locations=locations,
            )
            posts.append(post)

        for post in posts:
            if MetadataCleaner.is_generic_author(post.author_name):
                url = post.linkedin_url or post.author_url
                slug_name = MetadataCleaner.extract_name_from_url(url)
                if slug_name:
                    post.author_name = slug_name
        
        return posts

    _EXTRACTION_JS = r'''
    () => {
        const results = [];
        const seenUrls = new Set();

        const cleanUrl = (url) => {
            if (!url) return '';
            return url.split('?')[0].split('#')[0].replace(/\/$/, '');
        };

        // 1. Extract generic Feed Posts (modern Search results structure)
        const listItems = document.querySelectorAll('div[role="listitem"], .feed-shared-update-v2, [data-urn*="urn:li:activity:"]');
        
        listItems.forEach(el => {
            // Identify if this is a post container
            const isPost = el.innerText.includes('Feed post') || 
                           el.querySelector('[data-testid="expandable-text-box"]') ||
                           el.getAttribute('data-urn')?.includes('urn:li:activity:');
            
            if (!isPost) return;

            // Extract text - high reliability selector
            let textEl = el.querySelector('[data-testid="expandable-text-box"], .feed-shared-text, .update-components-text, [class*="description"]');
            let text = textEl ? textEl.innerText : el.innerText;
            text = text.replace(/see more/gi, '').replace(/\s+/g, ' ').trim();
            if (text.length < 30) return;

            // Extract author name and URL
            let authorName = '';
            let authorUrl = '';
            let companyName = '';
            
            // Look for author in various selectors
            const authorSelectors = [
                '.feed-shared-actor__name',
                '.update-components-actor__name', 
                '[class*="actor__name"]',
                '[class*="author__name"]',
                'span[class*="name"][class*="headline"]',
                '.attributed-text-segment__content'
            ];
            
            for (const sel of authorSelectors) {
                const nameEl = el.querySelector(sel);
                if (nameEl && !authorName) {
                    authorName = nameEl.innerText?.trim() || '';
                    if (authorName.length > 50) authorName = authorName.substring(0, 50);
                }
            }
            
            // Fallback: get from text if not found separately
            if (!authorName) {
                const textLines = text.split('\n').filter(l => l.trim().length > 0 && l.trim().length < 50);
                if (textLines.length > 0) {
                    authorName = textLines[0].trim();
                }
            }
            
            // Extract author profile URL
            const authorLinkEl = el.querySelector('a[href*="/in/"]:not([href*="/jobs/"])');
            if (authorLinkEl) {
                authorUrl = cleanUrl(authorLinkEl.href);
            }
            
            // Fallback: extract author name from URL if not found
            if (!authorName && authorUrl) {
                const urlMatch = authorUrl.match(/\/in\/([a-zA-Z0-9_-]+)/);
                if (urlMatch) {
                    authorName = urlMatch[1].replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                }
            }
            
            // Extract company name (often after author name in job posts)
            const companySelectors = [
                '[class*="company__name"]',
                '[class*="company-name"]',
                '.feed-shared-actor__sub-description',
                '[class*="sub-description"]',
                '[class*="actor__sub-description"]'
            ];
            
                    // Clean remaining junk (time, mutual connections, etc.)
                    // MetadataCleaner is accessible in JS context if passed, but for now we'll 
                    // use the Python-side cleaner after extraction for ultimate precision.
                    companyName = co;

            // Extract URN/URL
            let urn = el.getAttribute('data-urn') || '';
            let url = '';
            
            const linkEl = el.querySelector('a[href*="/feed/update/"], a[href*="/jobs/view/"]');
            if (linkEl) {
                url = cleanUrl(linkEl.href);
            } else if (urn) {
                url = `https://www.linkedin.com/feed/update/${urn}`;
            } else if (authorUrl) {
                url = authorUrl + "/detail/recent-activity/";
            }

            if (!url || seenUrls.has(url)) return;
            seenUrls.add(url);

            // Extract metrics
            let reactions = '', comments = '', reposts = '';
            el.querySelectorAll('button, span, [class*="count"]').forEach(item => {
                const label = item.getAttribute('aria-label') || item.innerText || '';
                if (/\d+\s*reaction/i.test(label)) reactions = label;
                else if (/\d+\s*comment/i.test(label)) comments = label;
                else if (/\d+\s*repost/i.test(label)) reposts = label;
            });

            // Extract time
            const timeEl = el.querySelector('time, [class*="time"], [class*="date"]');
            const timeText = timeEl ? (timeEl.getAttribute('datetime') || timeEl.innerText) : '';

            results.push({
                url,
                urn,
                text: text.substring(0, 3000),
                timeText,
                reactions,
                comments,
                reposts,
                images: [],
                authorName,
                authorUrl,
                companyName
            });
        });

        // 2. Extract direct Jobs links if not caught by listItems
        document.querySelectorAll('a[href*="/jobs/view/"]').forEach(link => {
            const url = cleanUrl(link.href);
            if (!url || seenUrls.has(url)) return;

            const parent = link.closest('li, article, div[class*="job"], div[class*="card"]');
            if (!parent) return;

            let text = parent.innerText.replace(/see more/gi, '').replace(/\s+/g, ' ').trim();
            
            // Extract company name from job cards
            let companyName = '';
            let authorName = '';
            const coSelectors = [
                '[class*="company-name"]',
                '[class*="company__name"]',
                'strong[class*="company"]',
                '.job-card-container__company-name'
            ];
            for (const sel of coSelectors) {
                const coEl = parent.querySelector(sel);
                if (coEl && !companyName) {
                    companyName = coEl.innerText?.trim() || '';
                }
            }
            
            // Extract author/recruiter name if available
            const authorSelectors = [
                '[class*="actor__name"]',
                '[class*="recruiter"]',
                '.job-card-container__title'
            ];
            for (const sel of authorSelectors) {
                const authEl = parent.querySelector(sel);
                if (authEl && !authorName) {
                    authorName = authEl.innerText?.trim() || '';
                }
            }
            
            seenUrls.add(url);
            results.push({
                url,
                text: text.substring(0, 3000),
                timeText: '',
                reactions: '',
                comments: '',
                reposts: '',
                images: [],
                authorName,
                authorUrl: '',
                companyName
            });
        });

        return results;
    }
    '''

    async def _human_scroll_and_wait(self, pause_min: float, pause_max: float) -> None:
        """Human-like scroll with randomized behavior - optimized for speed."""
        await asyncio.sleep(random.uniform(pause_min, pause_max))

        viewport_h = await self.page.evaluate('window.innerHeight')
        scroll_h = await self.page.evaluate('document.documentElement.scrollHeight')
        current_y = await self.page.evaluate('window.pageYOffset')

        if current_y >= scroll_h - viewport_h - 100:
            await self.page.evaluate('window.scrollTo(0, 0)')
            await asyncio.sleep(0.3)
            return

        steps = random.randint(2, 4)
        for i in range(steps):
            target = (scroll_h * (i + 1)) / (steps + 1)
            await self.page.evaluate(f'''
                window.scrollTo({{
                    top: {target},
                    behavior: 'smooth'
                }})
            ''')
            await asyncio.sleep(random.uniform(0.15, 0.35))

        await asyncio.sleep(random.uniform(pause_min * 0.6, pause_max * 0.6))

    def _is_hiring_post(self, text: str) -> bool:
        """Check if text contains hiring-related keywords."""
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in HIRING_KEYWORDS)

    def _parse_time_hours(self, time_text: str) -> Optional[float]:
        """Parse time text and return hours ago. Returns None if too old or unparseable."""
        if not time_text:
            return None
        
        time_lower = time_text.lower().strip()
        
        for pattern, hours, _ in self.TIME_PATTERNS:
            match = re.search(pattern, time_lower)
            if match:
                if hours is None:
                    return None
                if hours == 0 and pattern == r'just now':
                    return 0.5
                return hours * float(match.group(1)) if match.groups() else hours
        
        return None

    def _is_recent_enough(self, time_text: str) -> bool:
        """Check if post is within the max age threshold."""
        if not time_text:
            return True
        
        hours_ago = self._parse_time_hours(time_text)
        if hours_ago is None:
            return True
        
        return hours_ago <= self.max_hours_age

    def _extract_locations(self, text: str) -> List[str]:
        """Extract location/geography mentions from post text."""
        locations = []
        text_lower = text.lower()
        
        for pattern in self.LOCATION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                loc = match.group(0)
                if loc.lower() not in [l.lower() for l in locations]:
                    locations.append(loc)
        
        return locations

    def _extract_name_from_url(self, url: str) -> str:
        """Extract author name from LinkedIn profile URL.
        
        URL patterns:
        - linkedin.com/in/username/detail/recent-activity/
        - linkedin.com/in/first-last-12345/
        
        Returns only the alphabetic name part, not the numeric ID.
        """
        if not url:
            return ''
        
        # Handle various profile and post URL formats
        match = re.search(r'/(in|pub|comm|posts)/([a-zA-Z0-9_-]+)/?', url)
        if match:
            username = match.group(2)
            if username in ['in', 'posts', 'pub', 'comm']:
                return ''
            
            # Remove trailing numbers/IDs (e.g., -787b62358)
            username = re.sub(r'-[0-9a-f]{5,15}/?$', '', username)
            
            # If it's a post slug, it might contain keywords like 'hiring-ai-engineer'
            # We want to extract the first part if it looks like a name
            parts = username.split('-')
            # Filter out short parts or purely numeric parts
            name_parts = [p for p in parts if len(p) > 1 and not p.isdigit()]
            
            if name_parts:
                return ' '.join(name_parts).title()
            return username.replace('-', ' ').replace('_', ' ').title()
        return ''

    def _extract_profile_url_from_post_url(self, post_url: str) -> str:
        """Extract profile URL from post URL.
        
        From: linkedin.com/in/username/detail/recent-activity/
        To:   linkedin.com/in/username/
        """
        if not post_url:
            return ''
        
        match = re.search(r'(linkedin\.com/in/[a-zA-Z0-9_-]+)', post_url)
        if match:
            return match.group(1) + '/'
        return ''

    def _parse_count(self, text: str) -> Optional[int]:
        """Parse integer from text like '42 reactions'."""
        if not text:
            return None
        try:
            numbers = re.findall(r'[\d,]+', text.replace(',', ''))
            return int(numbers[0]) if numbers else None
        except:
            return None


class HiringPostSearcher:
    """
    Multi-query hiring post search with rate limiting.
    """

    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        self.scraper = PostSearchScraper(page, callback)

    async def search_for_hiring(
        self,
        roles: Optional[List[str]] = None,
        companies: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        posts_per_query: int = 10,
        min_posts: int = 5,
        max_time_per_query: int = 90,
        delay_between_queries: float = 5.0,
        max_hours_age: Optional[int] = None,
    ) -> List[Post]:
        """
        Search for hiring posts across multiple queries.

        Args:
            roles: Job titles to search for
            companies: Specific companies to search
            locations: Locations to include
            posts_per_query: Max posts per query
            min_posts: Minimum total posts to collect
            max_time_per_query: Max time per query
            delay_between_queries: Delay between queries
            max_hours_age: Only return posts from last N hours

        Returns:
            Combined list of hiring posts
        """
        queries = self._build_queries(roles, companies, locations)

        all_posts: List[Post] = []
        seen_urls: Set[str] = set()
        total_time = 0

        for query in queries:
            if total_time > 600:
                break

            posts = await self.scraper.search(
                keywords=query,
                limit=posts_per_query,
                filter_hiring=True,
                min_posts=min(3, posts_per_query),
                max_time_seconds=max_time_per_query,
                max_hours_age=max_hours_age,
            )

            for post in posts:
                if post.linkedin_url and post.linkedin_url not in seen_urls:
                    seen_urls.add(post.linkedin_url)
                    all_posts.append(post)

            total_time += max_time_per_query

            if len(all_posts) >= min_posts:
                break

            await asyncio.sleep(delay_between_queries)

        return all_posts

    def _build_queries(
        self,
        roles: Optional[List[str]] = None,
        companies: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
    ) -> List[str]:
        """Build search queries for hiring posts."""
        queries: List[str] = []

        if roles and locations:
            for role in roles[:3]:
                for loc in locations[:2]:
                    queries.append(f"{role} {loc} hiring")
                queries.append(f"{role} we're hiring")
        elif roles:
            for role in roles[:5]:
                queries.append(f"{role} we're hiring")
                queries.append(f"{role} now hiring")

        if companies:
            for company in companies[:5]:
                queries.append(f"{company} join our team")
                queries.append(f"{company} careers")

        base = ["we're hiring", "now hiring", "join our team", "open position"]
        for q in base[:4]:
            queries.append(q)

        return list(dict.fromkeys(queries))


async def search_linkedin_posts(
    page: Page,
    keywords: str,
    limit: int = 25,
    filter_hiring: bool = True,
    min_posts: int = 5,
    max_time_seconds: int = 180,
    max_hours_age: Optional[int] = None,
) -> List[Post]:
    """
    Convenience function to search LinkedIn posts.

    Args:
        page: Playwright page object
        keywords: Search keywords
        limit: Max posts to return
        filter_hiring: Only return hiring-related posts
        min_posts: Minimum posts to collect before stopping
        max_time_seconds: Hard time limit
        max_hours_age: Only return posts from last N hours

    Returns:
        List of posts matching search
    """
    scraper = PostSearchScraper(page)
    return await scraper.search(
        keywords=keywords,
        limit=limit,
        filter_hiring=filter_hiring,
        min_posts=min_posts,
        max_time_seconds=max_time_seconds,
        max_hours_age=max_hours_age,
    )
