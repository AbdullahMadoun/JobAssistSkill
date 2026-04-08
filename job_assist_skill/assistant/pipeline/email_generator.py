"""Generic local email draft generator for any job type."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional


PLACEHOLDER_PATTERNS = [
    re.compile(r"\bcompany\s*\d+\b", re.IGNORECASE),
    re.compile(r"\b(role|job|position|title)\s*\d+\b", re.IGNORECASE),
    re.compile(r"\[(company|role|job|title|name)[^\]]*\]", re.IGNORECASE),
    re.compile(r"<(company|role|job|title|name)[^>]*>", re.IGNORECASE),
    re.compile(r"\b(company|role|job|title|name)[ _-]?(name|placeholder|here)\b", re.IGNORECASE),
    re.compile(r"\b(insert|replace)\s+(company|role|job|title|name)\b", re.IGNORECASE),
]


@dataclass
class ApplicationEmail:
    """A structured application email draft."""

    subject: str
    body: str
    to: str
    cc: Optional[str] = None
    bcc: Optional[str] = None
    attachments: List[str] = field(default_factory=list)
    body_is_html: bool = False
    mailto_url: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


class EmailGenerator:
    """Create neutral, reusable application email drafts."""

    def generate_application_email(
        self,
        job: Dict,
        company: Optional[Dict] = None,
        recipient_email: str = "",
        recipient_name: str = "",
        sender_name: str = "Candidate",
        sender_email: str = "",
        cv_path: Optional[str] = None,
        cover_letter_path: Optional[str] = None,
        include_cover_letter: bool = True,
        template: str = "professional",
        user_summary: str = "",
        signature: str = "",
    ) -> ApplicationEmail:
        """Generate a professional email draft without domain assumptions."""
        del template
        warnings: List[str] = []

        raw_company_name = (company or {}).get("name") or job.get("company") or ""
        raw_job_title = job.get("title") or job.get("job_title") or "the role"
        raw_location = job.get("location") or ""
        raw_recipient_name = recipient_name or ""

        company_name, company_warnings = self._sanitize_value(raw_company_name, field_name="company")
        job_title, job_warnings = self._sanitize_value(raw_job_title, fallback="the role", field_name="job_title")
        location, _ = self._sanitize_value(raw_location, field_name="location")
        recipient_name, recipient_warnings = self._sanitize_value(raw_recipient_name, field_name="recipient_name")

        warnings.extend(company_warnings)
        warnings.extend(job_warnings)
        warnings.extend(recipient_warnings)

        subject = self._build_subject(job_title, company_name)
        body = self._build_body(
            job_title=job_title,
            company_name=company_name,
            location=location,
            recipient_name=recipient_name,
            sender_name=sender_name,
            sender_email=sender_email,
            user_summary=user_summary,
            signature=signature,
        )

        attachments: List[str] = []
        if cv_path:
            attachments.append(cv_path)
        if cover_letter_path and include_cover_letter:
            attachments.append(cover_letter_path)

        return ApplicationEmail(
            subject=subject,
            body=body,
            to=recipient_email,
            cc=sender_email or None,
            attachments=attachments,
            warnings=warnings,
        )

    def _sanitize_value(
        self,
        value: str,
        *,
        fallback: str = "",
        field_name: str,
    ) -> tuple[str, List[str]]:
        cleaned = " ".join((value or "").split()).strip()
        if not cleaned:
            return fallback, []

        if self._looks_like_placeholder(cleaned):
            return fallback, [f"placeholder_{field_name}_removed"]

        return cleaned, []

    def _looks_like_placeholder(self, value: str) -> bool:
        cleaned = " ".join((value or "").split()).strip()
        if not cleaned:
            return False
        return any(pattern.search(cleaned) for pattern in PLACEHOLDER_PATTERNS)

    def _build_subject(self, job_title: str, company_name: str) -> str:
        title = " ".join(job_title.split()).strip()
        if company_name:
            return f"Application for {title} at {company_name}"
        return f"Application for {title}"

    def _build_body(
        self,
        *,
        job_title: str,
        company_name: str,
        location: str,
        recipient_name: str,
        sender_name: str,
        sender_email: str,
        user_summary: str,
        signature: str,
    ) -> str:
        greeting = f"Dear {recipient_name.split()[0]}," if recipient_name.strip() else "Dear Hiring Team,"
        company_part = f" at {company_name}" if company_name else ""
        location_part = f" in {location}" if location else ""
        summary = user_summary.strip()
        summary_line = (
            f"{summary}\n\n"
            if summary
            else "I believe my background and recent work align well with the requirements of this opportunity.\n\n"
        )
        contact_line = f"\nYou can reach me at {sender_email}." if sender_email else ""
        closing = signature.strip() if signature.strip() else f"Best regards,\n{sender_name}"
        return (
            f"{greeting}\n\n"
            f"I am writing to express my interest in the {job_title} position{company_part}{location_part}.\n\n"
            f"{summary_line}"
            "I have attached my CV for review and would welcome the opportunity to discuss how my experience "
            "matches the role.\n"
            f"{contact_line}\n\n"
            f"{closing}"
        ).strip()


_default_generator: Optional[EmailGenerator] = None


def get_email_generator() -> EmailGenerator:
    """Get a singleton email generator instance."""
    global _default_generator
    if _default_generator is None:
        _default_generator = EmailGenerator()
    return _default_generator
