# Career Assistant Setup Report

This document explains how to operate the repo from scratch as a local skill for a coding agent.

## Current Model

The repo is now agent-first:

- the agent is the reasoning layer
- the repo performs deterministic local work only
- no external LLM API is required
- no Outlook MCP is part of the active workflow

Active capabilities:

- LinkedIn search through `jobs`, `posts`, or `both`
- staged prompt packaging for CV tailoring
- deterministic application of agent-authored JSON edits
- local PDF compilation
- local email drafting with `mailto:` handoff
- persistent memory in `.job_assist/preferences.json`

Legacy Outlook code is archived in `archive/outlook-mcp-legacy/`.

## What Was Fixed

The major repair areas were:

1. Packaging and imports
   The repo now imports cleanly and installs as a usable Python package.

2. Agent-facing workflow
   The CLI was rewritten around explicit search, tailoring, compile, email, memory, and setup stages.

3. Persistent memory
   `.job_assist/preferences.json` now stores profile, file paths, search defaults, and sender settings.

4. Prompt staging
   The tailoring flow now starts with `PARSE_JOB`, then alignment, then replace, then apply.

5. Search result quality
   Normalized candidates now carry `match_score`, `quality_flags`, `snippet`, `next_action`, and `detail_level`.

6. Email safety
   Email drafts now include `mailto_url` and warnings for placeholder-like values such as `COMPANY1`.

7. Login reuse
   The login path now reuses a still-valid saved LinkedIn session instead of forcing a fresh login every time.

8. Job scraping quality
   The jobs stream still uses the Playwright/session backbone, but the page parser now uses rendered HTML plus JSON-LD so title, company, location, posted date, applicant count, and description are separated correctly.

9. Blocking-input detection
   `python main.py doctor` now reports missing essentials and gives the exact questions the agent should ask before continuing.

10. Tests
   The active workflow is now covered by a deterministic test suite.

## Verified State

Current deterministic verification:

- `python -m pytest -q` passes with 28 tests
- `python -m compileall .` passes

Current live validation in this workspace:

- `python main.py doctor` reports the current local setup status and any blocking questions
- `python main.py login` reuses a valid saved LinkedIn session instead of forcing a fresh login
- `python main.py search --stream jobs --limit 1 --timeout 20 --headless` returned an expanded job record with title, company, location, posted date, applicant count, and description
- `python main.py search --stream posts ...` still remains the main live limitation; it fails safely but can return empty or time out under current LinkedIn conditions

That means:

- the repo is usable now for agent-driven job search and tailoring
- the `jobs` stream is the reliable backbone today
- the `posts` and `email-only-posts` modes are implemented and safe, but still need further recall tuning if they are meant to be primary

## Fresh Install

Clone and install:

```bash
git clone <your-repo-url>
cd Linkedin-Scraper
pip install -e .
playwright install chromium
```

Optional:

```bash
pip install -r requirements-dev.txt
```

## First-Time Agent Flow

1. Run the setup check:

```bash
python main.py doctor
```

2. If `blocking_inputs` is non-empty, ask those exact questions before continuing.

3. Save the answers into memory:

```bash
python main.py memory set profile.name "Your Name"
python main.py memory set profile.email "you@example.com"
python main.py memory set files.cv_path "cv_template.tex"
```

4. Re-run:

```bash
python main.py doctor
```

5. Only if the saved session is missing or invalid, run:

```bash
python main.py login
```

or:

```bash
python main.py login --auto
```

## Search From Scratch

Jobs only:

```bash
python main.py search "operations manager" --stream jobs --location "Riyadh" --output output/jobs.json
```

Posts only:

```bash
python main.py search "operations manager" --stream posts --location "Riyadh" --output output/posts.json
```

Both:

```bash
python main.py search "operations manager" --stream both --location "Riyadh" --output output/both.json
```

Posts with contact emails only:

```bash
python main.py search "operations manager" --stream posts --email-only-posts --output output/posts_email.json
```

If query defaults are already saved in memory, the agent can also run:

```bash
python main.py search --stream jobs --output output/jobs.json
```

## Tailoring Workflow

Prepare:

```bash
python main.py tailor prepare --job-file job.txt --cv-file cv_template.tex --output-dir output
```

Alignment prompt package:

```bash
python main.py tailor alignment --parsed-job output/parsed_job.json --cv-file cv_template.tex --output output/alignment_prompt.json
```

Rewrite prompt package:

```bash
python main.py tailor replace --alignment output/alignment.json --cv-file cv_template.tex --output output/replace_prompt.json
```

Cover-letter prompt package:

```bash
python main.py tailor cover-letter --parsed-job output/parsed_job.json --cv-file cv_template.tex --alignment output/alignment.json --output output/cover_letter_prompt.json
```

Apply:

```bash
python main.py tailor apply --context output/context_<id>.json --alignment output/alignment.json --changes output/changes.json --output output/tailored.tex
```

Compile:

```bash
python main.py compile --latex-file output/tailored.tex --output output/tailored.pdf
```

The stage payloads now carry explicit output contracts and quality checks so the agent can self-prompt more reliably.

## Email Workflow

Create a draft:

```bash
python main.py email --job "Operations Manager" --company "Example Co" --to "jobs@example.com" --output output/email.json
```

Open the user’s local mail client via `mailto:`:

```bash
python main.py email --job "Operations Manager" --company "Example Co" --to "jobs@example.com" --open-mailto
```

Important behavior:

- drafts include `mailto_url`
- drafts include `warnings`
- placeholder-like values such as `COMPANY1` are removed instead of passed through

## Recommended Validation

```bash
python main.py doctor
python -m pytest -q
python -m compileall .
```

## Commit Readiness Note

The repo is now coherent enough to start committing.

The only remaining high-signal live limitation is post-stream recall under current LinkedIn conditions. That should be documented honestly, but it does not block commits for the repaired agent-first skill baseline because:

- jobs search is live-validated
- deterministic tests pass
- mailto, memory, setup checks, and prompt staging are all in place
