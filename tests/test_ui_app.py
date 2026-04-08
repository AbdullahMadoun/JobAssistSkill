from job_assist_skill.assistant.ui.app import create_app


def test_ui_app_serves_candidates(tmp_path):
    app = create_app(
        candidates_store={
            "candidate-1": {
                "candidate_id": "candidate-1",
                "title": "Operations Manager",
                "company": "Example Co",
                "status": "pending",
                "snippet": "Lead operations improvement.",
            }
        },
        output_dir=str(tmp_path),
    )

    client = app.test_client()
    response = client.get("/api/candidates")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total"] == 1
