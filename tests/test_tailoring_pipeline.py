import json

from job_assist_skill.assistant.pipeline.tailoring import CVTailoringPipeline


def test_tailoring_pipeline_prepares_and_applies(tmp_path):
    pipeline = CVTailoringPipeline()
    cv_latex = "\\section{Experience}\n\\item Built reporting workflows."
    result = pipeline.prepare(
        job_text="We are hiring an operations manager with process improvement experience.",
        cv_latex=cv_latex,
        output_dir=str(tmp_path),
        session_id="abc12345",
    )

    assert result.success is True
    assert result.context is not None
    assert result.context.parse_job_prompt["system"]
    assert result.context_path is not None

    context_payload = json.loads((tmp_path / "context_abc12345.json").read_text(encoding="utf-8"))
    output_path = pipeline.apply_llm_results_from_payload(
        payload=context_payload,
        alignment_analysis={"overall_score": 80},
        suggested_changes=[
            {
                "original_text": "Built reporting workflows.",
                "edited_text": "Led reporting workflow improvements across business operations.",
                "change_type": "edit",
            }
        ],
    )

    tailored = (tmp_path / "cv_abc12345_tailored.tex").read_text(encoding="utf-8")
    assert output_path.endswith("cv_abc12345_tailored.tex")
    assert "Led reporting workflow improvements" in tailored


def test_tailoring_pipeline_builds_follow_up_prompts():
    pipeline = CVTailoringPipeline()
    alignment_prompt = pipeline.build_alignment_prompt(
        parsed_job={"title": "Analyst", "required_skills": ["SQL"]},
        cv_latex="\\section{Skills}\\item SQL",
    )
    replace_prompt = pipeline.build_replace_prompt(
        cv_latex="\\item SQL",
        alignment={"overall_score": 60, "sections": []},
    )

    assert alignment_prompt["system"]
    assert "SQL" in alignment_prompt["user"]
    assert replace_prompt["system"]
    assert "\\item SQL" in replace_prompt["user"]
