"""
Job search scraper for LinkedIn.

Searches for jobs on LinkedIn and extracts job URLs.
"""
import logging
from typing import Optional, List
from urllib.parse import urlencode

import requests
from lxml import html
from playwright.async_api import Page

from ..callbacks import ProgressCallback, SilentCallback
from ..utils import MetadataCleaner
from .base import BaseScraper

logger = logging.getLogger(__name__)

GUEST_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
GUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


class JobSearchScraper(BaseScraper):
    """
    Scraper for LinkedIn job search results.
    
    Example:
        async with BrowserManager() as browser:
            scraper = JobSearchScraper(browser.page)
            job_urls = await scraper.search(
                keywords="software engineer",
                location="San Francisco",
                limit=10
            )
    """
    
    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        """
        Initialize job search scraper.
        
        Args:
            page: Playwright page object
            callback: Optional progress callback
        """
        super().__init__(page, callback or SilentCallback())
    
    async def search(
        self,
        keywords: Optional[str] = None,
        location: Optional[str] = None,
        limit: int = 25
    ) -> List[str]:
        """
        Search for jobs on LinkedIn.
        
        Args:
            keywords: Job search keywords (e.g., "software engineer")
            location: Job location (e.g., "San Francisco, CA")
            limit: Maximum number of job URLs to return
            
        Returns:
            List of job posting URLs
        """
        logger.info(f"Starting job search: keywords='{keywords}', location='{location}'")

        try:
            page_urls = await self._search_authenticated_page(
                keywords=keywords,
                location=location,
                limit=limit,
            )
            if page_urls:
                return page_urls
        except Exception as exc:
            logger.debug(f"Authenticated job search failed, falling back to guest endpoint: {exc}")

        guest_urls = self._search_guest_endpoint(
            keywords=keywords,
            location=location,
            limit=limit,
        )
        if guest_urls:
            await self.callback.on_start("JobSearchGuest", self._build_guest_search_url(keywords, location, 0))
            await self.callback.on_progress(f"Found {len(guest_urls)} job URLs via guest endpoint", 100)
            await self.callback.on_complete("JobSearchGuest", guest_urls)
            logger.info(f"Guest job search complete: found {len(guest_urls)} jobs")
            return guest_urls
        
        search_url = self._build_search_url(keywords, location)
        await self.callback.on_start("JobSearch", search_url)
        
        await self.navigate_and_wait(search_url)
        await self.callback.on_progress("Navigated to search results", 20)
        
        try:
            await self.page.wait_for_selector('a[href*="/jobs/view/"]', timeout=10000)
        except:
            logger.warning("No job listings found on page")
            return []
        
        await self.wait_and_focus(1)
        await self.scroll_page_to_bottom(pause_time=1, max_scrolls=3)
        await self.callback.on_progress("Loaded job listings", 50)
        
        job_urls = await self._extract_job_urls(limit)
        await self.callback.on_progress(f"Found {len(job_urls)} job URLs", 90)
        
        await self.callback.on_progress("Search complete", 100)
        await self.callback.on_complete("JobSearch", job_urls)
        
        logger.info(f"Job search complete: found {len(job_urls)} jobs")
        return job_urls

    async def _search_authenticated_page(
        self,
        *,
        keywords: Optional[str],
        location: Optional[str],
        limit: int,
    ) -> List[str]:
        """Use the authenticated Playwright flow as the primary job-search path."""
        search_url = self._build_search_url(keywords, location)
        await self.callback.on_start("JobSearch", search_url)

        await self.navigate_and_wait(search_url)
        await self.callback.on_progress("Navigated to search results", 20)

        try:
            await self.page.wait_for_selector('a[href*="/jobs/view/"]', timeout=8000)
        except Exception:
            logger.warning("No authenticated job listings found on page")
            return []

        await self.wait_and_focus(1)
        await self.scroll_page_to_bottom(pause_time=1, max_scrolls=3)
        await self.callback.on_progress("Loaded job listings", 50)

        job_urls = await self._extract_job_urls(limit)
        await self.callback.on_progress(f"Found {len(job_urls)} job URLs", 90)
        await self.callback.on_progress("Search complete", 100)
        await self.callback.on_complete("JobSearch", job_urls)
        logger.info(f"Authenticated job search complete: found {len(job_urls)} jobs")
        return job_urls
    
    def _build_search_url(
        self,
        keywords: Optional[str] = None,
        location: Optional[str] = None
    ) -> str:
        """Build LinkedIn job search URL with parameters."""
        base_url = "https://www.linkedin.com/jobs/search/"
        
        params = {}
        if keywords:
            params['keywords'] = keywords
        if location:
            params['location'] = location
        
        if params:
            return f"{base_url}?{urlencode(params)}"
        return base_url

    def _build_guest_search_url(
        self,
        keywords: Optional[str] = None,
        location: Optional[str] = None,
        start: int = 0,
    ) -> str:
        params = {"start": start}
        if keywords:
            params["keywords"] = keywords
        if location:
            params["location"] = location
        return f"{GUEST_SEARCH_URL}?{urlencode(params)}"

    def _search_guest_endpoint(
        self,
        *,
        keywords: Optional[str],
        location: Optional[str],
        limit: int,
    ) -> List[str]:
        """Use LinkedIn's public jobs-guest endpoint for fast URL discovery."""
        if not keywords:
            return []

        seen_urls = set()
        job_urls: List[str] = []
        start = 0

        while len(job_urls) < limit:
            try:
                response = requests.get(
                    GUEST_SEARCH_URL,
                    params={
                        "keywords": keywords,
                        "location": location or "",
                        "start": start,
                    },
                    headers=GUEST_HEADERS,
                    timeout=15,
                )
            except requests.RequestException as exc:
                logger.debug(f"Guest job search request failed: {exc}")
                break

            if response.status_code in {429, 999}:
                logger.warning(f"Guest job search blocked with status {response.status_code}")
                break

            if "LinkedIn: Log In" in response.text:
                logger.warning("Guest job search returned a login page")
                break

            try:
                fragment = html.fromstring(f"<div>{response.text}</div>")
            except ValueError:
                break

            links = fragment.xpath('//a[contains(@class, "base-card__full-link")]/@href')
            if not links:
                break

            added_this_page = 0
            for href in links:
                clean_url = href.split("?")[0].strip()
                if clean_url and clean_url not in seen_urls and "/jobs/view/" in clean_url:
                    seen_urls.add(clean_url)
                    job_urls.append(clean_url)
                    added_this_page += 1
                if len(job_urls) >= limit:
                    break

            if added_this_page == 0:
                break
            start += 25

        return job_urls[:limit]
    
    async def _extract_job_urls(self, limit: int) -> List[str]:
        """
        Extract job URLs from search results.
        
        Args:
            limit: Maximum number of URLs to extract
            
        Returns:
            List of job posting URLs
        """
        job_urls = []
        
        try:
            # Find all job cards/links
            job_links = await self.page.locator('a[href*="/jobs/view/"]').all()
            
            seen_urls = set()
            for link in job_links:
                if len(job_urls) >= limit:
                    break
                
                try:
                    href = await link.get_attribute('href')
                    if href and '/jobs/view/' in href:
                        # Clean URL (remove query params)
                        clean_url = href.split('?')[0] if '?' in href else href

                        if clean_url in seen_urls:
                            continue

                        seen_urls.add(clean_url)
                        job_urls.append(clean_url)

                        company_name = ""
                        try:
                            container_text = await link.evaluate(
                                """(node) => {
                                    const container = node.closest('li, article, div') || node.parentElement;
                                    return container ? container.innerText : '';
                                }"""
                            )
                            company_name = MetadataCleaner.clean_company_name(container_text or "")
                        except Exception:
                            company_name = ""

                        logger.debug(f"Found job URL: {clean_url} (Company: {company_name})")
                except Exception as e:
                    logger.debug(f"Error extracting job URL: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Error extracting job URLs: {e}")
        
        return job_urls
