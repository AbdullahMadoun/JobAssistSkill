#!/usr/bin/env python
"""
Run All - Complete Career Assistant Workflow

Searches LinkedIn, tailors CV + cover letter, generates email.

Usage:
    python run_all.py --preset gulf_tech --send      # Full auto with email
    python run_all.py --preset us_tech --no-send   # Preview only
    python run_all.py --roles "software" --location "Remote" --limit 10 --send
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime
import re

sys.path.insert(0, str(Path(__file__).parent))


def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_step(step_num, text):
    print(f"\n{'='*60}")
    print(f"  STEP {step_num}: {text}")
    print("=" * 60)


class MCPEmailClient:
    """
    MCP Email Client for sending emails via Outlook/MCP.
    """
    
    def __init__(self, method="auto"):
        self.method = method
        self.sent_emails = []
        
    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str = None,
        attachments: list = None,
        smtp_server: str = None,
        smtp_port: int = 587,
    ) -> dict:
        """
        Send email via available method.
        """
        if not to:
            return {"success": False, "error": "No recipient email provided"}
        
        # Save to JSON for manual sending by default in this generic version
        return self._save_for_manual_send(to, subject, body, cc, attachments)
    
    def _save_for_manual_send(self, to, subject, body, cc, attachments) -> dict:
        """Save email data to JSON for manual sending."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"output/email_to_send_{timestamp}.json"
        
        email_data = {
            "to": to,
            "subject": subject,
            "body": body,
            "cc": cc,
            "attachments": attachments or [],
            "status": "pending_manual_send",
        }
        
        os.makedirs("output", exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(email_data, f, indent=2)
        
        return {
            "success": True,
            "method": "saved_to_file",
            "file": filename,
            "message": f"Email saved to {filename} - send manually or configure SMTP"
        }


async def run_all(args):
    """Run complete workflow: search → tailor → email."""
    from job_assist_skill.scraper import BrowserManager, HiringPostSearcher
    from job_assist_skill.assistant import (
        CVTailoringPipeline, LaTeXCompiler, EmailGenerator, 
    )
    from job_assist_skill import keywords as kw as kw

    session_path = args.session or "linkedin_session.json"
    if not os.path.exists(session_path):
        print(f"ERROR: Session file not found: {session_path}")
        print("Run: python main.py login --session linkedin_session.json")
        return 1

    cv_path = Path(__file__).parent / "cv_template.tex"
    if not cv_path.exists():
        print(f"ERROR: CV template not found: {cv_path}")
        return 1

    cv_latex = cv_path.read_text(encoding='utf-8')

    os.makedirs("output", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"output/run_all_{timestamp}.json"
    
    all_results = {
        "timestamp": timestamp,
        "preset": args.preset,
        "roles": args.roles,
        "location": args.location,
        "posts": [],
        "cvs": [],
        "emails": [],
        "sent": [],
        "failed": [],
    }

    # =========================================================================
    # STEP 1: Search LinkedIn
    # =========================================================================
    print_step(1, "Search LinkedIn for Hiring Posts")

    if args.preset:
        if args.preset not in kw.QUICK_SEARCHES:
            print(f"ERROR: Unknown preset '{args.preset}'")
            return 1
        config = kw.QUICK_SEARCHES[args.preset]
        role_list = config.get("roles", [])
        loc_list = config.get("locations", [])
        print(f"Using preset: {args.preset}")
    elif args.roles:
        role_list = args.roles.split(',')
        loc_list = args.location.split(',') if args.location else None
    else:
        role_list = ["software_engineer"]
        loc_list = None

    roles_to_search = []
    for r in role_list:
        if r in kw.ROLES:
            roles_to_search.extend(kw.ROLES[r][:3])
        else:
            roles_to_search.append(r)

    locs_to_search = None
    if loc_list:
        locs_to_search = []
        for l in loc_list:
            if l in kw.LOCATIONS:
                locs_to_search.extend(kw.LOCATIONS[l][:2])
            else:
                locs_to_search.append(l)

    print(f"Roles: {roles_to_search[:5]}")
    print(f"Locations: {locs_to_search}")

    async with BrowserManager(headless=args.headless, stealth=True) as browser:
        await browser.load_session(session_path)
        await asyncio.sleep(2)

        searcher = HiringPostSearcher(browser.page)
        posts = await searcher.search_for_hiring(
            roles=roles_to_search[:5],
            companies=args.companies.split(',') if args.companies else None,
            locations=locs_to_search,
            posts_per_query=args.limit,
            min_posts=args.min_posts,
            max_time_per_query=args.timeout,
            max_hours_age=args.hours,
        )

    print(f"\nFound {len(posts)} hiring posts")

    if not posts:
        print("No posts found. Try different keywords or increase --timeout/--limit")
        return 0

    # =========================================================================
    # STEP 2: Process each post
    # =========================================================================
    print_step(2, "Process Posts - CV, Email")

    pipeline = CVTailoringPipeline()
    compiler = LaTeXCompiler()
    generator = EmailGenerator()
    email_client = MCPEmailClient(method=args.email_method)

    for i, post in enumerate(posts[:args.max_candidates]):
        company = post.company_name or f"Company_{i+1}"
        job_text = post.text or ""
        post_url = post.linkedin_url or ""
        locations = post.locations or []
        author = post.author_name or ""

        print(f"\n{'─'*60}")
        print(f"Post #{i+1}: {company}")
        print(f"URL: {post_url[:80]}...")
        print(f"Locations: {locations}")

        if not job_text:
            print("  ⚠ Skipping: No job text")
            continue

        # Prepare CV Tailoring
        print("  📄 Preparing CV tailoring...")
        tailoring_result = pipeline.prepare(job_text, cv_latex, output_dir="output")

        if not tailoring_result.success:
            print(f"  ❌ Tailoring error: {tailoring_result.error}")
            continue

        session_id = tailoring_result.context.tailoring_session_id
        
        # Compile CV to PDF (using original template as placeholder if no LLM)
        print("  📑 Compiling CV to PDF...")
        cv_pdf_path = f"output/cv_{session_id}_tailored.pdf"
        compile_result = compiler.compile_one_page(cv_latex, cv_pdf_path)
        
        # Generate Email
        print("  📧 Generating application email...")
        job_title = author or "the position"
        email = generator.generate_application_email(
            job={
                "title": job_title,
                "company": company,
                "location": ", ".join(locations) if locations else "",
            },
            cv_path=cv_pdf_path,
        )

        recruiter_email = extract_recruiter_email(job_text) or ""
        
        email_data = {
            "subject": email.subject,
            "body": email.body,
            "to": recruiter_email,
            "cc": email.cc,
            "attachments": [cv_pdf_path] if cv_pdf_path else [],
        }

        email_json_path = f"output/email_{session_id}.json"
        Path(email_json_path).write_text(json.dumps(email_data, indent=2), encoding='utf-8')
        print(f"     Email saved: {email_json_path}")

        # Store results
        all_results["posts"].append({
            "index": i + 1,
            "company": company,
            "url": post_url,
            "text": job_text[:500],
        })

    print_step(3, "Summary")
    Path(results_file).write_text(json.dumps(all_results, indent=2, default=str), encoding='utf-8')
    print(f"\n📊 Results processed: {len(all_results['posts'])}")
    print(f"📁 Full results: {results_file}")
    return 0


def extract_recruiter_email(text: str) -> str:
    """Extract email from job posting text."""
    if not text:
        return None
    patterns = [r'[\w.+-]+@[\w-]+\.[\w.-]+']
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            email = match.lower()
            if any(skip in email for skip in ['noreply', 'no-reply', 'jobs@', 'careers@', 'hr@', 'info@']):
                continue
            if 'linkedin' not in email and '.' in email:
                return email
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Complete Career Assistant: Search → CV → Email"
    )
    parser.add_argument("--preset", "-p", help="Preset (gulf_tech, us_tech, etc.)")
    parser.add_argument("--roles", help="Comma-separated role categories")
    parser.add_argument("--location", help="Comma-separated location categories")
    parser.add_argument("--companies", help="Comma-separated companies")
    parser.add_argument("--limit", type=int, default=10, help="Max posts per query")
    parser.add_argument("--min-posts", type=int, default=3, help="Min posts to collect")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout per query")
    parser.add_argument("--hours", type=int, default=24, help="Filter to last N hours")
    parser.add_argument("--max-candidates", type=int, default=5, help="Max candidates to process")
    parser.add_argument("--session", help="Session file path")
    parser.add_argument("--headless", action="store_true", help="Run headless")
    parser.add_argument("--send", action="store_true", help="Send emails (simulated)")
    parser.add_argument("--no-send", action="store_true", help="Don't send, just prepare")
    parser.add_argument("--email-method", default="auto", help="Email sending method")

    args = parser.parse_args()
    if not args.preset and not args.roles:
        print("ERROR: Provide --preset or --roles")
        return 1
    return asyncio.run(run_all(args))


if __name__ == "__main__":
    exit(main())
