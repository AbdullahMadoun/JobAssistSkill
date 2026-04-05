"""

Career Assistant Scrapers - High-level wrappers for LinkedIn scraping.
"""

from .hiring_posts import HiringPostScraper
from .job_postings import JobPostingScraper

__all__ = [
    "HiringPostScraper",
    "JobPostingScraper",
]
