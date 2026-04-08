---
name: job-assist-skill
description: Use this skill when the user wants LinkedIn job search, dual-stream scraping of jobs and hiring posts, staged CV tailoring prompts, local email drafts, mailto handoff, or persistent job-search preference memory. The agent is the reasoning layer; this repo only provides deterministic local tooling.
---

# Job Assist Skill

This repository is itself the skill. Use it as a local toolbelt for:

- LinkedIn search through `jobs`, `posts`, or `both`
- staged prompt preparation for CV tailoring
- deterministic application of agent-authored rewrite JSON
- local PDF compilation
- local email draft generation with `mailto:` initiation
- persistent user preference memory

Do not use Outlook MCP. Do not assume an external LLM API is available. The agent should reason with the bundled prompts and feed its own JSON outputs back into the local commands.

Ignore `archive/outlook-mcp-legacy/`. It is preserved only as legacy reference material and is not part of the supported workflow.

## First Read

1. Read `README.md` for the operator workflow.
2. Read `.job_assist/preferences.json` if it exists.
3. Run `python main.py doctor`.
4. If the user mentions updated login credentials or scraping tweaks, inspect `.env`.

## Blocking Questions Rule

`python main.py doctor` is the first gate.

If `blocking_inputs` is non-empty, stop and ask the user those exact questions before searching, tailoring, or drafting email.

Typical blocking items:

- candidate full name
- candidate email
- LaTeX CV template path
- saved LinkedIn session path

## Core Rules

- Treat `.job_assist/preferences.json` as persistent memory.
- Before searching, prefer saved roles, locations, CV path, and LinkedIn session when they exist.
- Reuse the remembered LinkedIn session before starting a fresh login.
- Prefer `--stream both` unless the user clearly wants only job listings or only hiring posts.
- Use `--email-only-posts` when the user specifically wants recruiter posts that expose contact emails.
- The search stage is deterministic scraping only.
- The tailoring stage is prompt preparation plus deterministic application of the agent's own JSON output.
- Never route sending through Outlook MCP.
- Watch email draft `warnings` and do not ignore placeholder-removal notices.

## Login Workflow

Manual login:

```bash
python main.py login
```

Automatic login from `.env` or environment variables:

```bash
python main.py login --auto
```

The login command now reuses an existing valid saved session instead of forcing a fresh login every time.

## Search Workflow

Freeform query:

```bash
python main.py search "operations manager" --stream both --location "Riyadh" --output output/search.json
```

Memory-backed query:

```bash
python main.py search --stream jobs --output output/jobs.json
```

Email-only posts:

```bash
python main.py search "operations manager" --stream posts --email-only-posts --output output/posts_email.json
```

Use `match_score`, `quality_flags`, `snippet`, `detail_level`, `contact_emails`, and `next_action` to decide what to process first.

## Tailoring Workflow

Stage 1:

```bash
python main.py tailor prepare --job-file job.txt --cv-file cv_template.tex --output-dir output
```

Stage 2:

```bash
python main.py tailor alignment --parsed-job output/parsed_job.json --cv-file cv_template.tex --output output/alignment_prompt.json
```

Stage 3:

```bash
python main.py tailor replace --alignment output/alignment.json --cv-file cv_template.tex --output output/replace_prompt.json
```

Optional cover letter:

```bash
python main.py tailor cover-letter --parsed-job output/parsed_job.json --cv-file cv_template.tex --alignment output/alignment.json --output output/cover_letter_prompt.json
```

Stage 4:

```bash
python main.py tailor apply --context output/context_<id>.json --alignment output/alignment.json --changes output/changes.json --output output/tailored.tex
```

Compile:

```bash
python main.py compile --latex-file output/tailored.tex --output output/tailored.pdf
```

The generated stage payloads include `expected_output`, `quality_checks`, and `suggested_output_file`. The agent should follow those contracts exactly and avoid placeholder leaks like `COMPANY1`, `[COMPANY]`, or `<ROLE>`.

## Email Drafts

Generate a local draft:

```bash
python main.py email --job "Operations Manager" --company "Example Co" --to "jobs@example.com" --output output/email.json
```

Open the user’s default email client via `mailto:`:

```bash
python main.py email --job "Operations Manager" --company "Example Co" --to "jobs@example.com" --open-mailto
```

## Validation

```bash
python main.py doctor
python -m pytest -q
```

```bash
python - <<'PY'
import compileall
print(compileall.compile_dir('.', quiet=1, maxlevels=20))
PY
```
