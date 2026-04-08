"""Minimal review UI for local, agent-prepared candidate data."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, jsonify, render_template, request, send_file

from ..email.mailto_client import MailtoClient
from ..pipeline.email_generator import EmailGenerator
from ..pipeline.tailoring import CVTailoringPipeline


def create_app(
    candidates_store: Optional[Dict] = None,
    feedback_store=None,
    output_dir: str = "./output",
    cv_latex_template: Optional[str] = None,
) -> Flask:
    """Create a lightweight local review application."""
    app = Flask(__name__, template_folder="templates")
    app.candidates_store = candidates_store or {}
    app.feedback_store = feedback_store
    app.output_dir = Path(output_dir)
    app.output_dir.mkdir(parents=True, exist_ok=True)
    app.cv_latex_template = (
        Path(cv_latex_template).read_text(encoding="utf-8")
        if cv_latex_template and Path(cv_latex_template).exists()
        else None
    )

    @app.route("/")
    def dashboard():
        return render_template(
            "dashboard.html",
            candidates=_by_status(app.candidates_store, "pending"),
            stats=_stats(app.candidates_store, app.feedback_store),
            now=datetime.now(),
        )

    @app.route("/candidate/<candidate_id>")
    def candidate_detail(candidate_id: str):
        candidate = app.candidates_store.get(candidate_id)
        if not candidate:
            return "Candidate not found", 404
        job_context = app.feedback_store.get_job_context(candidate_id) if app.feedback_store else None
        return render_template("candidate_detail.html", candidate=candidate, job_context=job_context)

    @app.route("/approved")
    def approved():
        return render_template("approved.html", candidates=_by_status(app.candidates_store, "approved"))

    @app.route("/api/candidates")
    def api_candidates():
        status = request.args.get("status", "all")
        candidates = (
            list(app.candidates_store.values())
            if status == "all"
            else _by_status(app.candidates_store, status)
        )
        return jsonify({"candidates": [_serialize(c) for c in candidates], "total": len(candidates)})

    @app.route("/api/candidate/<candidate_id>/approve", methods=["POST"])
    def approve(candidate_id: str):
        candidate = app.candidates_store.get(candidate_id)
        if not candidate:
            return jsonify({"error": "Candidate not found"}), 404
        candidate["status"] = "approved"
        candidate["approved_at"] = datetime.now().isoformat()
        if app.feedback_store:
            app.feedback_store.record_feedback(
                candidate_id=candidate_id,
                action="approved",
                job_keywords=[candidate.get("title", "")],
                company_name=candidate.get("company", ""),
            )
        return jsonify({"success": True, "status": "approved"})

    @app.route("/api/candidate/<candidate_id>/reject", methods=["POST"])
    def reject(candidate_id: str):
        candidate = app.candidates_store.get(candidate_id)
        if not candidate:
            return jsonify({"error": "Candidate not found"}), 404
        candidate["status"] = "rejected"
        candidate["rejected_at"] = datetime.now().isoformat()
        if app.feedback_store:
            app.feedback_store.record_feedback(
                candidate_id=candidate_id,
                action="rejected",
                job_keywords=[candidate.get("title", "")],
                company_name=candidate.get("company", ""),
            )
        return jsonify({"success": True, "status": "rejected"})

    @app.route("/api/candidate/<candidate_id>/tailor", methods=["POST"])
    def tailor(candidate_id: str):
        candidate = app.candidates_store.get(candidate_id)
        if not candidate:
            return jsonify({"error": "Candidate not found"}), 404
        if not app.cv_latex_template:
            return jsonify({"error": "CV template not configured"}), 400
        job_text = candidate.get("snippet") or candidate.get("raw_data", {}).get("post_text") or ""
        if not job_text:
            return jsonify({"error": "No job text available"}), 400

        pipeline = CVTailoringPipeline()
        result = pipeline.prepare(
            job_text=job_text,
            cv_latex=app.cv_latex_template,
            output_dir=str(app.output_dir),
        )
        if not result.success:
            return jsonify({"error": result.error}), 500

        candidate["tailoring_context_path"] = result.context_path
        candidate["tailoring_status"] = "prepared"
        return jsonify(
            {
                "success": True,
                "context_path": result.context_path,
                "latex_path": result.latex_path,
            }
        )

    @app.route("/api/candidate/<candidate_id>/email", methods=["POST"])
    def email(candidate_id: str):
        candidate = app.candidates_store.get(candidate_id)
        if not candidate:
            return jsonify({"error": "Candidate not found"}), 404
        body = request.get_json(silent=True) or {}
        generator = EmailGenerator()
        email_draft = generator.generate_application_email(
            job={
                "title": candidate.get("title", ""),
                "company": candidate.get("company", ""),
                "location": candidate.get("location", ""),
            },
            recipient_email=body.get("to", ""),
            recipient_name=body.get("recipient_name", ""),
            cv_path=body.get("cv_path", ""),
            cover_letter_path=body.get("cover_letter_path", ""),
            sender_name=body.get("sender_name", "Candidate"),
            sender_email=body.get("sender_email", ""),
            user_summary=body.get("user_summary", ""),
        )
        mailto_url = MailtoClient(
            user_name=body.get("sender_name", "Candidate"),
            user_email=body.get("sender_email", ""),
        ).create_mailto_url(
            to=body.get("to", ""),
            subject=email_draft.subject,
            body=email_draft.body,
            cc=email_draft.cc or "",
            bcc=email_draft.bcc or "",
        )
        candidate["email"] = {
            "subject": email_draft.subject,
            "body": email_draft.body,
            "to": email_draft.to,
            "attachments": email_draft.attachments,
            "mailto_url": mailto_url,
            "warnings": email_draft.warnings,
            "status": "draft",
        }
        return jsonify({"success": True, "email": candidate["email"]})

    @app.route("/statistics")
    def statistics():
        return jsonify(app.feedback_store.get_statistics() if app.feedback_store else {})

    @app.route("/output/<path:filename>")
    def output_file(filename: str):
        file_path = app.output_dir / filename
        if not file_path.exists():
            return "Not found", 404
        return send_file(file_path)

    return app


def _serialize(candidate: Dict) -> Dict:
    return {
        "id": candidate.get("candidate_id", ""),
        "title": candidate.get("title", ""),
        "company": candidate.get("company", ""),
        "location": candidate.get("location", ""),
        "source": candidate.get("source", ""),
        "status": candidate.get("status", "pending"),
        "url": candidate.get("url", ""),
        "snippet": candidate.get("snippet", "")[:150] + "..." if candidate.get("snippet") else "",
        "collected_at": candidate.get("collected_at", ""),
        "approved_at": candidate.get("approved_at", ""),
        "email": candidate.get("email"),
    }


def _by_status(store: Dict, status: str) -> List[Dict]:
    return [_serialize(candidate) for candidate in store.values() if candidate.get("status") == status]


def _stats(store: Dict, feedback_store) -> Dict:
    stats = {
        "total": len(store),
        "pending": sum(1 for value in store.values() if value.get("status") == "pending"),
        "approved": sum(1 for value in store.values() if value.get("status") == "approved"),
        "rejected": sum(1 for value in store.values() if value.get("status") == "rejected"),
        "applied": sum(1 for value in store.values() if value.get("status") == "applied"),
    }
    if feedback_store:
        stats.update(feedback_store.get_statistics())
    return stats
