# AI Agent Notes

`SKILL.md` is the source of truth for how an agent should use this repo.

Key rules:

- the agent is the only reasoning layer
- no external LLM API calls are part of the supported workflow
- no Outlook MCP is part of the supported workflow; the archived legacy code lives in `archive/outlook-mcp-legacy/`
- the first step is `python main.py doctor`
- if `doctor` reports missing inputs, ask the user the blocking questions before continuing
- reuse a saved LinkedIn session before starting a fresh login
- use `python main.py search --stream jobs|posts|both` for scraping
- use `--email-only-posts` when the user wants recruiter posts that expose a contact email
- use `python main.py tailor ...` for staged prompt preparation and local CV rewrite application
- use `python main.py email ...` only for local drafts; the output includes a `mailto_url` for the user’s email client
- use `.job_assist/preferences.json` as persistent user memory
- watch for placeholder-removal warnings in email drafts and surface them to the user instead of sending blindly

For end-to-end operator setup, see `CAREER_ASSISTANT.md`.
