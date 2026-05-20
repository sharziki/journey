import json
from argparse import Namespace

import pytest

from journey.adapters.fastapi import generate
from journey.cli.main import _autonomous_agent_command, cmd_agent, cmd_watch
from journey.core.config import RobustnessConfig
from journey.core.normalize import normalize
from journey.core.validation import JourneyValidationError, validate
from journey.parser import parse_file, parse_string


def test_validate_accepts_bundled_auth_example():
    spec = parse_file("examples/auth_workspaces.journey")

    report = validate(spec)

    assert report.ok
    assert report.issues == ()


def test_validate_rejects_missing_required_test_input():
    spec = parse_string(
        '''
        journey "Bad" {
          step signup {
            input {
              email string required
            }
          }

          test "missing input" {
            do signup()
              expect status 200
          }
        }
        '''
    )

    report = validate(spec)

    assert not report.ok
    assert [issue.code for issue in report.errors] == ["missing_input"]


def test_validate_strict_promotes_warnings_to_errors():
    spec = parse_string(
        '''
        journey "Strict" {
          step signup {
            input {
              email string required
            }
          }

          test "extra input" {
            do signup(email: "a@example.com", extra: "x")
              expect status 200
          }
        }
        '''
    )

    report = validate(spec, strict=True)

    assert not report.ok
    assert report.errors[0].code == "unknown_input"


def test_normalize_returns_agent_checklist():
    spec = parse_file("examples/journey_spine.journey")

    journey = normalize(spec)

    assert journey.slug == "journey-spine"
    assert "Parse journey 'Journey Spine'" in journey.checklist()
    assert "Implement step 'brief_agent'" in journey.checklist()


def test_fastapi_adapter_writes_agent_artifacts(tmp_path):
    spec = parse_file("examples/journey_spine.journey")
    config = RobustnessConfig.from_profile("standard")

    result = generate(spec, tmp_path, config=config)

    assert str(tmp_path / "JOURNEY.md") in result.files
    assert str(tmp_path / "journey.agent.json") in result.files
    manifest = json.loads((tmp_path / "journey.agent.json").read_text())
    assert manifest["schema"] == "journey.agent.v1"
    assert manifest["slug"] == "journey-spine"
    assert manifest["checklist"]


def test_adapter_raises_for_invalid_spec(tmp_path):
    spec = parse_string(
        '''
        journey "Broken" {
          entity Thing {
            owner MissingEntity
          }
        }
        '''
    )

    with pytest.raises(JourneyValidationError):
        generate(spec, tmp_path)


def test_agent_command_writes_handoff_without_tests(tmp_path):
    args = Namespace(
        file="examples/journey_spine.journey",
        output=str(tmp_path),
        robustness="strict",
        strict=False,
        clean=True,
        no_agent_manifest=False,
        no_markdown_summary=False,
        no_test=True,
    )

    cmd_agent(args)

    assert (tmp_path / "JOURNEY.md").exists()
    manifest = json.loads((tmp_path / "journey.agent.json").read_text())
    assert manifest["schema"] == "journey.agent.v1"
    assert manifest["slug"] == "journey-spine"


def test_watch_command_advances_one_deliverable(tmp_path):
    output = tmp_path / "generated"
    state_dir = tmp_path / "state"
    args = Namespace(
        file="examples/journey_spine.journey",
        output=str(output),
        robustness="strict",
        strict=False,
        clean=True,
        no_agent_manifest=False,
        no_markdown_summary=False,
        state_dir=str(state_dir),
        agent_command=None,
        once=True,
        max_cycles=1,
    )

    cmd_watch(args)

    state = json.loads((state_dir / "journey-spine.json").read_text())
    assert state["completed"] == ["Parse journey 'Journey Spine'"]


def test_autonomous_agent_command_prefers_environment(monkeypatch):
    monkeypatch.setenv("JOURNEY_AGENT_COMMAND", "custom-agent {item}")

    assert _autonomous_agent_command() == "custom-agent {item}"


def test_autonomous_agent_command_detects_codex(monkeypatch):
    monkeypatch.delenv("JOURNEY_AGENT_COMMAND", raising=False)
    monkeypatch.setattr("journey.cli.main.shutil.which", lambda name: "/usr/bin/codex" if name == "codex" else None)

    command = _autonomous_agent_command()

    assert command is not None
    assert command.startswith("codex exec -C")
    assert "{item}" in command
