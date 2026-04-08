from job_assist_skill.assistant.pipeline.alignment import CVAlignment
from job_assist_skill.assistant.pipeline.cover_letter import CoverLetterGenerator
from job_assist_skill.assistant.pipeline.job_parser import JobParser
from job_assist_skill.assistant.pipeline.replacer import CVReplacer


def test_job_parser_prepares_and_parses():
    parser = JobParser()
    prompt = parser.prepare_prompt("Hiring an analyst with SQL experience.")
    parsed = parser.parse_response(
        '{"company":"Example Co","title":"Analyst","required_skills":["SQL"],"preferred_skills":[],"responsibilities":[],"industry_keywords":[],"soft_skills":[],"education":"","experience_years":"","culture_signals":[],"keyword_taxonomy":{"hard_skills":["SQL"],"tools":[],"certifications":[],"domain_knowledge":[]}}',
        job_text="Hiring an analyst with SQL experience.",
    )

    assert prompt["system"]
    assert "SQL" in parsed["required_skills"]


def test_alignment_and_replace_and_cover_letter_parsers():
    alignment = CVAlignment()
    replace = CVReplacer()
    cover = CoverLetterGenerator()

    alignment_payload = alignment.parse_response(
        '{"overall_score":80,"overall_verdict":"Strong fit","sections":[],"missing_from_cv":[],"strongest_matches":[],"recommended_emphasis":[]}'
    )
    replace_payload = replace.parse_response(
        '[{"original_text":"old","edited_text":"new","change_type":"edit"}]'
    )
    cover_letter = cover.parse_response('{"body":"Dear Hiring Team,\\\\n\\\\nI am interested."}')

    assert alignment_payload["overall_score"] == 80
    assert replace_payload[0]["edited_text"] == "new"
    assert "I am interested" in cover_letter
