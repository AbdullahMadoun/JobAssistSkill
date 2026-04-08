# JobAssistSkill

JobAssistSkill is a local, agent-operated skill for:

- LinkedIn scraping through `jobs`, `posts`, or `both`
- staged CV tailoring prompt preparation with the bundled advanced prompts
- deterministic application of agent-authored CV edits
- local PDF compilation
- local email draft generation with `mailto:` handoff
- persistent user memory in `.job_assist/preferences.json`

The agent is the reasoning layer. This repo only performs deterministic local work.

The old Outlook MCP subtree is not part of the supported workflow. Legacy code is archived in `archive/outlook-mcp-legacy/`.

## Quick Start

```bash
git clone https://github.com/AbdullahMadoun/JobAssistSkil
pip install -e .
playwright install chromium
```

Optional dev dependencies:

```bash
pip install -r requirements-dev.txt
```

## First Step: Doctor

Before searching or tailoring, ask the repo what is missing:

```bash
python main.py doctor
```

This prints:

- whether the saved LinkedIn session exists
- whether the CV template exists
- whether email drafting is ready
- `blocking_inputs` with the exact questions the agent should ask the user

If `blocking_inputs` is not empty, the agent should stop and ask those questions before continuing.

## Memory Setup

Store the user’s stable defaults:

```bash
python main.py memory set profile.name "Your Name"
python main.py memory set profile.email "you@example.com"
python main.py memory set files.cv_path "cv_template.tex"
python main.py memory set search.roles '["operations manager"]' --as-json
python main.py memory set search.locations '["Riyadh"]' --as-json
```

Inspect memory:

```bash
python main.py memory show
```

## LinkedIn Session

The scraper reuses the saved LinkedIn session. Do not log in from scratch every time.

If the remembered session is still valid:

```bash
python main.py login
```

will reuse it and exit without forcing a fresh login.

If `.env` already contains LinkedIn credentials:

```bash
python main.py login --auto
```

Supported environment names:

- `LINKEDIN_EMAIL`
- `LINKEDIN_USERNAME`
- `LINKEDIN_PASSWORD`
- legacy `LinkedinUser`
- legacy `LinkedinPassword`

## Search

Freeform search:

```bash
python main.py search "operations manager" --stream both --location "Riyadh" --output output/search.json
```

Memory-backed search:

```bash
python main.py search --stream jobs --output output/jobs.json
```

If no query or roles are passed, `search` now falls back to saved memory defaults.

Streams:

- `jobs`: formal LinkedIn job pages
- `posts`: recruiter and hiring posts from content search
- `both`: merge both streams

The normalized output includes:

- `match_score`
- `quality_flags`
- `snippet`
- `next_action`
- `detail_level`
- `contact_emails` when available

If the user wants only posts that expose a contact email:

```bash
python main.py search "operations manager" --stream posts --email-only-posts --output output/posts_email.json
```

## Tailoring Workflow

Prepare the first-stage bundle:

```bash
python main.py tailor prepare --job-file job.txt --cv-file cv_template.tex --output-dir output
```

This writes `context_<id>.json` with:

- the job text
- the raw CV LaTeX
- the `PARSE_JOB` prompt package
- quality checks
- next-step commands

Build the alignment prompt package:

```bash
python main.py tailor alignment --parsed-job output/parsed_job.json --cv-file cv_template.tex --output output/alignment_prompt.json
```

Build the rewrite prompt package:

```bash
python main.py tailor replace --alignment output/alignment.json --cv-file cv_template.tex --output output/replace_prompt.json
```

Build the cover-letter prompt package:

```bash
python main.py tailor cover-letter --parsed-job output/parsed_job.json --cv-file cv_template.tex --alignment output/alignment.json --output output/cover_letter_prompt.json
```

These stage payloads now include:

- `expected_output`
- `quality_checks`
- `suggested_output_file`

The agent should obey those contracts and avoid placeholder leaks such as `COMPANY1`, `[COMPANY]`, or `<ROLE>`.

Apply the rewrite JSON:

```bash
python main.py tailor apply --context output/context_<id>.json --alignment output/alignment.json --changes output/changes.json --output output/tailored.tex
```

Compile:

```bash
python main.py compile --latex-file output/tailored.tex --output output/tailored.pdf
```

## Email Drafts and Mailto

Generate a local email draft:

```bash
python main.py email --job "Operations Manager" --company "Example Co" --to "jobs@example.com" --output output/email_draft.json
```

Open the default email client through `mailto:`:

```bash
python main.py email --job "Operations Manager" --company "Example Co" --to "jobs@example.com" --open-mailto
```

The saved JSON includes:

- `subject`
- `body`
- `mailto_url`
- `warnings`

If `warnings` contains placeholder-removal notices, the agent should surface that to the user instead of blindly using the draft.

## Batch Mode

Prepare several candidates in one run:

```bash
python run_all.py "operations manager" --stream both --max-candidates 5 --output output/batch_summary.json
```

Batch mode prepares local artifacts only. It does not call an external LLM and does not send email.

## Validation

```bash
python -m pytest -q
```

```bash
python - <<'PY'
import compileall
print(compileall.compile_dir('.', quiet=1, maxlevels=20))
PY
```

## Current Live Status

- `jobs` stream: live-validated with remembered session and expanded job details
- `posts` stream: still the main tuning target; it fails safely but can return empty/time out under current LinkedIn conditions
- `email-only-posts`: supported in code and safe to run, but currently limited by the same post-stream recall issues

## More Detail

- Skill contract: `SKILL.md`
- Agent notes: `AI_AGENT_DOCS.md`
- Detailed operator/setup report: `CAREER_ASSISTANT.md`
