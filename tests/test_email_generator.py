from job_assist_skill.assistant.pipeline.email_generator import EmailGenerator


def test_email_generator_is_generic():
    generator = EmailGenerator()
    email = generator.generate_application_email(
        job={"title": "Operations Manager", "company": "Example Co", "location": "Riyadh"},
        sender_name="Jane Doe",
        sender_email="jane@example.com",
        user_summary="I have led cross-functional operations improvement programs.",
    )

    assert email.subject == "Application for Operations Manager at Example Co"
    assert "final-year Software Engineering student" not in email.body
    assert "cross-functional operations improvement programs" in email.body
    assert "jane@example.com" in email.body


def test_email_generator_removes_placeholder_company_names():
    generator = EmailGenerator()
    email = generator.generate_application_email(
        job={"title": "Operations Manager", "company": "company1"},
        sender_name="Jane Doe",
    )

    assert "company1" not in email.subject.lower()
    assert "company1" not in email.body.lower()
    assert "placeholder_company_removed" in email.warnings
