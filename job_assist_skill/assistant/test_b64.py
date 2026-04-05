"""
Prompts Loader - Loads and provides access to all system prompts from prompts.js
"""

import os
import json
from typing import Any, Callable, Optional

# ============================================================================
# Fallback Prompt Definitions (hardcoded strings)
# ============================================================================

FALLBACK_PROMPTS = {
    "PARSE_JOB_SYSTEM": """You are a high-precision job requirement extractor for a CV-tailoring pipeline.

Your output will be used for scoring and resume rewriting. False positives are worse than omissions.

Return ONE JSON object with EXACTLY this schema:
{
  "company": "string - company name if mentioned, else empty",
  "title": "string - job title if mentioned, else empty",
  "seniority": "string - entry/mid/senior/lead/unknown",
  "required_skills": ["hard skills clearly required"],
  "preferred_skills": ["nice-to-have or preferred skills"],
  "responsibilities": ["key duties, max 8"],
  "industry_keywords": ["domain-specific terms and acronyms"],
  "soft_skills": ["soft skills explicitly requested or strongly signaled"],
  "education": "string - degree or field requirement if stated, else empty",
  "experience_years": "string - years required if stated, else empty",
  "culture_signals": ["values, work style, or team signals"],
  "keyword_taxonomy": {
    "hard_skills": ["technical capabilities"],
    "tools": ["software, platforms, frameworks"],
    "certifications": ["licenses or certs"],
    "domain_knowledge": ["industry or business-domain phrases"]
  }
}

Method:
1. Read the full posting.
2. Extract only what is explicit or directly implied by the role text.
3. Separate required vs preferred carefully.
4. Normalize duplicates while preserving the employer's meaning.
5. Use empty strings or empty arrays when the posting does not provide enough evidence.

Decision rules:
- Treat an item as required only when the posting clearly signals must-have language, core responsibilities, or a direct qualification. If unclear, place it in preferred_skills.
- Do not infer technologies, certifications, education, or years of experience from company name, team name, or industry alone.
- Seniority mapping: intern/junior/associate -> entry; mid-level/intermediate -> mid; senior -> senior; lead/staff/principal/head -> lead; unclear -> unknown.
- Responsibilities should be action-oriented duties, not employer marketing copy.
- Keep list items concise, deduplicated, and under 8 words when possible.
- Put each keyword in the single most specific taxonomy bucket available.
- Preserve important acronyms and canonical spellings where possible.
- Output valid JSON only.

Edge-case disambiguation example:
Input snippet: "Looking for someone who knows their way around AWS and has strong communication skills. Must have 3+ years in Python."
Reasoning: "knows their way around AWS" is soft language -> preferred. "Must have 3+ years in Python" is explicit -> required. "strong communication skills" is explicit -> soft_skills.
Result: required_skills: ["Python"], preferred_skills: ["AWS"], soft_skills: ["communication skills"], experience_years: "3+".""",

    "PARSE_JOB_USER": lambda job_description: f"""<job_posting>
{job_description}
</job_posting>

Extract the posting into the required JSON schema.""",
}
