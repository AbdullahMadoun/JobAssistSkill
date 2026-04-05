"""

Hiring Posts Scraper - High-level wrapper around HiringPostSearcher.
"""

from typing import List, Optional
from playwright.async_api import Page

from job_assist_skill.scraper.scrapers.post_search import HiringPostSearcher
from job_assist_skill.scraper.models.post import Post


class HiringPostScraper:
    def __init__(self, page: Page):
        self.page = page
        self._searcher = None

    async def search(self, roles, locations, max_hours_age=24, posts_per_query=10):
        return await HiringPostSearcher(self.page).search_for_hiring(
            roles=roles,
            locations=locations,
            max_hours_age=max_hours_age,
            posts_per_query=posts_per_query,
        )

__all__ = ["HiringPostScraper"]
