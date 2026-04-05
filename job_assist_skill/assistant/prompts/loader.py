"""
Prompt Loader for prompts.js.

Loads the prompts from prompts.js and provides Python-friendly builders
for the CV tailoring pipeline.
"""

import os
import re
from typing import Any, Dict, List, Optional
from pathlib import Path


class PromptLoader:
    """
    Loads and provides access to prompts from prompts.js.

    Usage:
        loader = PromptLoader()
        system, user = loader.build_parse_job_prompt(job_description)
    """

    def __init__(self, prompts_path: Optional[str] = None):
        """
        Initialize prompt loader.

        Args:
            prompts_path: Path to prompts.js. Defaults to repo root.
        """
        if prompts_path is None:
            repo_root = Path(__file__).parent.parent.parent
            prompts_path = repo_root / "prompts.js"

        self.prompts_path = Path(prompts_path)
        self._prompts = self._load_prompts()

    def _load_prompts(self) -> Dict[str, str]:
        """Load all prompts from prompts.js file."""
        if not self.prompts_path.exists():
            raise FileNotFoundError(f"prompts.js not found at {self.prompts_path}")

        content = self.prompts_path.read_text(encoding='utf-8')

        prompts = {}

        prompt_pattern = re.compile(
            r'const\s+(\w+)\s*=\s*(?:`([^`]*)`|\'([^\']*)\'|"([^"]*)")',
            re.MULTILINE | re.DOTALL
        )

        for match in prompt_pattern.finditer(content):
            name = match.group(1)
            value = match.group(2) or match.group(3) or match.group(4)
            prompts[name] = value

        return prompts

    def get_system(self, name: str) -> str:
        """Get system prompt by name."""
        return self._prompts.get(f"{name}_SYSTEM", "")

    def get_user(self, name: str) -> str:
        """Get user prompt builder by name."""
        return self._prompts.get(f"{name}_USER", "")

    @property
    def PARSE_JOB_SYSTEM(self) -> str:
        return self._prompts.get('PARSE_JOB_SYSTEM', '')

    @property
    def PARSE_JOB_USER(self):
        def build(job_description: str) -> str:
            return f"<job_posting>\n{job_description}\n</job_posting>\n\nExtract the posting into the required JSON schema."
        return build

    @property
    def ANALYZE_ALIGNMENT_SYSTEM(self) -> str:
        return self._prompts.get('ANALYZE_ALIGNMENT_SYSTEM', '')

    @property
    def ANALYZE_ALIGNMENT_USER(self):
        def build(parsed_req: Dict, latex: str) -> str:
            return f"<parsed_job_requirements>\n{self._json_dumps(parsed_req)}\n</parsed_job_requirements>\n\n<candidate_cv_latex>\n{latex}\n</candidate_cv_latex>\n\nAnalyze the CV against the job requirements. Review EVERY bullet point in every section. Return the required JSON."
        return build

    @property
    def REPLACE_SYSTEM(self) -> str:
        return self._prompts.get('REPLACE_SYSTEM', '')

    def build_replace_user(
        self,
        latex: str,
        alignment: Dict,
        stories: Optional[List[Dict]] = None,
        options: Optional[Dict] = None
    ) -> str:
        """
        Build the REPLACE user prompt.

        Args:
            latex: The LaTeX CV content
            alignment: Alignment analysis from ANALYZE_ALIGNMENT
            stories: Optional vault experience stories
            options: Optional parameters like rewriteCoverage, mustEditLineNumbers, etc.

        Returns:
            Formatted user prompt string
        """
        stories = stories or []
        options = options or {}

        stories_text = '\n'.join(
            f"{i+1}. [{s.get('tag', 'general')}] {s.get('text', '')}"
            for i, s in enumerate(stories)
        ) or 'None'

        inventory_text = self._json_dumps(options.get('inventory', []))
        strategy_brief = options.get('strategyBrief')
        strategy_brief_text = f"\n\n<cv_strategy_brief>\n{self._json_dumps(strategy_brief)}\n</cv_strategy_brief>" if strategy_brief else ''
        bullet_review = options.get('bulletReview')
        bullet_review_text = f"\n\n<per_bullet_analysis>\n{self._json_dumps(bullet_review)}\n</per_bullet_analysis>" if bullet_review else ''
        rewrite_coverage = options.get('rewriteCoverage')
        rewrite_coverage_text = ''
        if rewrite_coverage is not None:
            coverage_json = self._json_dumps({
                'item_edit_ratio': rewrite_coverage,
                'item_edit_percent': int(rewrite_coverage * 100),
                'target_item_edit_count': options.get('targetItemEditCount', 0),
                'total_item_count': options.get('totalItemCount', 0),
            })
            rewrite_coverage_text = (
                f"\n\n<desired_rewrite_coverage>\n"
                f"{coverage_json}\n"
                f"</desired_rewrite_coverage>"
            )
        must_edit = options.get('mustEditLineNumbers')
        must_edit_text = f"\n\n<must_edit_item_lines>\n{self._json_dumps(must_edit)}\n</must_edit_item_lines>" if must_edit else ''
        preferred_edit = options.get('preferredEditLineNumbers')
        preferred_edit_text = f"\n\n<preferred_edit_item_lines>\n{self._json_dumps(preferred_edit)}\n</preferred_edit_item_lines>" if preferred_edit else ''
        feedback = options.get('feedback')
        feedback_text = f"\n\n<attempt_feedback>\n{feedback}\n</attempt_feedback>" if feedback else ''
        exhaustive = options.get('exhaustiveInventory', False)
        source_label = (
            'The text inside <replaceable_source> is the ONLY pool you may use for original_text, and every line there must produce one output object in the same order.'
            if exhaustive else
            'Read the full LaTeX below and copy original_text only from it.'
        )

        return f"""<alignment_analysis>
{self._json_dumps(alignment)}
</alignment_analysis>

<grounded_vault_experience>
{stories_text}
</grounded_vault_experience>{strategy_brief_text}{bullet_review_text}

<rewrite_inventory>
{inventory_text}
</rewrite_inventory>{rewrite_coverage_text}{preferred_edit_text}{must_edit_text}{feedback_text}

<replaceable_source>
{latex}
</replaceable_source>

<non_negotiable_rules>
- {source_label}
- The rewrite_inventory defines the target rows. Follow its order exactly.
- Each rewrite_inventory row may include target_keywords, current_keywords, and rewrite_goal. Use those as the first-choice plan for that specific bullet.
- The cv_strategy_brief describes what should stay prominent, what can be compressed, and what kind of bullet rewrites create the most value.
- If per_bullet_analysis is provided, use each bullet's verdict and suggestion as a starting point for your rewrite.
- Aim to edit roughly the requested share of item bullets, not all of them.
- Prioritize item lines listed in <preferred_edit_item_lines> first when choosing which bullets to rewrite.
- Lines listed in <must_edit_item_lines> must receive substantive edits in this attempt.
- A valid edit must improve at least TWO of: keyword coverage, action verb strength, specificity, ownership, scope, stakeholder context, outcome framing, or ATS clarity.
- Prefer meaningful reframes over minimal edits. If a bullet can truthfully say the same thing in a stronger, clearer, more job-relevant way, rewrite it fully.
- The vault experience is the ONLY place you may pull in new supporting facts or metrics from.
- If a job keyword is unsupported by both the source and the vault, do not force it into the resume.
- If a line does not support keyword injection, improve clarity, ordering, phrasing, ownership, scope, stakeholder context, or emphasis instead.
- Quality beats count. Returning keep for some item bullets is allowed when they are already strong or lower priority than the requested coverage target.
</non_negotiable_rules>"""

    @property
    def COVER_LETTER_SYSTEM(self) -> str:
        return self._prompts.get('COVER_LETTER_SYSTEM', '')

    def build_cover_letter_user(
        self,
        parsed_req: Dict,
        latex: str,
        alignment: Dict,
        job: Optional[Dict] = None,
        user_story: str = '',
        template: str = ''
    ) -> str:
        """
        Build the cover letter user prompt.

        Args:
            parsed_req: Parsed job requirements from PARSE_JOB
            latex: The candidate's CV LaTeX
            alignment: Alignment analysis from ANALYZE_ALIGNMENT
            job: Optional job metadata
            user_story: Optional user story/objectives
            template: Cover letter template LaTeX

        Returns:
            Formatted user prompt string
        """
        user_story_text = f"\n\n<user_story_objectives>\n{user_story}\n</user_story_objectives>" if user_story.strip() else ''

        return f"""<job_requirements>
{self._json_dumps(parsed_req)}
</job_requirements>

<job_metadata>
{self._json_dumps(job or {})}
</job_metadata>

<candidate_cv_latex>
{latex}
</candidate_cv_latex>

<alignment_analysis>
{self._json_dumps(alignment)}
</alignment_analysis>

<cover_letter_template>
{template}
</cover_letter_template>

<template_usage_rules>
- The template is for formatting structure, pacing, and professional voice only.
- Ignore any placeholders or old personal details in the template.
- Your output will be inserted into the template later, so only provide raw LaTeX body paragraphs and the closing inside JSON.
</template_usage_rules>{user_story_text}

Write the cover letter body JSON."""

    @property
    def REVIEW_APPLIED_CV_SYSTEM(self) -> str:
        return self._prompts.get('REVIEW_APPLIED_CV_SYSTEM', '')

    def build_review_applied_cv_user(self, params: Dict) -> str:
        """Build the review applied CV user prompt."""
        return f"""<job_requirements>
{self._json_dumps(params.get('parsedReq', {}))}
</job_requirements>

<job_metadata>
{self._json_dumps(params.get('job', {}))}
</job_metadata>

<run_context>
{self._json_dumps(params.get('runContext', {}))}
</run_context>

<original_cv>
{params.get('originalCv', '')}
</original_cv>

<accepted_cv>
{params.get('acceptedCv', '')}
</accepted_cv>

<original_metrics>
{self._json_dumps(params.get('originalMetrics', {}))}
</original_metrics>

<suggested_draft_metrics>
{self._json_dumps(params.get('suggestedMetrics', {}))}
</suggested_draft_metrics>

<accepted_draft_metrics>
{self._json_dumps(params.get('acceptedMetrics', {}))}
</accepted_draft_metrics>

<original_alignment_summary>
{self._json_dumps(params.get('originalAlignment', {}))}
</original_alignment_summary>

<accepted_alignment_summary>
{self._json_dumps(params.get('acceptedAlignment', {}))}
</accepted_alignment_summary>

<user_choices>
{self._json_dumps(params.get('userChoices', {}))}
</user_choices>

Evaluate whether the accepted draft improved relative to the original CV for this job, then return the required JSON."""

    @property
    def COMPANY_RESEARCH_SYSTEM(self) -> str:
        return self._prompts.get('COMPANY_RESEARCH_SYSTEM', '')

    @property
    def COMPANY_RESEARCH_USER(self):
        def build(company: str, role: str = '') -> str:
            role_part = f' for the role "{role}"' if role else ''
            return f'Conduct deep interview research for the company "{company}"{role_part}. Provide a concise report covering culture, recent news, interview style, employee sentiment, and likely technical or business context.'
        return build

    @property
    def INTERVIEW_PREP_SYSTEM(self) -> str:
        return self._prompts.get('INTERVIEW_PREP_SYSTEM', '')

    @property
    def JOB_SUMMARY_SYSTEM(self) -> str:
        return self._prompts.get('JOB_SUMMARY_SYSTEM', '')

    @property
    def JOB_SUMMARY_USER(self):
        def build(job_description: str) -> str:
            return f"""<job_posting>
{job_description}
</job_posting>

Provide a compact summary that preserves the critical requirements and duties only."""
        return build

    @staticmethod
    def _json_dumps(obj: Any, indent: int = 2) -> str:
        """Serialize obj to JSON string."""
        import json
        return json.dumps(obj, indent=indent, ensure_ascii=False)


_default_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """Get singleton prompt loader instance."""
    global _default_loader
    if _default_loader is None:
        _default_loader = PromptLoader()
    return _default_loader
