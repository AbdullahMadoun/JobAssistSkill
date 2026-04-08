import json

from job_assist_skill.assistant.pipeline.alignment import CVAlignment
from job_assist_skill.assistant.pipeline.cover_letter import CoverLetterGenerator
from job_assist_skill.assistant.pipeline.job_parser import JobParser
from job_assist_skill.assistant.pipeline.replacer import CVReplacer
from job_assist_skill.assistant.pipeline.tailoring import CVTailoringPipeline


def test_job_parser_prepares_prompt_and_parses_response():
    parser = JobParser()
    prompt = parser.prepare_prompt("We are hiring an operations manager with Excel and stakeholder management.")

    assert "operations manager" in prompt["user"].lower()

    parsed = parser.parse_response(
        '```json {"title":"Operations Manager","company":"Example Co","required_skills":["Excel"]} ```',
        "We are hiring an operations manager.",
    )
    assert parsed["title"] == "Operations Manager"
    assert parsed["required_skills"] == ["Excel"]
    assert parsed["raw_text"].startswith("We are hiring")


def test_alignment_prepare_prompt_and_parse_response():
    analyzer = CVAlignment()
    prompt = analyzer.prepare_prompt({"title": "Operations Manager"}, "\\section{Experience}")
    assert "candidate_cv_latex" in prompt["user"]

    parsed = analyzer.parse_response('{"overall_score": 83, "sections": []}')
    assert parsed["overall_score"] == 83
    assert parsed["sections"] == []


def test_replacer_parses_changes_and_applies_them():
    replacer = CVReplacer()
    changes = replacer.parse_response(
        json.dumps(
            {
                "changes": [
                    {
                        "change_type": "edit",
                        "original_text": "Led team meetings",
                        "edited_text": "Led weekly team meetings across operations stakeholders",
                    }
                ]
            }
        )
    )
    updated = replacer.apply_changes("Led team meetings", changes)
    assert "operations stakeholders" in updated


def test_cover_letter_generator_prepares_prompt_and_extracts_body():
    generator = CoverLetterGenerator()
    prompt = generator.prepare_prompt({"title": "Planner"}, "CV latex")
    assert "cover letter" in prompt["system"].lower()

    body = generator.parse_response('{"body_latex":["Paragraph one.","Paragraph two."],"closing":"Best regards,"}')
    assert "Paragraph one." in body
    assert "Paragraph two." in body


def test_tailoring_pipeline_writes_context_and_applies_changes(tmp_path):
    pipeline = CVTailoringPipeline()
    cv_latex = "\\item Original bullet"
    result = pipeline.prepare(
        job_text="Hiring an analyst with reporting experience",
        cv_latex=cv_latex,
        output_dir=str(tmp_path),
        session_id="abc12345",
    )

    assert result.success
    assert result.context_path is not None
    assert (tmp_path / "context_abc12345.json").exists()

    payload = json.loads((tmp_path / "context_abc12345.json").read_text(encoding="utf-8"))
    assert "parse_prompt" in payload["job_requirements"]

    output_path = pipeline.apply_llm_results_from_payload(
        payload=payload,
        alignment_analysis={"overall_score": 75},
        suggested_changes=[
            {
                "change_type": "edit",
                "original_text": "Original bullet",
                "edited_text": "Rewritten bullet",
            }
        ],
        output_path=str(tmp_path / "tailored.tex"),
    )

    assert "Rewritten bullet" in (tmp_path / "tailored.tex").read_text(encoding="utf-8")
    assert output_path.endswith("tailored.tex")
