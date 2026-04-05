# JobAssistSkill 🚀

**AI-Powered Career Automation Suite**

JobAssistSkill is a comprehensive toolkit for automating the modern job search. It combines high-fidelity LinkedIn scraping with LLM-powered CV tailoring and email generation to help you apply for roles with "Elite" precision at scale.

## Core Features

- **Dual-Stream Search**: Finds both formal job postings and informal "hiring posts" from LinkedIn content.
- **Elite CV Tailoring**: Uses the "STAR Ladder" framework to rewrite CV bullets for maximum alignment with job requirements.
- **Cold Email Automation**: Generates personalized application emails addressed directly to recruiters.
- **AI-Agent Optimized**: Designed to be executed by AI agents (Codex, Claude, GPT) with minimal human intervention.
- **Quality Guard**: Automated self-audit system to ensure professional identity and domain clarity.

## Quick Start

### 1. Installation
```bash
git clone https://github.com/AbdullahMadoun/JobAssistSkill.git
cd JobAssistSkill
pip install -e .
playwright install chromium
```

### 2. Login
```bash
python main.py login
```

### 3. Run Automated Workflow
```bash
# Search for local tech roles and prepare applications
python run_all.py --preset gulf_tech --limit 10
```

## Tools & Commands

| Command | Purpose |
|---------|---------|
| `search` | Find jobs/hiring posts using presets or keywords |
| `tailor` | Prepare CV tailoring context for LLM |
| `compile` | Convert tailored LaTeX CV to one-page PDF |
| `email` | Generate personalized application email |
| `ui` | Launch web dashboard for job review |

## For AI Builders 🤖
See [SKILL.md](SKILL.md) for detailed instructions on how to integrate JobAssistSkill into your AI agent's toolbelt.

---
*Created by Abdullah Madoun*
