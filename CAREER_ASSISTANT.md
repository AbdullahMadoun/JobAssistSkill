# Career Assistant

Automated job search, CV tailoring, cover letter generation, and email campaign management for job applications.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Login to LinkedIn (one-time setup)
python main.py login --session linkedin_session.json

# Run everything in one go: search → tailor → PDF → email
python run_all.py --preset gulf_tech

# Or use custom roles
python run_all.py --roles "software_engineer,data_ml" --location "Remote" --limit 10

# Run full demo (uses your CV template)
python main.py demo
```

## Commands

### `search` - Find Hiring Posts

```bash
# Simple keyword search
python main.py search "software engineer" --location "Remote" --hours 24

# Use preset (see --list-presets for all)
python main.py search --preset remote_software
python main.py search --preset us_tech
python main.py search --preset gulf_tech

# Custom role categories from keywords.py
python main.py search --roles "software_engineer,data_ml" --location "usa,remote"

# List available presets
python main.py search --list-presets
```

Available presets:
- `remote_software` - Remote software/senior engineers
- `us_tech` - US tech hubs (SF, Seattle, Boston)
- `gulf_tech` - Saudi Arabia, UAE, GCC
- `europe_tech` - Europe + UK tech hubs
- `asia_tech` - Singapore, HK, Tokyo, Seoul
- `entry_level` - Junior/graduate positions
- `data_science` - ML/AI/data roles
- `devops` - DevOps/SRE/Cloud roles

### `tailor` - Prepare CV Tailoring

```bash
python main.py tailor \
    --job-file job_posting.txt \
    --cv-file cv_template.tex \
    --output output/ \
    --save-context
```

### `compile` - Compile LaTeX to PDF

```bash
python main.py compile --latex-file output/cv_tailored.tex --output output/cv_tailored.pdf
```

### `email` - Generate Application Email

```bash
python main.py email \
    --job "Software Engineer" \
    --company "Microsoft" \
    --to "careers@microsoft.com" \
    --cv output/cv.pdf
```

### `ui` - Start Web UI

```bash
python main.py ui --port 5050
```

### `login` - LinkedIn Login

```bash
python main.py login --session linkedin_session.json
```

### `demo` - Full Workflow Demo

```bash
python main.py demo --session linkedin_session.json
```

## run_all.py - Complete Workflow

The `run_all.py` script runs the entire pipeline in one command:

```bash
# Run everything: search → tailor CV → compile PDF → generate email
python run_all.py --preset gulf_tech

# Custom roles and locations
python run_all.py --roles "software_engineer,data_ml" --location "Remote,USA"

# More candidates
python run_all.py --preset us_tech --max-candidates 10
```

**What it does:**
1. Searches LinkedIn for hiring posts matching your preset/keywords
2. For each post: prepares CV tailoring context
3. Applies LLM suggestions (or simulates if no LLM)
4. Compiles tailored CV to one-page PDF
5. Generates personalized application email
6. Saves everything to `output/` folder

**Output files:**
- `cv_{session_id}_tailored.tex` - Tailored CV LaTeX
- `cv_{session_id}_tailored.pdf` - Compiled CV PDF
- `email_{session_id}.json` - Generated email (subject, body, to, cc)
- `run_all_{timestamp}.json` - Full results summary

**Presets available:**
| Preset | Roles | Locations |
|--------|-------|-----------|
| `remote_software` | software/senior | Remote |
| `us_tech` | software/data/cloud | SF, Seattle, Boston |
| `gulf_tech` | software/senior | Saudi Arabia, UAE, GCC |
| `europe_tech` | software/data | Europe, UK |
| `asia_tech` | software/data/mobile | Asia, Singapore |
| `entry_level` | junior/grad | USA, UK, Remote |
| `data_science` | ML/AI/data | US tech, Remote |
| `devops` | DevOps/SRE | Remote, USA |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     main.py (CLI)                          │
│   search | tailor | compile | email | ui | login | demo     │
└─────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ linkedin_scraper│  │ career_assistant│  │    prompts.js   │
│                 │  │                 │  │                 │
│ • JobSearch     │  │ • Tailoring     │  │ • PARSE_JOB     │
│ • PostSearch    │  │ • LaTeX Compile │  │ • ANALYZE       │
│ • HiringSearch  │  │ • Email Gen     │  │ • REPLACE       │
│ • CompanyPosts  │  │ • Feedback Store│  │ • COVER_LETTER  │
└─────────────────┘  └─────────────────┘  └─────────────────┘
                              │
                              ▼ (opencode handles LLM calls)
                     ┌─────────────────┐
                     │   opencode LLM  │
                     │                 │
                     │ • GPT-4         │
                     │ • Claude        │
                     │ • etc.          │
                     └─────────────────┘
```

## Project Structure

```
Linkedin-Scraper/
├── main.py                  # CLI entry point
├── cv_template.tex          # Your LaTeX CV template
├── prompts.js                # CV tailoring prompts
├── linkedin_session.json    # LinkedIn auth session
├── output/                   # Generated CVs, PDFs, emails
│
├── linkedin_scraper/        # LinkedIn scraping
│   ├── __init__.py
│   ├── core/
│   │   └── browser.py      # BrowserManager with stealth
│   ├── scrapers/
│   │   ├── post_search.py  # PostSearchScraper, HiringPostSearcher
│   │   └── job_search.py    # JobSearchScraper
│   └── models/
│       └── post.py         # Post model
│
└── career_assistant/        # CV tailoring & workflow
    ├── __init__.py          # CareerAssistant class
    ├── pipeline/
    │   ├── tailoring.py     # CV tailoring preparation
    │   ├── latex_compiler.py # LaTeX → PDF
    │   ├── email_generator.py
    │   └── aggregator.py    # Multi-source job aggregation
    ├── prompts/
    │   └── loader.py        # Load prompts.js
    ├── storage/
    │   └── feedback.py      # SQLite learning system
    └── ui/
        └── app.py           # Flask web UI
```

## CV Tailoring Flow

1. **Prepare**: `CVTailoringPipeline.prepare()` generates prompts from job text + CV
2. **LLM Parse**: Send `job_requirements.parse_prompt` to LLM → get JSON requirements
3. **LLM Analyze**: Send `alignment_prompt` to LLM → get alignment analysis
4. **LLM Rewrite**: Send `replace_prompt` to LLM → get suggested edits
5. **Apply**: `apply_llm_results()` applies edits to LaTeX
6. **Compile**: `LaTeXCompiler.compile_one_page()` → PDF

## Files

| File | Description |
|------|-------------|
| `main.py` | CLI entry point |
| `cv_template.tex` | Your LaTeX CV template |
| `prompts.js` | LLM prompts for CV tailoring |
| `linkedin_session.json` | LinkedIn authentication session |
| `output/` | Generated files (CVs, PDFs, emails) |
| `VIBE_CODING.md` | Guide for AI Agent interactions |
| `career_assistant/storage/feedback.db` | SQLite database for learning |

## Requirements

- Python 3.8+
- LinkedIn authenticated session
- LaTeX distribution (pdflatex) for PDF compilation
- Chrome/Firefox browser for Playwright
