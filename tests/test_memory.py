import json

from job_assist_skill.assistant.memory import PreferenceMemory


def test_preference_memory_creates_defaults_and_persists(tmp_path):
    memory_path = tmp_path / "preferences.json"
    memory = PreferenceMemory(str(memory_path))

    assert memory_path.exists()
    assert memory.get_value("search.stream") == "both"

    memory.remember_profile(name="Jane Doe", email="jane@example.com")
    memory.remember_files(cv_path="resume.tex", linkedin_session="linkedin_session.json")
    memory.remember_search(roles=["operations manager"], locations=["Riyadh"], stream="jobs")

    reloaded = PreferenceMemory(str(memory_path))
    assert reloaded.get_value("profile.name") == "Jane Doe"
    assert reloaded.get_value("application.sender_email") == "jane@example.com"
    assert reloaded.get_value("files.cv_path") == "resume.tex"
    assert reloaded.get_value("search.roles") == ["operations manager"]
    assert reloaded.get_value("search.stream") == "jobs"


def test_preference_memory_set_value_supports_nested_keys(tmp_path):
    memory = PreferenceMemory(str(tmp_path / "prefs.json"))
    memory.set_value("preferences.target_roles", ["analyst", "planner"])
    stored = json.loads((tmp_path / "prefs.json").read_text(encoding="utf-8"))
    assert stored["preferences"]["target_roles"] == ["analyst", "planner"]
