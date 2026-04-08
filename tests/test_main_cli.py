import json

from main import main


def test_main_memory_commands(tmp_path, capsys):
    memory_path = tmp_path / "prefs.json"

    assert main(["memory", "set", "profile.name", "Jane Doe", "--memory-path", str(memory_path)]) == 0
    assert main(["memory", "show", "--memory-path", str(memory_path)]) == 0

    output = capsys.readouterr().out
    assert "Jane Doe" in output


def test_main_email_command_writes_json(tmp_path):
    memory_path = tmp_path / "prefs.json"
    output_path = tmp_path / "email.json"

    assert (
        main(
            [
                "email",
                "--job",
                "Operations Manager",
                "--company",
                "Example Co",
                "--output",
                str(output_path),
                "--memory-path",
                str(memory_path),
            ]
        )
        == 0
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["subject"] == "Application for Operations Manager at Example Co"
    assert payload["mailto_url"].startswith("mailto:")


def test_main_doctor_command_outputs_blocking_inputs(tmp_path, capsys):
    memory_path = tmp_path / "prefs.json"

    assert main(["doctor", "--memory-path", str(memory_path)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert "blocking_inputs" in payload
    assert any(item["key"] == "profile.name" for item in payload["blocking_inputs"])
