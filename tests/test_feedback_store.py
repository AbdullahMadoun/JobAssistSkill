from job_assist_skill.assistant.storage import FeedbackStore


def test_feedback_store_records_preferences(tmp_path):
    db_path = tmp_path / "feedback.db"
    store = FeedbackStore(str(db_path))

    store.record_feedback(
        candidate_id="cand-1",
        action="approved",
        job_keywords=["operations", "planning"],
        company_name="Example Co",
    )

    roles = store.get_preferred_roles()
    companies = store.get_preferred_companies()

    assert "operations" in roles
    assert "example co" in companies
    assert store.is_candidate_approved("cand-1") is True
