import asyncio
import json

from job_assist_skill.assistant.service import CareerAssistant


class DummyBrowserManager:
    def __init__(self, *args, **kwargs):
        self.page = object()
        self.loaded_session = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def load_session(self, path):
        self.loaded_session = path


class DummyPost:
    def __init__(self):
        self.linkedin_url = "https://www.linkedin.com/feed/update/1"
        self.company_name = "Example Co"
        self.locations = ["Riyadh"]
        self.text = "We are hiring an operations manager."
        self.posted_date = "1 day ago"
        self.author_name = "Recruiter Name"
        self.contact_emails = ["jobs@example.com"]

    def to_dict(self):
        return {
            "linkedin_url": self.linkedin_url,
            "company_name": self.company_name,
            "locations": self.locations,
            "text": self.text,
            "contact_emails": self.contact_emails,
        }


class DummyHiringPostSearcher:
    def __init__(self, page):
        self.page = page

    async def search_for_hiring(self, **kwargs):
        return [DummyPost()]


class DummyJobSearchScraper:
    def __init__(self, page):
        self.page = page

    async def search(self, **kwargs):
        return ["https://www.linkedin.com/jobs/view/123456"]


class DummyJob:
    job_title = "Operations Manager"
    company = "Example Co"
    location = "Riyadh"
    job_description = "Lead operations and reporting."
    posted_date = "2 days ago"

    def to_dict(self):
        return {
            "job_title": self.job_title,
            "company": self.company,
            "location": self.location,
            "job_description": self.job_description,
        }


class DummyJobScraper:
    def __init__(self, page):
        self.page = page

    async def scrape(self, url):
        return DummyJob()


def test_career_assistant_search_runs_both_streams(monkeypatch, tmp_path):
    import job_assist_skill.assistant.service as service_module

    monkeypatch.setattr(service_module, "BrowserManager", DummyBrowserManager)
    monkeypatch.setattr(service_module, "HiringPostSearcher", DummyHiringPostSearcher)
    monkeypatch.setattr(service_module, "JobSearchScraper", DummyJobSearchScraper)
    monkeypatch.setattr(service_module, "JobScraper", DummyJobScraper)

    session_path = tmp_path / "linkedin_session.json"
    session_path.write_text("{}", encoding="utf-8")
    cv_path = tmp_path / "cv.tex"
    cv_path.write_text("\\item Resume bullet", encoding="utf-8")

    assistant = CareerAssistant(memory_path=str(tmp_path / "prefs.json"), output_dir=str(tmp_path / "out"))
    assistant.memory.remember_files(
        cv_path=str(cv_path),
        linkedin_session=str(session_path),
    )

    results = asyncio.run(
        assistant.search(
            roles=["operations manager"],
            locations=["Riyadh"],
            stream="both",
            limit=5,
            session_path=str(session_path),
        )
    )

    assert len(results) == 2
    assert {result.source for result in results} == {"posts", "jobs"}
    assert any(result.text for result in results)
    assert any(result.next_action == "generate_mailto_application" for result in results if result.source == "posts")


def test_career_assistant_email_uses_memory_profile(tmp_path):
    assistant = CareerAssistant(memory_path=str(tmp_path / "prefs.json"), output_dir=str(tmp_path / "out"))
    assistant.memory.remember_profile(name="Jane Doe", email="jane@example.com", headline="Built operations workflows.")
    assistant.memory.set_value("application.default_summary", "Built operations workflows.")

    draft_path = tmp_path / "draft.json"
    email = assistant.generate_email(
        job_title="Operations Manager",
        company="Example Co",
        output_path=str(draft_path),
    )

    saved = json.loads(draft_path.read_text(encoding="utf-8"))
    assert email.cc == "jane@example.com"
    assert "Built operations workflows." in email.body
    assert saved["subject"].startswith("Application for Operations Manager")
    assert saved["mailto_url"].startswith("mailto:")


def test_career_assistant_setup_report_lists_blocking_questions(tmp_path):
    assistant = CareerAssistant(memory_path=str(tmp_path / "prefs.json"), output_dir=str(tmp_path / "out"))

    report = assistant.get_setup_report()

    assert any(item["key"] == "profile.name" for item in report["blocking_inputs"])
    assert any(item["key"] == "profile.email" for item in report["blocking_inputs"])
