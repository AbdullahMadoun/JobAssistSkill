#!/usr/bin/env python
"""Agent-controlled CLI for dual-stream scraping and local CV workflows."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from job_assist_skill import keywords as kw
from job_assist_skill.assistant import (
    CVAlignment,
    CVReplacer,
    CVTailoringPipeline,
    CareerAssistant,
    CoverLetterGenerator,
    FeedbackStore,
)
from job_assist_skill.scraper import (
    BrowserManager,
    is_logged_in,
    load_credentials_from_env,
    login_with_credentials,
    wait_for_manual_login,
)


def _csv_to_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _read_text_arg(text_value: Optional[str], file_value: Optional[str], label: str) -> str:
    if text_value:
        return text_value
    if file_value:
        return Path(file_value).read_text(encoding="utf-8")
    raise ValueError(f"Provide --{label}-text or --{label}-file")


def _read_json(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(payload: Any, path: Optional[str] = None) -> Optional[Path]:
    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    if not path:
        print(rendered)
        return None
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Saved {output}")
    return output


def _prompt_payload(
    *,
    stage: str,
    prompt: Dict[str, str],
    expected_output: str,
    quality_checks: List[str],
    suggested_output: str,
) -> Dict[str, Any]:
    return {
        "stage": stage,
        "system": prompt["system"],
        "user": prompt["user"],
        "expected_output": expected_output,
        "quality_checks": quality_checks,
        "suggested_output_file": suggested_output,
    }


async def cmd_search(args: argparse.Namespace) -> int:
    assistant = CareerAssistant(memory_path=args.memory_path, output_dir=args.output_dir)

    if args.list_presets:
        for name, config in sorted(kw.QUICK_SEARCHES.items()):
            roles = ",".join(config.get("roles", []))
            locations = ",".join(config.get("locations", []))
            print(f"{name}: roles={roles} | locations={locations}")
        return 0

    memory_roles = assistant.memory.get_value("search.roles", []) or []
    memory_locations = assistant.memory.get_value("search.locations", []) or []
    memory_companies = assistant.memory.get_value("search.companies", []) or []

    roles = []
    locations = _csv_to_list(args.locations or args.location) or list(memory_locations)
    companies = _csv_to_list(args.companies) or list(memory_companies)

    if args.preset:
        if args.preset not in kw.QUICK_SEARCHES:
            print(f"Unknown preset: {args.preset}", file=sys.stderr)
            return 1
        preset = kw.QUICK_SEARCHES[args.preset]
        roles.extend(preset.get("roles", []))
        if not locations:
            locations = preset.get("locations", [])

    if args.query:
        roles.append(args.query)
    roles.extend(_csv_to_list(args.roles))

    if not roles:
        roles.extend(memory_roles)

    if not roles:
        print("Provide a query, --roles, or --preset.", file=sys.stderr)
        return 1

    try:
        results = await assistant.search(
            roles=roles,
            locations=locations,
            companies=companies,
            stream=args.stream,
            limit=args.limit,
            min_posts=args.min_posts,
            timeout=args.timeout,
            max_hours_age=args.hours,
            session_path=args.session,
            headless=args.headless,
            expand_job_details=not args.no_job_details,
            email_only_posts=args.email_only_posts,
        )
    except Exception as exc:
        print(f"Search failed: {exc}", file=sys.stderr)
        return 1

    payload = [result.to_dict() for result in results]
    if args.output:
        assistant.save_search_results(results, args.output)
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    if results:
        best = results[0]
        print(
            "Top result: "
            f"source={best.source} | title={best.title or 'Untitled'} | "
            f"company={best.company or 'Unknown'} | score={best.match_score} | "
            f"next={best.next_action} | url={best.url}"
        )
    return 0


async def cmd_login(args: argparse.Namespace) -> int:
    assistant = CareerAssistant(memory_path=args.memory_path)
    session_path = Path(args.session or assistant.memory.get_value("files.linkedin_session", "linkedin_session.json"))
    if not session_path.is_absolute():
        session_path = assistant.repo_root / session_path
    session_path.parent.mkdir(parents=True, exist_ok=True)

    print("Opening LinkedIn login page...")
    async with BrowserManager(headless=False, stealth=True) as browser:
        if session_path.exists() and not args.force:
            try:
                await browser.load_session(str(session_path))
                await browser.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                if await is_logged_in(browser.page):
                    try:
                        session_value = str(session_path.relative_to(assistant.repo_root))
                    except ValueError:
                        session_value = str(session_path)
                    assistant.memory.remember_files(linkedin_session=session_value)
                    print(f"Existing LinkedIn session is still valid: {session_path}")
                    return 0
            except Exception:
                pass
        if args.auto:
            email, password = load_credentials_from_env()
            if not email or not password:
                print("No LinkedIn credentials found in .env/environment.", file=sys.stderr)
                return 1
            print("Attempting automatic login using environment credentials...")
            await login_with_credentials(browser.page, email=email, password=password, warm_up=True)
        else:
            await browser.page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
            print("Complete login manually in the browser window.")
            await wait_for_manual_login(browser.page, timeout=args.timeout * 1000)
        await browser.save_session(str(session_path))

    try:
        session_value = str(session_path.relative_to(assistant.repo_root))
    except ValueError:
        session_value = str(session_path)
    assistant.memory.remember_files(linkedin_session=session_value)
    print(f"Session saved to {session_path}")
    return 0


def cmd_tailor_prepare(args: argparse.Namespace) -> int:
    assistant = CareerAssistant(memory_path=args.memory_path, output_dir=args.output_dir)
    try:
        job_text = _read_text_arg(args.job_text, args.job_file, "job")
        result = assistant.prepare_tailoring(
            job_text=job_text,
            cv_path=args.cv_file,
            output_dir=args.output_dir,
        )
    except Exception as exc:
        print(f"Tailoring preparation failed: {exc}", file=sys.stderr)
        return 1

    if not result.success:
        print(result.error, file=sys.stderr)
        return 1

    if args.context_out and result.context:
        Path(args.context_out).write_text(
            json.dumps(result.context.__dict__, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Saved {args.context_out}")

    print(f"Context: {result.context_path}")
    print(f"Source CV: {result.latex_path}")
    return 0


def cmd_tailor_alignment(args: argparse.Namespace) -> int:
    assistant = CareerAssistant(memory_path=args.memory_path)
    cv_path = assistant.resolve_cv_path(args.cv_file)
    cv_latex = cv_path.read_text(encoding="utf-8")
    parsed_job = _read_json(args.parsed_job)
    prompt = CVTailoringPipeline().build_alignment_prompt(parsed_job=parsed_job, cv_latex=cv_latex)
    payload = _prompt_payload(
        stage="alignment",
        prompt=prompt,
        expected_output=(
            "One JSON object with overall_score, overall_verdict, sections, missing_from_cv, "
            "strongest_matches, recommended_emphasis, priority_gaps, and evidence_candidates."
        ),
        quality_checks=[
            "Return valid JSON only.",
            "Use only evidence already present in the CV and parsed job posting.",
            "Review every meaningful bullet or line in the CV before scoring.",
            "Never invent skills, certifications, employers, dates, or metrics.",
        ],
        suggested_output="alignment.json",
    )
    _write_json(payload, args.output)
    return 0


def cmd_tailor_replace(args: argparse.Namespace) -> int:
    assistant = CareerAssistant(memory_path=args.memory_path)
    cv_path = assistant.resolve_cv_path(args.cv_file)
    cv_latex = cv_path.read_text(encoding="utf-8")
    alignment = _read_json(args.alignment)
    stories = _read_json(args.stories) if args.stories else []
    options = _read_json(args.options) if args.options else {}
    prompt = CVTailoringPipeline().build_replace_prompt(
        cv_latex=cv_latex,
        alignment=alignment,
        stories=stories,
        options=options,
    )
    payload = _prompt_payload(
        stage="replace",
        prompt=prompt,
        expected_output=(
            "One JSON object with summary, alignment_improvement, strategic_recommendations, "
            "changes, and risks. Each changes entry must preserve exact original_text substrings."
        ),
        quality_checks=[
            "Return valid JSON only.",
            "Do not leave placeholders such as COMPANY1, [COMPANY], or <ROLE> in any edited_text.",
            "Do not invent tools, metrics, employers, dates, or scope not supported by the CV or stories.",
            "Preserve LaTeX wrappers and keep each change scoped to one inventory row.",
        ],
        suggested_output="changes.json",
    )
    _write_json(payload, args.output)
    return 0


def cmd_tailor_cover_letter(args: argparse.Namespace) -> int:
    assistant = CareerAssistant(memory_path=args.memory_path)
    cv_path = assistant.resolve_cv_path(args.cv_file)
    cv_latex = cv_path.read_text(encoding="utf-8")
    parsed_job = _read_json(args.parsed_job)
    alignment = _read_json(args.alignment) if args.alignment else {}
    job_meta = _read_json(args.job_meta) if args.job_meta else {}
    template = Path(args.template_file).read_text(encoding="utf-8") if args.template_file else ""
    user_story = args.user_story or assistant.memory.get_value("profile.headline", "")
    prompt = CVTailoringPipeline().build_cover_letter_prompt(
        parsed_job=parsed_job,
        cv_latex=cv_latex,
        alignment=alignment,
        job=job_meta,
        user_story=user_story,
        template=template,
    )
    payload = _prompt_payload(
        stage="cover-letter",
        prompt=prompt,
        expected_output="One JSON object with body_latex and closing only.",
        quality_checks=[
            "Return valid JSON only.",
            "Never leave placeholders such as COMPANY1, [COMPANY], <ROLE>, or copied template tokens.",
            "Base every claim on the CV and alignment evidence only.",
            "Keep the tone specific, adaptable, and free of generic filler.",
        ],
        suggested_output="cover_letter.json",
    )
    _write_json(payload, args.output)
    return 0


def cmd_tailor_apply(args: argparse.Namespace) -> int:
    assistant = CareerAssistant(memory_path=args.memory_path, output_dir=args.output_dir)
    try:
        tailored_path = assistant.apply_tailoring(
            context_path=args.context,
            alignment_path=args.alignment,
            changes_path=args.changes,
            output_path=args.output,
        )
    except Exception as exc:
        print(f"Apply failed: {exc}", file=sys.stderr)
        return 1
    print(f"Saved tailored CV to {tailored_path}")
    return 0


def cmd_compile(args: argparse.Namespace) -> int:
    assistant = CareerAssistant(memory_path=args.memory_path)
    try:
        result = assistant.compile_cv(args.latex_file, args.output)
    except Exception as exc:
        print(f"Compile failed: {exc}", file=sys.stderr)
        return 1

    if result["success"]:
        print(json.dumps(result, indent=2))
        return 0
    print(json.dumps(result, indent=2), file=sys.stderr)
    return 1


def cmd_email(args: argparse.Namespace) -> int:
    assistant = CareerAssistant(memory_path=args.memory_path)
    try:
        email = assistant.generate_email(
            job_title=args.job,
            company=args.company,
            location=args.location or "",
            recipient_email=args.to or "",
            recipient_name=args.recipient_name or "",
            cv_path=args.cv,
            cover_letter_path=args.cover_letter,
            output_path=args.output,
            open_mailto=args.open_mailto,
        )
    except Exception as exc:
        print(f"Email generation failed: {exc}", file=sys.stderr)
        return 1

    if not args.output:
        print(
            json.dumps(
                {
                    "subject": email.subject,
                    "body": email.body,
                    "to": email.to,
                    "mailto_url": email.mailto_url,
                    "attachments": email.attachments,
                    "warnings": email.warnings,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    from job_assist_skill.assistant.ui.app import create_app

    feedback_store = FeedbackStore() if args.learn else None
    app = create_app(
        output_dir=args.output_dir,
        cv_latex_template=args.cv_file,
        feedback_store=feedback_store,
    )
    app.run(host="0.0.0.0", port=args.port, debug=not args.production)
    return 0


def cmd_memory_show(args: argparse.Namespace) -> int:
    assistant = CareerAssistant(memory_path=args.memory_path)
    print(json.dumps(assistant.memory.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_memory_set(args: argparse.Namespace) -> int:
    assistant = CareerAssistant(memory_path=args.memory_path)
    value: Any = args.value
    if args.as_json:
        value = json.loads(args.value)
    assistant.memory.set_value(args.key, value)
    print(f"Updated {args.key}")
    return 0


def cmd_memory_update(args: argparse.Namespace) -> int:
    assistant = CareerAssistant(memory_path=args.memory_path)
    payload = _read_json(args.file) if args.file else json.loads(args.json)
    assistant.memory.update(payload)
    print(f"Updated memory at {assistant.memory.path}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    assistant = CareerAssistant(memory_path=args.memory_path, output_dir=args.output_dir)
    report = assistant.get_setup_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


async def cmd_batch(args: argparse.Namespace) -> int:
    assistant = CareerAssistant(memory_path=args.memory_path, output_dir=args.output_dir)
    roles = []
    locations = _csv_to_list(args.locations or args.location)

    if args.preset:
        if args.preset not in kw.QUICK_SEARCHES:
            print(f"Unknown preset: {args.preset}", file=sys.stderr)
            return 1
        preset = kw.QUICK_SEARCHES[args.preset]
        roles.extend(preset.get("roles", []))
        if not locations:
            locations = preset.get("locations", [])

    if args.query:
        roles.append(args.query)
    roles.extend(_csv_to_list(args.roles))

    results = await assistant.search(
        roles=roles,
        locations=locations,
        companies=_csv_to_list(args.companies),
        stream=args.stream,
        limit=args.limit,
        min_posts=args.min_posts,
        timeout=args.timeout,
        max_hours_age=args.hours,
        session_path=args.session,
        headless=args.headless,
        expand_job_details=not args.no_job_details,
        email_only_posts=args.email_only_posts,
    )

    summary = []
    for candidate in results[: args.max_candidates]:
        if not candidate.text.strip():
            continue
        tailoring = assistant.prepare_tailoring(
            job_text=candidate.text,
            cv_path=args.cv_file,
            output_dir=args.output_dir,
        )
        email_path = Path(args.output_dir) / f"email_{tailoring.context.tailoring_session_id}.json"
        assistant.generate_email(
            job_title=candidate.title or "Target Role",
            company=candidate.company or "",
            location=candidate.location or "",
            recipient_email=(candidate.contact_emails[0] if candidate.contact_emails else ""),
            output_path=str(email_path),
        )
        summary.append(
            {
                "candidate": candidate.to_dict(),
                "tailoring_context": tailoring.context_path,
                "cv_source": tailoring.latex_path,
                "email_draft": str(email_path),
                "recommended_commands": [
                    f"python main.py tailor alignment --parsed-job <parsed_job.json> --cv-file {tailoring.latex_path}",
                    f"python main.py tailor replace --alignment <alignment.json> --cv-file {tailoring.latex_path}",
                    f"python main.py tailor cover-letter --parsed-job <parsed_job.json> --cv-file {tailoring.latex_path} --alignment <alignment.json>",
                    f"python main.py tailor apply --context {tailoring.context_path} --alignment <alignment.json> --changes <changes.json>",
                ],
            }
        )

    _write_json(summary, args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Agent-controlled job search skill",
        epilog="Example: python main.py search \"operations manager\" --stream both --location \"Riyadh\"",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--memory", dest="memory_path", help="Path to memory JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        help="Run LinkedIn search using jobs, posts, or both",
        epilog="Example: python main.py search \"operations manager\" --stream both --output output/search.json",
    )
    search.add_argument("query", nargs="?", help="Freeform search query, e.g. 'financial analyst'")
    search.add_argument("--roles", help="Comma-separated role names or keyword categories")
    search.add_argument("--preset", help="Preset from keywords.py")
    search.add_argument("--location", help="Comma-separated locations")
    search.add_argument("--locations", help="Comma-separated locations")
    search.add_argument("--companies", help="Comma-separated companies")
    search.add_argument("--stream", choices=["jobs", "posts", "both"], default="both")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--min-posts", type=int, default=3)
    search.add_argument("--timeout", type=int, default=60)
    search.add_argument("--hours", type=int, default=24)
    search.add_argument("--session", help="Path to LinkedIn session JSON")
    search.add_argument("--memory-path", "--memory", dest="memory_path", help="Path to memory JSON")
    search.add_argument("--output-dir", default="output", help="Directory for generated artifacts")
    search.add_argument("--output", help="Optional JSON output path")
    search.add_argument("--headless", action="store_true", help="Run browser headless")
    search.add_argument("--no-job-details", action="store_true", help="Do not open each job result page")
    search.add_argument("--email-only-posts", action="store_true", help="For the posts stream, keep only posts that expose a contact email")
    search.add_argument("--list-presets", action="store_true", help="List available presets")

    login = subparsers.add_parser("login", help="Open browser for manual LinkedIn login")
    login.add_argument("--session", help="Where to save the LinkedIn session JSON")
    login.add_argument("--auto", action="store_true", help="Use LinkedIn credentials from .env/environment")
    login.add_argument("--force", action="store_true", help="Ignore any saved session and perform a fresh login")
    login.add_argument("--timeout", type=int, default=300, help="Manual login timeout in seconds")
    login.add_argument("--memory-path", "--memory", dest="memory_path", help="Path to memory JSON")

    tailor = subparsers.add_parser(
        "tailor",
        help="Build or apply staged tailoring prompts",
        epilog="Example: python main.py tailor prepare --job-file job.txt --cv-file cv_template.tex --output-dir output",
    )
    tailor_subparsers = tailor.add_subparsers(dest="tailor_command", required=True)

    tailor_prepare = tailor_subparsers.add_parser("prepare", help="Save initial tailoring bundle")
    tailor_prepare.add_argument("--job-text", help="Raw job posting text")
    tailor_prepare.add_argument("--job-file", help="Path to job posting text file")
    tailor_prepare.add_argument("--cv-file", help="Path to CV LaTeX")
    tailor_prepare.add_argument("--memory-path", "--memory", dest="memory_path", help="Path to memory JSON")
    tailor_prepare.add_argument("--output-dir", default="output")
    tailor_prepare.add_argument("--context-out", help="Optional alternate context output path")

    tailor_alignment = tailor_subparsers.add_parser("alignment", help="Build alignment prompt payload")
    tailor_alignment.add_argument("--parsed-job", required=True, help="PARSE_JOB JSON file")
    tailor_alignment.add_argument("--cv-file", help="Path to CV LaTeX")
    tailor_alignment.add_argument("--memory-path", "--memory", dest="memory_path", help="Path to memory JSON")
    tailor_alignment.add_argument("--output", help="Output JSON file for the prompt payload")

    tailor_replace = tailor_subparsers.add_parser("replace", help="Build rewrite prompt payload")
    tailor_replace.add_argument("--alignment", required=True, help="Alignment JSON file")
    tailor_replace.add_argument("--cv-file", help="Path to CV LaTeX")
    tailor_replace.add_argument("--stories", help="Optional JSON file of grounded stories")
    tailor_replace.add_argument("--options", help="Optional JSON file of rewrite options")
    tailor_replace.add_argument("--memory-path", "--memory", dest="memory_path", help="Path to memory JSON")
    tailor_replace.add_argument("--output", help="Output JSON file for the prompt payload")

    tailor_cover = tailor_subparsers.add_parser("cover-letter", help="Build cover letter prompt payload")
    tailor_cover.add_argument("--parsed-job", required=True, help="PARSE_JOB JSON file")
    tailor_cover.add_argument("--cv-file", help="Path to CV LaTeX")
    tailor_cover.add_argument("--alignment", help="Optional alignment JSON file")
    tailor_cover.add_argument("--job-meta", help="Optional job metadata JSON file")
    tailor_cover.add_argument("--template-file", help="Optional LaTeX cover letter template")
    tailor_cover.add_argument("--user-story", help="Optional user-provided story/objective")
    tailor_cover.add_argument("--memory-path", "--memory", dest="memory_path", help="Path to memory JSON")
    tailor_cover.add_argument("--output", help="Output JSON file for the prompt payload")

    tailor_apply = tailor_subparsers.add_parser("apply", help="Apply agent-authored rewrite JSON")
    tailor_apply.add_argument("--context", required=True, help="Prepared tailoring context JSON")
    tailor_apply.add_argument("--alignment", required=True, help="Alignment JSON from the agent")
    tailor_apply.add_argument("--changes", required=True, help="Rewrite JSON from the agent")
    tailor_apply.add_argument("--output", help="Optional tailored LaTeX output path")
    tailor_apply.add_argument("--memory-path", "--memory", dest="memory_path", help="Path to memory JSON")
    tailor_apply.add_argument("--output-dir", default="output")

    compile_parser = subparsers.add_parser("compile", help="Compile LaTeX to PDF")
    compile_parser.add_argument("--latex-file", required=True)
    compile_parser.add_argument("--output", help="Output PDF path")
    compile_parser.add_argument("--memory-path", "--memory", dest="memory_path", help="Path to memory JSON")

    email = subparsers.add_parser("email", help="Generate a local email draft JSON")
    email.add_argument("--job", required=True, help="Job title")
    email.add_argument("--company", required=True, help="Company name")
    email.add_argument("--location", help="Job location")
    email.add_argument("--to", help="Recipient email")
    email.add_argument("--recipient-name", help="Recipient display name")
    email.add_argument("--cv", help="Attached CV path")
    email.add_argument("--cover-letter", help="Attached cover letter path")
    email.add_argument("--output", help="Optional output JSON path")
    email.add_argument("--open-mailto", action="store_true", help="Open the default mail client using a mailto: URL after building the draft")
    email.add_argument("--memory-path", "--memory", dest="memory_path", help="Path to memory JSON")

    doctor = subparsers.add_parser("doctor", help="Show missing blocking inputs and setup readiness for the agent")
    doctor.add_argument("--memory-path", "--memory", dest="memory_path", help="Path to memory JSON")
    doctor.add_argument("--output-dir", default="output", help="Directory for generated artifacts")

    ui = subparsers.add_parser("ui", help="Launch the local review UI")
    ui.add_argument("--port", type=int, default=5050)
    ui.add_argument("--output-dir", default="output")
    ui.add_argument("--cv-file", help="Path to CV LaTeX template")
    ui.add_argument("--production", action="store_true")
    ui.add_argument("--no-learn", dest="learn", action="store_false")

    memory = subparsers.add_parser("memory", help="Inspect or update user preference memory")
    memory.add_argument("--memory-path", "--memory", dest="memory_path", help="Path to memory JSON")
    memory_subparsers = memory.add_subparsers(dest="memory_command", required=True)

    memory_show = memory_subparsers.add_parser("show", help="Show current memory")
    memory_show.add_argument("--memory-path", "--memory", dest="memory_path", help="Path to memory JSON")

    memory_set = memory_subparsers.add_parser("set", help="Set a nested memory value")
    memory_set.add_argument("key", help="Dotted key, e.g. profile.name")
    memory_set.add_argument("value", help="Value to store")
    memory_set.add_argument("--as-json", action="store_true", help="Parse the value as JSON")
    memory_set.add_argument("--memory-path", "--memory", dest="memory_path", help="Path to memory JSON")

    memory_update = memory_subparsers.add_parser("update", help="Deep-merge a JSON payload into memory")
    memory_update.add_argument("--file", help="JSON file to merge")
    memory_update.add_argument("--json", help="Inline JSON to merge")
    memory_update.add_argument("--memory-path", "--memory", dest="memory_path", help="Path to memory JSON")

    batch = subparsers.add_parser(
        "batch",
        help="Search and prepare prompt bundles for multiple results",
        epilog="Example: python main.py batch \"operations manager\" --stream both --max-candidates 5",
    )
    batch.add_argument("query", nargs="?", help="Freeform search query")
    batch.add_argument("--roles", help="Comma-separated role names or keyword categories")
    batch.add_argument("--preset", help="Preset from keywords.py")
    batch.add_argument("--location", help="Comma-separated locations")
    batch.add_argument("--locations", help="Comma-separated locations")
    batch.add_argument("--companies", help="Comma-separated companies")
    batch.add_argument("--stream", choices=["jobs", "posts", "both"], default="both")
    batch.add_argument("--limit", type=int, default=10)
    batch.add_argument("--min-posts", type=int, default=3)
    batch.add_argument("--timeout", type=int, default=60)
    batch.add_argument("--hours", type=int, default=24)
    batch.add_argument("--max-candidates", type=int, default=5)
    batch.add_argument("--session", help="Path to LinkedIn session JSON")
    batch.add_argument("--memory-path", "--memory", dest="memory_path", help="Path to memory JSON")
    batch.add_argument("--output-dir", default="output")
    batch.add_argument("--output", default="output/batch_summary.json")
    batch.add_argument("--headless", action="store_true")
    batch.add_argument("--no-job-details", action="store_true")
    batch.add_argument("--email-only-posts", action="store_true", help="For the posts stream, keep only posts that expose a contact email")
    batch.add_argument("--cv-file", help="Path to CV LaTeX")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "debug", False):
        logging.basicConfig(level=logging.DEBUG)

    if args.command == "search":
        return asyncio.run(cmd_search(args))
    if args.command == "login":
        return asyncio.run(cmd_login(args))
    if args.command == "compile":
        return cmd_compile(args)
    if args.command == "email":
        return cmd_email(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "ui":
        return cmd_ui(args)
    if args.command == "batch":
        return asyncio.run(cmd_batch(args))
    if args.command == "memory":
        if args.memory_command == "show":
            return cmd_memory_show(args)
        if args.memory_command == "set":
            return cmd_memory_set(args)
        if args.memory_command == "update":
            if not args.file and not args.json:
                print("Provide --file or --json", file=sys.stderr)
                return 1
            return cmd_memory_update(args)
    if args.command == "tailor":
        if args.tailor_command == "prepare":
            return cmd_tailor_prepare(args)
        if args.tailor_command == "alignment":
            return cmd_tailor_alignment(args)
        if args.tailor_command == "replace":
            return cmd_tailor_replace(args)
        if args.tailor_command == "cover-letter":
            return cmd_tailor_cover_letter(args)
        if args.tailor_command == "apply":
            return cmd_tailor_apply(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
