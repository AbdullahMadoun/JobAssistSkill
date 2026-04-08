from job_assist_skill.assistant.pipeline.email_generator import EmailGenerator
from job_assist_skill.scraper.core.auth import load_credentials_from_env


def test_email_generator_is_generic():
    generator = EmailGenerator()
    email = generator.generate_application_email(
        job={"title": "Operations Manager", "company": "Example Co", "location": "Riyadh"},
        sender_name="Jane Doe",
        sender_email="jane@example.com",
        user_summary="I have experience leading operational improvements and cross-functional delivery.",
    )

    assert "Operations Manager" in email.subject
    assert "Example Co" in email.subject
    assert "cross-functional delivery" in email.body
    assert "AI/ML" not in email.body


def test_auth_loader_supports_legacy_env_aliases(monkeypatch):
    monkeypatch.delenv("LINKEDIN_EMAIL", raising=False)
    monkeypatch.delenv("LINKEDIN_USERNAME", raising=False)
    monkeypatch.delenv("LINKEDIN_PASSWORD", raising=False)
    monkeypatch.setenv("LinkedinUser", "user@example.com")
    monkeypatch.setenv("LinkedinPassword", "secret")

    email, password = load_credentials_from_env()

    assert email == "user@example.com"
    assert password == "secret"
