import asyncio

from job_assist_skill.scraper.scrapers.job_search import JobSearchScraper


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


class DummyPage:
    pass


def test_job_search_scraper_uses_guest_endpoint(monkeypatch):
    html_fragment = """
    <div class="base-card">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/123456/?trk=public_jobs">Job</a>
    </div>
    <div class="base-card">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/789012/">Job</a>
    </div>
    """

    def fake_get(*args, **kwargs):
        return DummyResponse(html_fragment)

    scraper = JobSearchScraper(DummyPage())
    monkeypatch.setattr("job_assist_skill.scraper.scrapers.job_search.requests.get", fake_get)

    urls = asyncio.run(scraper.search(keywords="operations manager", location="Riyadh", limit=2))

    assert urls == [
        "https://www.linkedin.com/jobs/view/123456/",
        "https://www.linkedin.com/jobs/view/789012/",
    ]
