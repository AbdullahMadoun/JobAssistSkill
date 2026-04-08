"""
Job scraper for LinkedIn.

Keeps the Joeyism-style Playwright navigation/session flow, but parses the
rendered page HTML and JSON-LD for more stable field extraction on current
LinkedIn job pages.
"""

from __future__ import annotations

import json
import logging
import re
from html import unescape
from typing import Any, Dict, Iterable, List, Optional, Tuple

from lxml import html as lxml_html
from playwright.async_api import Page

from ..callbacks import ProgressCallback, SilentCallback
from ..models.job import Job
from .base import BaseScraper

logger = logging.getLogger(__name__)

APPLICANT_PATTERN = re.compile(
    r"((?:over\s+)?[\d,٠-٩]+\+?\s+applicants?|people clicked apply|أكثر من\s*[\d٠-٩]+\s*متقدم|[\d٠-٩]+\s*متقدم)",
    re.IGNORECASE,
)


def _normalize_space(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _first_nonempty(values: Iterable[Optional[str]]) -> Optional[str]:
    for value in values:
        cleaned = _normalize_space(value)
        if cleaned:
            return cleaned
    return None


def _clean_url(value: Optional[str]) -> Optional[str]:
    cleaned = _normalize_space(value)
    if not cleaned:
        return None
    if "?" in cleaned:
        cleaned = cleaned.split("?", 1)[0]
    if cleaned.startswith("/"):
        cleaned = f"https://www.linkedin.com{cleaned}"
    return cleaned


def _html_fragment_to_text(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        fragment = lxml_html.fromstring(f"<div>{value}</div>")
        text = " ".join(text.strip() for text in fragment.xpath(".//text()") if text and text.strip())
    except Exception:
        text = re.sub(r"<[^>]+>", " ", value)
    return _normalize_space(unescape(text))


def _iter_ld_nodes(payload: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(payload, list):
        for item in payload:
            yield from _iter_ld_nodes(item)
        return

    if not isinstance(payload, dict):
        return

    graph = payload.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            yield from _iter_ld_nodes(item)

    yield payload


def _extract_ld_job_posting(tree) -> Dict[str, Any]:
    for raw_payload in tree.xpath('//script[@type="application/ld+json"]/text()'):
        raw_payload = raw_payload.strip()
        if not raw_payload:
            continue
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            continue
        for node in _iter_ld_nodes(payload):
            node_type = node.get("@type")
            if node_type == "JobPosting" or (
                isinstance(node_type, list) and "JobPosting" in node_type
            ):
                return node
    return {}


def _extract_texts(tree, xpath: str) -> List[str]:
    results: List[str] = []
    for item in tree.xpath(xpath):
        if hasattr(item, "text_content"):
            text = item.text_content()
        else:
            text = str(item)
        cleaned = _normalize_space(text)
        if cleaned:
            results.append(cleaned)
    return results


def _location_from_ld(job_posting: Dict[str, Any]) -> str:
    job_locations = job_posting.get("jobLocation")
    if not job_locations:
        return ""

    if not isinstance(job_locations, list):
        job_locations = [job_locations]

    for item in job_locations:
        if not isinstance(item, dict):
            continue
        address = item.get("address") or {}
        parts: List[str] = []
        for key in ("addressLocality", "addressRegion", "addressCountry"):
            value = _normalize_space(address.get(key))
            if value and value.lower() != "none" and value not in parts:
                parts.append(value)
        if parts:
            return ", ".join(parts)
    return ""


def _split_metadata(value: str) -> Tuple[str, str]:
    cleaned = _normalize_space(value)
    if not cleaned:
        return "", ""

    applicant_match = APPLICANT_PATTERN.search(cleaned)
    if not applicant_match:
        return cleaned, ""

    applicant_count = _normalize_space(applicant_match.group(1))
    posted_date = _normalize_space(cleaned.replace(applicant_count, " "))
    return posted_date, applicant_count


def parse_job_page_html(page_html: str) -> Dict[str, Optional[str]]:
    """Parse a rendered LinkedIn job page HTML snapshot into normalized fields."""
    tree = lxml_html.fromstring(page_html)
    job_posting = _extract_ld_job_posting(tree)

    title = _first_nonempty(
        [
            *_extract_texts(tree, "//h1/text()"),
            job_posting.get("title", ""),
            *tree.xpath('//meta[@property="og:title"]/@content'),
        ]
    )
    company = _first_nonempty(
        [
            *_extract_texts(tree, '//a[@data-tracking-control-name="public_jobs_topcard-org-name"]/text()'),
            *_extract_texts(tree, '//a[contains(@href, "/company/")]/text()'),
            (job_posting.get("hiringOrganization") or {}).get("name", ""),
        ]
    )
    company_url = _first_nonempty(
        [
            *_extract_texts(tree, '//a[@data-tracking-control-name="public_jobs_topcard-org-name"]/@href'),
            *_extract_texts(tree, '//a[contains(@href, "/company/")]/@href'),
            (job_posting.get("hiringOrganization") or {}).get("sameAs", ""),
        ]
    )
    location = _first_nonempty(
        [
            *_extract_texts(
                tree,
                '//span[contains(@class, "topcard__flavor--bullet") and not(contains(@class, "topcard__flavor--metadata"))]//text()',
            ),
            _location_from_ld(job_posting),
        ]
    )

    posted_date = _first_nonempty(_extract_texts(tree, '//span[contains(@class, "posted-time-ago__text")]//text()'))
    applicant_count = _first_nonempty(
        _extract_texts(tree, '//figcaption[contains(@class, "num-applicants__caption")]//text()')
    )

    combined_metadata = _first_nonempty(
        _extract_texts(
            tree,
            '//*[contains(@class, "topcard__flavor--metadata") or contains(@class, "num-applicants__caption")]//text()',
        )
    )
    if combined_metadata and (not posted_date or not applicant_count):
        split_posted, split_applicants = _split_metadata(combined_metadata)
        posted_date = posted_date or split_posted
        applicant_count = applicant_count or split_applicants

    description = _first_nonempty(
        [
            _html_fragment_to_text(
                "".join(
                    tree.xpath(
                        '(//div[contains(@class, "show-more-less-html__markup")])[1]//text()'
                    )
                )
            ),
            _html_fragment_to_text(
                "".join(tree.xpath('(//div[contains(@class, "description__text")])[1]//text()'))
            ),
            _html_fragment_to_text(job_posting.get("description", "")),
        ]
    )

    criteria_lines: List[str] = []
    for item in tree.xpath('//li[contains(@class, "description__job-criteria-item")]'):
        header = _normalize_space(" ".join(item.xpath('.//h3[contains(@class, "description__job-criteria-subheader")]//text()')))
        value = _normalize_space(" ".join(item.xpath('.//*[contains(@class, "description__job-criteria-text")]//text()')))
        if header and value:
            criteria_lines.append(f"{header}: {value}")

    if criteria_lines:
        criteria_text = "\n".join(criteria_lines)
        description = (
            f"{description}\n\nKey criteria:\n{criteria_text}".strip()
            if description
            else f"Key criteria:\n{criteria_text}"
        )

    return {
        "job_title": title,
        "company": company,
        "company_linkedin_url": _clean_url(company_url),
        "location": location,
        "posted_date": posted_date or _normalize_space(job_posting.get("datePosted", "")),
        "applicant_count": applicant_count,
        "job_description": description,
    }


class JobScraper(BaseScraper):
    """
    Scraper for LinkedIn job postings.

    Example:
        async with BrowserManager() as browser:
            scraper = JobScraper(browser.page)
            job = await scraper.scrape("https://www.linkedin.com/jobs/view/123456/")
            print(job.to_json())
    """

    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        super().__init__(page, callback or SilentCallback())

    async def scrape(self, linkedin_url: str) -> Job:
        """Scrape a LinkedIn job posting into the normalized Job model."""
        logger.info(f"Starting job scraping: {linkedin_url}")
        await self.callback.on_start("Job", linkedin_url)

        await self.navigate_and_wait(linkedin_url)
        await self.callback.on_progress("Navigated to job page", 10)
        await self.check_rate_limit()

        try:
            await self.page.wait_for_selector('h1, script[type="application/ld+json"]', timeout=10000)
        except Exception:
            logger.debug("Timed out waiting for job content selectors; falling back to current page HTML")

        page_html = await self.page.content()
        parsed = parse_job_page_html(page_html)

        job_title = parsed.get("job_title") or await self._get_job_title()
        await self.callback.on_progress(f"Got job title: {job_title}", 20)

        company = parsed.get("company") or await self._get_company()
        await self.callback.on_progress("Got company name", 30)

        location = parsed.get("location") or await self._get_location()
        await self.callback.on_progress("Got location", 40)

        posted_date = parsed.get("posted_date") or await self._get_posted_date()
        await self.callback.on_progress("Got posted date", 50)

        applicant_count = parsed.get("applicant_count") or await self._get_applicant_count()
        await self.callback.on_progress("Got applicant count", 60)

        job_description = parsed.get("job_description") or await self._get_description()
        await self.callback.on_progress("Got job description", 80)

        company_url = parsed.get("company_linkedin_url") or await self._get_company_url()
        await self.callback.on_progress("Got company URL", 90)

        job = Job(
            linkedin_url=linkedin_url,
            job_title=job_title,
            company=company,
            company_linkedin_url=company_url,
            location=location,
            posted_date=posted_date,
            applicant_count=applicant_count,
            job_description=job_description,
        )

        await self.callback.on_progress("Scraping complete", 100)
        await self.callback.on_complete("Job", job)
        logger.info(f"Successfully scraped job: {job_title}")
        return job

    async def _get_job_title(self) -> Optional[str]:
        try:
            title_elem = self.page.locator("h1").first
            title = await title_elem.inner_text()
            return _normalize_space(title)
        except Exception:
            return None

    async def _get_company(self) -> Optional[str]:
        try:
            preferred = self.page.locator('[data-tracking-control-name="public_jobs_topcard-org-name"]').first
            if await preferred.count() > 0:
                text = _normalize_space(await preferred.inner_text())
                if text:
                    return text

            company_link = self.page.locator('a[href*="/company/"]').first
            if await company_link.count() > 0:
                text = _normalize_space(await company_link.inner_text())
                if text:
                    return text
        except Exception:
            pass
        return None

    async def _get_company_url(self) -> Optional[str]:
        try:
            company_link = self.page.locator('a[href*="/company/"]').first
            if await company_link.count() > 0:
                href = await company_link.get_attribute("href")
                return _clean_url(href)
        except Exception:
            pass
        return None

    async def _get_location(self) -> Optional[str]:
        try:
            locator = self.page.locator(
                '.topcard__flavor--bullet:not(.topcard__flavor--metadata), '
                'span.topcard__flavor.topcard__flavor--bullet'
            ).first
            if await locator.count() > 0:
                return _normalize_space(await locator.inner_text())
        except Exception:
            pass
        return None

    async def _get_posted_date(self) -> Optional[str]:
        try:
            locator = self.page.locator(".posted-time-ago__text").first
            if await locator.count() > 0:
                return _normalize_space(await locator.inner_text())
        except Exception:
            pass
        return None

    async def _get_applicant_count(self) -> Optional[str]:
        try:
            locator = self.page.locator(".num-applicants__caption").first
            if await locator.count() > 0:
                return _normalize_space(await locator.inner_text())
        except Exception:
            pass
        return None

    async def _get_description(self) -> Optional[str]:
        try:
            locator = self.page.locator(
                ".show-more-less-html__markup, .description__text .show-more-less-html__markup, .description__text"
            ).first
            if await locator.count() > 0:
                return _normalize_space(await locator.inner_text())
        except Exception:
            pass
        return None
