"""
Email Generator for job applications.

Generates personalized job application emails based on job data
and tailored CV/cover letter.
"""

import re
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ApplicationEmail:
    """Generated application email."""
    subject: str
    body: str
    to: str
    cc: Optional[str] = None
    bcc: Optional[str] = None
    attachments: List[str] = None
    body_is_html: bool = False

    def __post_init__(self):
        if self.attachments is None:
            self.attachments = []


class EmailGenerator:
    """
    Generates personalized job application emails.

    Usage:
        generator = EmailGenerator()
        email = generator.generate_application_email(
            job={"title": "Software Engineer", "company": "Microsoft"},
            company={"name": "Microsoft", "industry": "Tech"},
            recipient_email="careers@microsoft.com",
            cv_path="./output/cv.pdf",
            cover_letter_path="./output/cover_letter.pdf",
        )
    """

    def generate_application_email(
        self,
        job: Dict,
        company: Optional[Dict] = None,
        recipient_email: str = "",
        recipient_name: str = "",
        sender_name: str = "Your Name",
        sender_email: str = "your.email@example.com",
        cv_path: Optional[str] = None,
        cover_letter_path: Optional[str] = None,
        include_cover_letter: bool = True,
        template: str = "professional",
    ) -> ApplicationEmail:
        """
        Generate a job application email.

        Args:
            job: Job data dict with keys: title, company, location, description
            company: Company data dict (optional)
            recipient_email: HR/recruiter email
            recipient_name: HR/recruiter name (optional)
            sender_name: Your name
            sender_email: Your email
            cv_path: Path to tailored CV PDF
            cover_letter_path: Path to cover letter PDF (optional)
            include_cover_letter: Whether to include cover letter
            template: Email template style

        Returns:
            ApplicationEmail instance
        """
        # ELITE DATA VALIDATION: Reject generic mock strings
        temp_company = company.get('name', '') if company else (job.get('company', ''))
        company_name = temp_company if temp_company and "Company_" not in temp_company else ""
        
        temp_title = job.get('title', job.get('job_title', ''))
        job_title = temp_title if temp_title and "Position" not in temp_title else "AI Engineering"
        
        location = job.get('location', job.get('job_location', ''))

        subject = self._build_subject(job_title, company_name)

        body = self._build_body(
            job_title=job_title,
            company_name=company_name,
            location=location,
            recipient_name=recipient_name,
            sender_name=sender_name,
            sender_email=sender_email,
            template=template,
        )

        attachments = []
        if cv_path:
            attachments.append(cv_path)
        if cover_letter_path and include_cover_letter:
            attachments.append(cover_letter_path)

        cc = None
        if cover_letter_path and include_cover_letter:
            cc = sender_email

        return ApplicationEmail(
            subject=subject,
            body=body,
            to=recipient_email,
            cc=cc,
            attachments=attachments,
            body_is_html=False,
        )

    def _build_subject(self, job_title: str, company_name: str) -> str:
        """Build email subject line."""
        clean_title = self._clean_text(job_title)
        if company_name:
            return f"Application for {clean_title} at {company_name}"
        return f"Application for {clean_title}"

    def _build_body(
        self,
        job_title: str,
        company_name: str,
        location: str,
        recipient_name: str,
        sender_name: str,
        sender_email: str,
        template: str,
    ) -> str:
        """Build email body text."""
        greeting = self._build_greeting(recipient_name)
        introduction = self._build_introduction(job_title, company_name, location, sender_name)
        value_proposition = self._build_value_proposition(job_title, company_name)
        closing = self._build_closing(sender_name, sender_email)

        body = f"""{greeting}

{introduction}

{value_proposition}

I have attached my CV for your review. I would welcome the opportunity to discuss how my skills and experience align with {company_name or 'this role'}'s needs.

{closing}

Best regards,
{sender_name}"""

        return body

    def _build_greeting(self, recipient_name: str) -> str:
        """Build email greeting."""
        if recipient_name and recipient_name.strip():
            # Handle "First Last" -> "First" for a personal touch
            first_name = recipient_name.strip().split()[0]
            return f"Dear {first_name},"
        return "Dear Hiring Manager,"

    def _build_introduction(
        self,
        job_title: str,
        company_name: str,
        location: str,
        sender_name: str,
    ) -> str:
        """Build introduction paragraph."""
        name_parts = sender_name.split()
        first_name = name_parts[0] if name_parts else sender_name

        location_part = f" in {location}" if location else ""
        company_part = f" at {company_name}" if company_name else ""

        return (
            f"I am writing to express my strong interest in the {job_title} "
            f"position{company_part}{location_part}. "
            f"As a final-year Software Engineering student with a strong academic background "
            f"and specialization in AI/ML, I am excited about opportunities where "
            f"I can contribute to meaningful projects."
        )

    def _build_value_proposition(
        self,
        job_title: str,
        company_name: str,
    ) -> str:
        """Build value proposition paragraph."""
        value_props = []

        if any(kw in job_title.lower() for kw in ['software', 'engineer', 'developer']):
            value_props.append(
                "My experience building end-to-end computer vision pipelines, "
                "implementing few-shot classification systems, and working with "
                "modern ML frameworks (PyTorch, TensorFlow, scikit-learn) has given "
                "me strong foundations in production-quality development."
            )

        if any(kw in job_title.lower() for kw in ['data', 'ml', 'ai', 'machine learning']):
            value_props.append(
                "I have hands-on experience with the full ML lifecycle—from data "
                "preprocessing and model training to evaluation and optimization. "
                "My recent work includes building high-performance computer vision "
                "pipelines for real-world applications."
            )

        if 'analyst' in job_title.lower():
            value_props.append(
                "Through my previous experience, I developed fraud risk metrics "
                "that flagged hundreds of high-probability cases and built semantic "
                "text-matching tools that cut manual tasks from weeks to minutes."
            )

        if not value_props:
            value_props.append(
                "I bring strong technical skills in Python, Java, and SQL, "
                "along with practical experience in Docker, FastAPI, and CI/CD pipelines. "
                "I am a quick learner who thrives in collaborative environments."
            )

        return value_props[0]

    def _build_closing(self, sender_name: str, sender_email: str) -> str:
        """Build email closing."""
        return f"I can be reached at {sender_email}"

    def _clean_text(self, text: str) -> str:
        """Clean text for use in subject lines."""
        text = text.strip()
        text = re.sub(r'\s+', ' ', text)
        return text

    def generate_follow_up_email(
        self,
        original_email: ApplicationEmail,
        days_since: int = 5,
    ) -> ApplicationEmail:
        """
        Generate a follow-up email for a previously sent application.

        Args:
            original_email: The original application email
            days_since: Days since the original application

        Returns:
            New ApplicationEmail for follow-up
        """
        subject = f"Following Up: {original_email.subject}"

        body = f"""Dear Hiring Manager,

I hope this message finds you well. I wanted to follow up on my application
for the position referenced in the subject line, which I submitted approximately
{days_since} days ago.

I remain very interested in this opportunity and would love to discuss how
my skills in AI/ML and software engineering could contribute to your team.
Please let me know if there is any additional information I can provide.

Thank you for your time and consideration.

Best regards,
{self._extract_sender_name(original_email.body)}"""

        return ApplicationEmail(
            subject=subject,
            body=body,
            to=original_email.to,
            cc=original_email.cc,
        )

    def _extract_sender_name(self, body: str) -> str:
        """Extract sender name from email body."""
        match = re.search(r'Best regards,\s*\n?\s*([^\n]+)', body)
        return match.group(1).strip() if match else "Your Name"


_default_generator: Optional[EmailGenerator] = None


def get_email_generator() -> EmailGenerator:
    """Get singleton email generator instance."""
    global _default_generator
    if _default_generator is None:
        _default_generator = EmailGenerator()
    return _default_generator
