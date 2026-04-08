from job_assist_skill.assistant.prompts.loader import PromptLoader


def test_prompt_loader_reads_repo_prompts():
    loader = PromptLoader()

    assert loader.PARSE_JOB_SYSTEM
    assert loader.ANALYZE_ALIGNMENT_SYSTEM
    assert loader.REPLACE_SYSTEM
