"""

Job Postings Scraper - High-level wrapper around JobSearchScraper.

Provides a simplified async interface for searching LinkedIn job postings.
"""

from typing import List
from playwright.async_api import Page

from job_assist_skill.scraper.scrapers.job_search import JobSearchScraper
from job_assist_skill.scraper.models.job import Job


class JobPostingScraper:
    def __init__(self, page: Page):
        self.page = page
        self._searcher = JobSearchScraper(page)

    async def search(self, keywords, location, limit=25):
        job_urls = await self._searcher.search(
            keywords=keywords,
            location=location,
            limit=limit,
        )
        
        jobs = []
        for url in job_urls:
            try:
                job = Job(linkedin_url=url)
                jobs.append(job)
            except Exception:
                continue
        
        return jobs

__all__ = ["JobPostingScraper"]
