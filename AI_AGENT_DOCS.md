# Vibecoding with JobAssistSkill 🚀

This repository is designed to be highly interoperable with AI coding assistants and autonomous agents ("vibecoding"). 
It provides structured entry points for searching, tailoring, and career automation.

## For AI Agents: How to use this Repo

### 1. The Multi-Model Pipeline
The core logic resides in `career_assistant/pipeline/`. 
- **`CVTailoringPipeline`**: Prepares a JSON context that contains job requirements and CV LaTeX. 
- **Agent Action**: You should take the `alignment_prompt` from the prepared context, send it to your LLM, and then call `apply_llm_results()` with the JSON output from the LLM.

### 2. CLI Entry Point (`main.py`)
`main.py` is the primary interface for automated tasks.
- **Search**: `python main.py search "roles" --location "loc"`
- **Tailor**: `python main.py tailor --job-text "..." --cv-file "cv_template.tex"`
- **UI**: `python main.py ui` (for interactive review)

### 3. Key Components
- **`linkedin_scraper`**: A Playwright-based scraper. It expects a `linkedin_session.json` which can be generated via `python main.py login`.
- **`keywords.py`**: A centralized dictionary of search terms. Agents can expand this to target new industries.
- **`output/`**: All generated artifacts (Tailored CVs, Emails, Search Results) are stored here. Agents should monitor this directory.

### 4. Extending the Logic
To add new tailoring strategies or scoring methods:
- Modify `career_assistant/ranker.py` for scoring.
- Update `career_assistant/pipeline/email_generator.py` for personalized messaging.

## Agent Workflow (Recommended)
1. **Login**: Ask the user to run `python main.py login` once.
2. **Search**: Run `python main.py search` to find target roles.
3. **Analyze**: Read the results from `output/search_results.json`.
4. **Tailor**: For each interesting role, run `python main.py tailor`.
5. **Collaborate**: Show the generated draft to the user for final approval before sending.

---
*Built for the future of AI-assisted career development.*
