#!/usr/bin/env python
"""
Career Assistant CLI - Main entry point for the career assistant skill.

Usage:
    python main.py search "software engineer" --location "Remote"
    python main.py tailor --job-text "We're hiring..." --cv cv_template.tex
    python main.py email --job "Software Engineer" --company "Company Name"
    python main.py run --roles "Python Developer" --companies "Microsoft,Google"
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def cmd_search(args):
    """Search for jobs/hiring posts."""
    from job_assist_skill.scraper import BrowserManager, HiringPostSearcher
    from job_assist_skill import keywords as kw as kw
    
    session_path = args.session or "linkedin_session.json"
    if not os.path.exists(session_path):
        print(f"ERROR: Session file not found: {session_path}")
        print("Run: python main.py login")
        return 1
    
    # Handle --list-presets
    if args.list_presets:
        print("Available presets from keywords.py:")
        for name, config in kw.QUICK_SEARCHES.items():
            roles_str = ",".join(config.get("roles", []))
            locs_str = ",".join(config.get("locations", []))
            print(f"  {name}: roles={roles_str}, locations={locs_str}")
        return 0
    
    # Build search queries
    if args.preset:
        if args.preset not in kw.QUICK_SEARCHES:
            print(f"ERROR: Unknown preset '{args.preset}'")
            print("Use --list-presets to see available presets")
            return 1
        config = kw.QUICK_SEARCHES[args.preset]
        role_list = config.get("roles", [])
        loc_list = config.get("locations", [])
        print(f"Using preset: {args.preset}")
        print(f"Roles: {role_list}")
        print(f"Locations: {loc_list}")
    elif args.roles:
        role_list = args.roles.split(',')
        loc_list = args.location.split(',') if args.location else None
    elif args.keywords:
        role_list = [args.keywords]
        loc_list = args.location.split(',') if args.location else None
    else:
        print("ERROR: Provide keywords, --preset, or --roles")
        return 1
    
    # Convert role categories to actual keywords
    roles_to_search = []
    for r in role_list:
        if r in kw.ROLES:
            roles_to_search.extend(kw.ROLES[r][:3])
        else:
            roles_to_search.append(r)
    
    # Convert location categories to actual keywords
    locs_to_search = None
    if loc_list:
        locs_to_search = []
        for l in loc_list:
            if l in kw.LOCATIONS:
                locs_to_search.extend(kw.LOCATIONS[l][:2])
            else:
                locs_to_search.append(l)
    
    print(f"Searching for: {roles_to_search[:3]}...")
    if locs_to_search:
        print(f"Locations: {locs_to_search[:3]}")
    
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
        
        print(f"\n=== Found {len(posts)} hiring posts ===\n")
        
        for i, post in enumerate(posts[:args.limit]):
            print(f"[{i+1}] {post.company_name or 'Unknown Company'}")
            print(f"    URL: {post.linkedin_url}")
            print(f"    Text: {(post.text or '')[:150]}...")
            print(f"    Locations: {post.locations}")
            print(f"    Date: {post.posted_date}")
            print()
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump([{
                    'company': p.company_name,
                    'url': p.linkedin_url,
                    'text': p.text,
                    'locations': p.locations,
                    'date': p.posted_date,
                    'author': p.author_name,
                } for p in posts], f, indent=2)
            print(f"Saved results to {args.output}")
        
    return 0


def cmd_tailor(args):
    """Prepare CV tailoring (generates prompts for LLM)."""
    from job_assist_skill.assistant import CVTailoringPipeline
    
    if args.job_file:
        job_text = Path(args.job_file).read_text(encoding='utf-8')
    elif args.job_text:
        job_text = args.job_text
    else:
        print("ERROR: Provide --job-text or --job-file")
        return 1
    
    if args.cv_file:
        cv_latex = Path(args.cv_file).read_text(encoding='utf-8')
    else:
        cv_path = Path(__file__).parent / "cv_template.tex"
        if cv_path.exists():
            cv_latex = cv_path.read_text(encoding='utf-8')
        else:
            print(f"ERROR: CV template not found: {cv_path}")
            print("Please provide --cv-file or create cv_template.tex")
            return 1
    
    print("Preparing CV tailoring context...")
    
    pipeline = CVTailoringPipeline()
    result = pipeline.prepare(job_text, cv_latex, output_dir=args.output or "output")
    
    if result.success:
        print(f"SUCCESS: Tailoring context prepared")
        print(f"  Session ID: {result.context.tailoring_session_id}")
        print(f"  LaTeX saved to: {result.latex_path}")
        print(f"\nNext: Send the alignment_prompt to LLM and call apply_llm_results()")
        
        if args.save_context:
            ctx_path = os.path.join(args.output or "output", f"context_{result.context.tailoring_session_id}.json")
            with open(ctx_path, 'w') as f:
                json.dump({
                    'session_id': result.context.tailoring_session_id,
                    'alignment_prompt': result.context.alignment_prompt,
                    'job_requirements': result.context.job_requirements,
                }, f, indent=2)
            print(f"  Context saved to: {ctx_path}")
    else:
        print(f"ERROR: {result.error}")
        return 1
    
    return 0


def cmd_compile(args):
    """Compile LaTeX to PDF."""
    from job_assist_skill.assistant import LaTeXCompiler
    
    if not args.latex_file:
        print("ERROR: Provide --latex-file")
        return 1
    
    latex = Path(args.latex_file).read_text(encoding='utf-8')
    output = args.output or args.latex_file.replace('.tex', '.pdf')
    
    print(f"Compiling {args.latex_file} to {output}...")
    
    compiler = LaTeXCompiler()
    result = compiler.compile_one_page(latex, output)
    
    if result['success']:
        print(f"SUCCESS: PDF created at {result['pdf_path']} ({result['pages']} page(s))")
        if result.get('issues'):
            print(f"Issues: {result['issues']}")
    else:
        print(f"ERROR: Compilation failed: {result.get('issues')}")
        return 1
    
    return 0


def cmd_email(args):
    """Generate application email."""
    from job_assist_skill.assistant import EmailGenerator
    
    generator = EmailGenerator()
    
    email = generator.generate_application_email(
        job={
            "title": args.job or "Position",
            "company": args.company or "Company",
            "location": args.location or "",
        },
        recipient_email=args.to or "",
        cv_path=args.cv,
    )
    
    print(f"Subject: {email.subject}")
    print(f"To: {email.to}")
    if email.cc:
        print(f"CC: {email.cc}")
    print(f"\n--- Email Body ---\n{email.body}\n---")
    
    if args.output:
        email_data = {
            "subject": email.subject,
            "body": email.body,
            "to": email.to,
            "cc": email.cc,
        }
        with open(args.output, 'w') as f:
            json.dump(email_data, f, indent=2)
        print(f"Email saved to {args.output}")
    
    return 0


def cmd_ui(args):
    """Start the web UI."""
    from job_assist_skill.assistant.ui.app import create_app
    from job_assist_skill.assistant import FeedbackStore
    
    output_dir = args.output or "output"
    os.makedirs(output_dir, exist_ok=True)
    
    cv_template = Path(__file__).parent / "cv_template.tex"
    
    feedback_store = FeedbackStore() if args.learn else None
    
    app = create_app(
        output_dir=output_dir,
        cv_latex_template=str(cv_template) if cv_template.exists() else None,
        feedback_store=feedback_store,
    )
    
    print(f"Starting UI at http://localhost:{args.port}")
    print(f"Output directory: {output_dir}")
    app.run(host='0.0.0.0', port=args.port, debug=not args.production)


async def cmd_login(args):
    """Login to LinkedIn and save session."""
    from job_assist_skill.scraper import BrowserManager, wait_for_manual_login, save_session
    
    print("Opening LinkedIn login page...")
    async with BrowserManager(headless=False, stealth=True) as browser:
        page = browser.page
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        
        print("Please log in manually in the browser window...")
        await wait_for_manual_login(page, timeout=300)
        
        session_path = args.session or "linkedin_session.json"
        await browser.save_session(session_path)
        print(f"Session saved to {session_path}")
    
    return 0


async def cmd_demo(args):
    """Run a demo of the full workflow."""
    from job_assist_skill.scraper import BrowserManager, HiringPostSearcher
    from job_assist_skill.assistant import CVTailoringPipeline, LaTeXCompiler, EmailGenerator
    
    session_path = args.session or "linkedin_session.json"
    if not os.path.exists(session_path):
        print(f"ERROR: Session file not found: {session_path}")
        return 1
    
    cv_path = Path(__file__).parent / "cv_template.tex"
    if not cv_path.exists():
        print(f"ERROR: CV file not found: {cv_path}")
        return 1
    
    print("=== Career Assistant Demo ===\n")
    
    # Step 1: Search
    print("Step 1: Searching LinkedIn for hiring posts...")
    async with BrowserManager(headless=args.headless, stealth=True) as browser:
        await browser.load_session(session_path)
        await asyncio.sleep(2)
        
        searcher = HiringPostSearcher(browser.page)
        posts = await searcher.search_for_hiring(
            roles=["software engineer"],
            posts_per_query=5,
            min_posts=3,
            max_hours_age=24,
        )
    
    print(f"Found {len(posts)} posts\n")
    
    if not posts:
        print("No posts found. Try running with more time or different keywords.")
        return 0
    
    # Step 2: Pick first post and prepare tailoring
    post = posts[0]
    print(f"Step 2: Preparing CV tailoring for: {post.company_name or 'Unknown'}")
    
    job_text = post.text or ""
    cv_latex = cv_path.read_text(encoding='utf-8')
    
    pipeline = CVTailoringPipeline()
    result = pipeline.prepare(job_text, cv_latex, output_dir="output")
    
    if not result.success:
        print(f"ERROR: {result.error}")
        return 1
    
    print(f"  Session ID: {result.context.tailoring_session_id}")
    print(f"  Alignment prompt length: {len(result.context.alignment_prompt)} chars")
    print(f"\n  (In production, you would send alignment_prompt to LLM here)")
    
    # Step 3: Show what LLM output would look like
    print("\nStep 3: Simulating LLM response...")
    sample_alignment = {
        "overall_score": 65,
        "sections": [
            {"name": "Experience", "scoring": {"overall": 60}},
            {"name": "Skills", "scoring": {"overall": 70}},
        ]
    }
    sample_changes = [
        {
            "change_type": "keep",
            "section_name": "Experience",
            "original_text": "",
            "edited_text": "",
        }
    ]
    
    tailored_latex = pipeline.apply_llm_results(
        result.context,
        sample_alignment,
        sample_changes,
        cv_latex,
    )
    print(f"  Applied {len(sample_changes)} changes")
    
    # Step 4: Compile
    print("\nStep 4: Compiling to PDF...")
    os.makedirs("output", exist_ok=True)
    compiler = LaTeXCompiler()
    compile_result = compiler.compile_one_page(tailored_latex, "output/demo_cv.pdf")
    
    if compile_result['success']:
        print(f"  PDF created: {compile_result['pdf_path']} ({compile_result['pages']} page(s))")
    else:
        print(f"  PDF compilation issues: {compile_result.get('issues')}")
    
    # Step 5: Generate email
    print("\nStep 5: Generating application email...")
    generator = EmailGenerator()
    email = generator.generate_application_email(
        job={"title": "Software Engineer", "company": post.company_name or "Company"},
        cv_path="output/demo_cv.pdf" if compile_result['success'] else None,
    )
    print(f"  Subject: {email.subject}")
    print(f"  Body preview: {email.body[:200]}...")
    
    print("\n=== Demo Complete ===")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Career Assistant - Job search and CV tailoring")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for hiring posts")
    search_parser.add_argument("keywords", nargs="?", help="Search keywords (or use --preset)")
    search_parser.add_argument("--preset", "-p", help="Use preset from keywords.py (remote_software, us_tech, gulf_tech, etc.)")
    search_parser.add_argument("--roles", help="Comma-separated role categories from keywords.py (e.g., software_engineer,data_ml)")
    search_parser.add_argument("--location", help="Location filter")
    search_parser.add_argument("--companies", help="Comma-separated companies")
    search_parser.add_argument("--limit", type=int, default=10, help="Max posts per query")
    search_parser.add_argument("--min-posts", type=int, default=3, help="Min posts to collect")
    search_parser.add_argument("--timeout", type=int, default=60, help="Timeout per query")
    search_parser.add_argument("--hours", type=int, default=24, help="Filter to last N hours")
    search_parser.add_argument("--session", help="Session file path")
    search_parser.add_argument("--output", help="Output JSON file")
    search_parser.add_argument("--headless", action="store_true", help="Run headless")
    search_parser.add_argument("--list-presets", action="store_true", help="List available presets")

    # Tailor command
    tailor_parser = subparsers.add_parser("tailor", help="Prepare CV tailoring")
    tailor_parser.add_argument("--job-text", help="Job posting text")
    tailor_parser.add_argument("--job-file", help="Job posting file")
    tailor_parser.add_argument("--cv-file", help="CV LaTeX file")
    tailor_parser.add_argument("--output", help="Output directory")
    tailor_parser.add_argument("--save-context", action="store_true", help="Save context JSON")

    # Compile command
    compile_parser = subparsers.add_parser("compile", help="Compile LaTeX to PDF")
    compile_parser.add_argument("--latex-file", help="LaTeX file")
    compile_parser.add_argument("--output", help="Output PDF path")

    # Email command
    email_parser = subparsers.add_parser("email", help="Generate application email")
    email_parser.add_argument("--job", help="Job title")
    email_parser.add_argument("--company", help="Company name")
    email_parser.add_argument("--location", help="Location")
    email_parser.add_argument("--to", help="Recipient email")
    email_parser.add_argument("--cv", help="CV PDF path")
    email_parser.add_argument("--output", help="Output JSON file")

    # UI command
    ui_parser = subparsers.add_parser("ui", help="Start web UI")
    ui_parser.add_argument("--port", type=int, default=5050, help="UI port")
    ui_parser.add_argument("--output", help="Output directory")
    ui_parser.add_argument("--no-learn", dest="learn", action="store_false", help="Disable learning")
    ui_parser.add_argument("--production", action="store_true", help="Production mode")

    # Login command
    login_parser = subparsers.add_parser("login", help="Login to LinkedIn")
    login_parser.add_argument("--session", help="Session output path")

    # Demo command
    demo_parser = subparsers.add_parser("demo", help="Run full demo")
    demo_parser.add_argument("--session", help="Session file path")
    demo_parser.add_argument("--headless", action="store_true", help="Run headless")

    args = parser.parse_args()

    if args.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    if args.command == "search":
        return asyncio.run(cmd_search(args))
    elif args.command == "tailor":
        return cmd_tailor(args)
    elif args.command == "compile":
        return cmd_compile(args)
    elif args.command == "email":
        return cmd_email(args)
    elif args.command == "ui":
        cmd_ui(args)
    elif args.command == "login":
        return asyncio.run(cmd_login(args))
    elif args.command == "demo":
        return asyncio.run(cmd_demo(args))
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    exit(main())
