import json

from job_assist_skill.assistant.ui.app import create_app
import main as cli_main


def test_flask_ui_prepares_tailoring_and_email(tmp_path):
    cv_path = tmp_path / "cv.tex"
    cv_path.write_text("\\item Resume bullet", encoding="utf-8")

    store = {
        "cand-1": {
            "candidate_id": "cand-1",
            "title": "Operations Manager",
            "company": "Example Co",
            "location": "Riyadh",
            "status": "pending",
            "snippet": "We are hiring an operations manager with reporting ownership.",
        }
    }

    app = create_app(
        candidates_store=store,
        output_dir=str(tmp_path / "output"),
        cv_latex_template=str(cv_path),
    )
    client = app.test_client()

    tailor_response = client.post("/api/candidate/cand-1/tailor")
    assert tailor_response.status_code == 200
    assert tailor_response.get_json()["success"] is True

    email_response = client.post(
        "/api/candidate/cand-1/email",
        json={"sender_name": "Jane Doe", "sender_email": "jane@example.com"},
    )
    assert email_response.status_code == 200
    assert "subject" in email_response.get_json()["email"]
    assert email_response.get_json()["email"]["mailto_url"].startswith("mailto:")


def test_cli_memory_and_tailor_alignment_commands(tmp_path):
    memory_path = tmp_path / "prefs.json"
    parsed_job_path = tmp_path / "parsed_job.json"
    parsed_job_path.write_text(json.dumps({"title": "Operations Manager"}), encoding="utf-8")
    cv_path = tmp_path / "cv.tex"
    cv_path.write_text("\\item Resume bullet", encoding="utf-8")
    output_path = tmp_path / "alignment_prompt.json"

    rc = cli_main.main(["memory", "set", "profile.name", "Jane Doe", "--memory-path", str(memory_path)])
    assert rc == 0

    rc = cli_main.main(
        [
            "tailor",
            "alignment",
            "--parsed-job",
            str(parsed_job_path),
            "--cv-file",
            str(cv_path),
            "--output",
            str(output_path),
            "--memory-path",
            str(memory_path),
        ]
    )
    assert rc == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert "system" in payload
    assert "user" in payload
    assert payload["suggested_output_file"] == "alignment.json"
    assert payload["quality_checks"]
