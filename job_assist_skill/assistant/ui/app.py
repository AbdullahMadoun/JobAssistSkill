"""
Career Assistant Web UI.

Flask web application for reviewing and approving job candidates,
viewing tailored CVs, and sending application emails.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
import logging

logger = logging.getLogger(__name__)


def create_app(
    candidates_store: Optional[Dict] = None,
    feedback_store=None,
    output_dir: str = "./output",
    cv_latex_template: Optional[str] = None,
    llm_provider: str = "openai",
    model: str = "gpt-4o",
) -> Flask:
    """
    Create Flask application for career assistant UI.

    Args:
        candidates_store: In-memory candidates store
        feedback_store: FeedbackStore instance
        output_dir: Directory for compiled CVs and outputs
        cv_latex_template: Path to user's LaTeX CV template
        llm_provider: LLM provider (openai, anthropic)
        model: Model name to use

    Returns:
        Flask app instance
    """
    app = Flask(__name__, template_folder="templates")
    app.config['OUTPUT_DIR'] = output_dir

    if candidates_store is None:
        candidates_store = {}

    app.candidates_store = candidates_store
    app.feedback_store = feedback_store
    app.llm_provider = llm_provider
    app.model = model

    if cv_latex_template and os.path.exists(cv_latex_template):
        app.cv_latex_template = Path(cv_latex_template).read_text(encoding='utf-8')
    else:
        app.cv_latex_template = None

    os.makedirs(output_dir, exist_ok=True)

    @app.route("/")
    def dashboard():
        """Main dashboard with pending candidates."""
        candidates = _get_pending_candidates(app.candidates_store)
        stats = _get_stats(app.candidates_store, app.feedback_store)

        return render_template(
            "dashboard.html",
            candidates=candidates,
            stats=stats,
            now=datetime.now(),
        )

    @app.route("/candidate/<candidate_id>")
    def candidate_detail(candidate_id: str):
        """Candidate detail view."""
        candidate = app.candidates_store.get(candidate_id)
        if not candidate:
            return "Candidate not found", 404

        job_context = None
        if app.feedback_store:
            job_context = app.feedback_store.get_job_context(candidate_id)

        return render_template(
            "candidate_detail.html",
            candidate=candidate,
            job_context=job_context,
        )

    @app.route("/api/candidates", methods=["GET"])
    def api_list_candidates():
        """API: List all candidates."""
        status = request.args.get("status", "all")

        if status == "all":
            candidates = list(app.candidates_store.values())
        else:
            candidates = [
                c for c in app.candidates_store.values()
                if c.get("status") == status
            ]

        return jsonify({
            "candidates": [_serialize_candidate(c) for c in candidates],
            "total": len(candidates),
        })

    @app.route("/api/candidate/<candidate_id>/approve", methods=["POST"])
    def api_approve_candidate(candidate_id: str):
        """API: Approve a candidate."""
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
    def api_reject_candidate(candidate_id: str):
        """API: Reject a candidate."""
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
    def api_tailor_cv(candidate_id: str):
        """API: Trigger CV tailoring for a candidate."""
        candidate = app.candidates_store.get(candidate_id)
        if not candidate:
            return jsonify({"error": "Candidate not found"}), 404

        candidate["tailoring_status"] = "in_progress"

        try:
            from ..pipeline.tailoring import CVTailoringPipeline

            job_text = candidate.get("snippet") or candidate.get("raw_data", {}).get("post_text", "")
            if not job_text:
                return jsonify({"error": "No job text available"}), 400

            pipeline = CVTailoringPipeline(
                llm_provider=app.llm_provider,
                model=app.model,
            )

            cv_latex = app.cv_latex_template
            if not cv_latex:
                cv_template_path = Path(output_dir).parent / "cv.tex"
                if cv_template_path.exists():
                    cv_latex = cv_template_path.read_text(encoding='utf-8')

            if not cv_latex:
                return jsonify({"error": "CV template not found"}), 400

            result = pipeline.tailor(
                job_text=job_text,
                cv_latex=cv_latex,
                output_dir=output_dir,
            )

            if result.success:
                candidate["tailoring_status"] = "completed"
                candidate["tailored_cv_path"] = result.pdf_path
                candidate["alignment_score_before"] = result.alignment_score_before
                candidate["alignment_score_after"] = result.alignment_score_after
                return jsonify({
                    "success": True,
                    "cv_path": result.pdf_path,
                    "alignment_before": result.alignment_score_before,
                    "alignment_after": result.alignment_score_after,
                })
            else:
                candidate["tailoring_status"] = "failed"
                candidate["tailoring_error"] = result.error
                return jsonify({"error": result.error}), 500

        except Exception as e:
            logger.exception(f"CV tailoring failed for {candidate_id}")
            candidate["tailoring_status"] = "failed"
            candidate["tailoring_error"] = str(e)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/candidate/<candidate_id>/email", methods=["POST"])
    def api_generate_email(candidate_id: str):
        """API: Generate application email for a candidate."""
        candidate = app.candidates_store.get(candidate_id)
        if not candidate:
            return jsonify({"error": "Candidate not found"}), 404

        email_data = request.get_json() or {}

        try:
            from ..pipeline.email_generator import EmailGenerator

            generator = EmailGenerator()

            cv_path = candidate.get("tailored_cv_path")
            cover_letter_path = email_data.get("cover_letter_path")

            email = generator.generate_application_email(
                job={
                    "title": candidate.get("title", ""),
                    "company": candidate.get("company", ""),
                    "location": candidate.get("location", ""),
                },
                recipient_email=email_data.get("to", ""),
                cv_path=cv_path,
                cover_letter_path=cover_letter_path,
            )

            candidate["email"] = {
                "subject": email.subject,
                "body": email.body,
                "to": email.to,
                "cc": email.cc,
                "status": "draft",
            }

            return jsonify({
                "success": True,
                "email": {
                    "subject": email.subject,
                    "body": email.body,
                    "to": email.to,
                    "cc": email.cc,
                }
            })

        except Exception as e:
            logger.exception(f"Email generation failed for {candidate_id}")
            return jsonify({"error": str(e)}), 500

    @app.route("/approved")
    def approved_list():
        """List of approved candidates ready to apply."""
        candidates = _get_approved_candidates(app.candidates_store)
        return render_template("approved.html", candidates=candidates)

    @app.route("/statistics")
    def statistics():
        """Feedback and learning statistics."""
        stats = {}
        if app.feedback_store:
            stats = app.feedback_store.get_statistics()

        return jsonify(stats)

    @app.route("/output/<path:filename>")
    def serve_output(filename: str):
        """Serve output files (CVs, PDFs)."""
        return send_file(os.path.join(output_dir, filename))

    @app.route("/refresh", methods=["POST"])
    def refresh_candidates():
        """Refresh candidates from LinkedIn."""
        pass

    return app


def _get_pending_candidates(store: Dict) -> List[Dict]:
    """Get all pending candidates."""
    return [
        _serialize_candidate(c)
        for c in store.values()
        if c.get("status") == "pending"
    ]


def _get_approved_candidates(store: Dict) -> List[Dict]:
    """Get all approved candidates."""
    return [
        _serialize_candidate(c)
        for c in store.values()
        if c.get("status") == "approved"
    ]


def _get_stats(store: Dict, feedback_store) -> Dict:
    """Get dashboard statistics."""
    stats = {
        "total": len(store),
        "pending": sum(1 for c in store.values() if c.get("status") == "pending"),
        "approved": sum(1 for c in store.values() if c.get("status") == "approved"),
        "rejected": sum(1 for c in store.values() if c.get("status") == "rejected"),
        "applied": sum(1 for c in store.values() if c.get("status") == "applied"),
    }

    if feedback_store:
        fb_stats = feedback_store.get_statistics()
        stats.update(fb_stats)

    return stats


def _serialize_candidate(candidate: Dict) -> Dict:
    """Serialize candidate for JSON/display."""
    return {
        "id": candidate.get("candidate_id", ""),
        "title": candidate.get("title", ""),
        "company": candidate.get("company", ""),
        "location": candidate.get("location", ""),
        "source": candidate.get("source", ""),
        "status": candidate.get("status", "pending"),
        "url": candidate.get("url", ""),
        "snippet": candidate.get("snippet", "")[:150] + "..." if candidate.get("snippet") else "",
        "llm_score": candidate.get("llm_score", 0),
        "collected_at": candidate.get("collected_at", ""),
    }
