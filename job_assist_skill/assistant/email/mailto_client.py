"""
Mailto Client - Email via mailto: protocol.

Opens the user's default email client with pre-filled email.
This is the simplest email method - no auth or MCP required.
"""

import json
import os
import subprocess
import webbrowser
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote, urlencode


class MailtoClient:
    """
    Email client using mailto: protocol.
    
    Opens the user's default email client with pre-filled fields.
    The user then reviews and sends manually.
    
    Usage:
        client = MailtoClient("Your Name", "your.email@example.com")
        
        # Create mailto URL
        url = client.create_mailto_url(
            to="hr@company.com",
            subject="Application for Software Engineer",
            body="Dear Hiring Manager...",
        )
        
        # Open email client
        client.open_email(
            to="hr@company.com",
            subject="Application",
            body="...",
        )
        
        # Save for manual sending
        client.save_email_json("email.json", to, subject, body)
    """
    
    def __init__(self, user_name: str = "", user_email: str = ""):
        """
        Initialize MailtoClient.
        
        Args:
            user_name: Sender's name
            user_email: Sender's email address
        """
        self.user_name = user_name
        self.user_email = user_email
    
    def create_mailto_url(
        self,
        to: str,
        subject: str = "",
        body: str = "",
        cc: str = "",
        bcc: str = "",
    ) -> str:
        """
        Create a mailto: URL with pre-filled fields.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body (plain text)
            cc: CC recipients (comma-separated)
            bcc: BCC recipients (comma-separated)
            
        Returns:
            mailto: URL string
        """
        if not to:
            raise ValueError("Recipient email (to) is required")
        
        params = {}
        
        if subject:
            params["subject"] = subject
        
        if body:
            params["body"] = body
        
        if cc:
            params["cc"] = cc
        
        if bcc:
            params["bcc"] = bcc
        
        if params:
            query = urlencode(params)
            return f"mailto:{to}?{query}"
        else:
            return f"mailto:{to}"
    
    def open_email(
        self,
        to: str,
        subject: str = "",
        body: str = "",
        cc: str = "",
        attachment_path: str = "",
    ) -> bool:
        """
        Open default email client with pre-filled email.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body
            cc: CC recipients
            attachment_path: Path to attachment (mentioned in body if provided)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            full_body = body
            
            if attachment_path:
                full_body += f"\n\n---\nCV: {os.path.basename(attachment_path)}\n(Please manually attach this file to the email)"
            
            url = self.create_mailto_url(
                to=to,
                subject=subject,
                body=full_body,
                cc=cc,
            )
            
            if os.name == 'nt':
                subprocess.run(["cmd", "/c", "start", "", url], shell=True)
            elif os.name == 'posix':
                try:
                    subprocess.run(["xdg-open", url], timeout=10)
                except FileNotFoundError:
                    try:
                        subprocess.run(["open", url], timeout=10)
                    except FileNotFoundError:
                        webbrowser.open(url)
            else:
                webbrowser.open(url)
            
            return True
            
        except Exception as e:
            print(f"Failed to open email client: {e}")
            return False
    
    def save_email_json(
        self,
        filepath: str,
        to: str,
        subject: str = "",
        body: str = "",
        cc: str = "",
        attachment_path: str = "",
    ) -> str:
        """
        Save email data to JSON for manual sending.
        
        Args:
            filepath: Path to save JSON file
            to: Recipient email
            subject: Email subject
            body: Email body
            cc: CC recipients
            attachment_path: Path to attachment
            
        Returns:
            Path to saved JSON file
        """
        data = {
            "to": to,
            "subject": subject,
            "body": body,
            "cc": cc or None,
            "attachment": attachment_path or None,
            "from": {
                "name": self.user_name,
                "email": self.user_email,
            }
        }
        
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return str(path)
    
    def format_email_body(
        self,
        job_title: str,
        company: str,
        recruiter_name: str = "",
        custom_message: str = "",
    ) -> str:
        """
        Format a standard application email body.
        
        Args:
            job_title: Position title
            company: Company name
            recruiter_name: Optional recruiter name for salutation
            custom_message: Optional custom message to add
            
        Returns:
            Formatted email body
        """
        salutation = f"Dear {recruiter_name}," if recruiter_name else "Dear Hiring Manager,"
        body = f"""{salutation}

I am writing to express my strong interest in the {job_title} position at {company}.

"""
        
        if custom_message:
            body += f"{custom_message}\n\n"
        
        body += """I have attached my CV for your review. I would welcome the opportunity to discuss how my skills and experience align with your team's needs.

Thank you for your consideration.

Best regards,
"""
        
        if self.user_name:
            body += f"{self.user_name}\n"
        
        if self.user_email:
            body += f"{self.user_email}\n"
        
        return body
    
    def create_application_email(
        self,
        to: str,
        job_title: str,
        company: str,
        cv_path: str = "",
        cover_letter_path: str = "",
        custom_message: str = "",
    ) -> dict:
        """
        Create a complete application email.
        
        Args:
            to: Recipient email
            job_title: Position title
            company: Company name
            cv_path: Path to CV PDF
            cover_letter_path: Path to cover letter PDF
            custom_message: Optional custom message
            
        Returns:
            Dict with to, subject, body, attachment paths
        """
        subject = f"Application for {job_title}"
        if company:
            subject += f" at {company}"
        
        body = self.format_email_body(job_title, company, custom_message)
        
        attachments = []
        if cv_path:
            attachments.append(cv_path)
        if cover_letter_path:
            attachments.append(cover_letter_path)
        
        attachment_note = ""
        if attachments:
            attachment_note = "\n\nAttachments:\n" + "\n".join(
                f"- {os.path.basename(p)}" for p in attachments
            )
        
        if attachment_note:
            body += attachment_note
        
        return {
            "to": to,
            "subject": subject,
            "body": body,
            "attachments": attachments,
        }


_default_client: Optional[MailtoClient] = None


def get_mailto_client(user_name: str = "", user_email: str = "") -> MailtoClient:
    """Get singleton MailtoClient instance."""
    global _default_client
    if _default_client is None:
        _default_client = MailtoClient(user_name, user_email)
    return _default_client
