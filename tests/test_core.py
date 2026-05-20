import json
from argparse import Namespace

import pytest

from journey.adapters.fastapi import generate
from journey.cli.main import _autonomous_agent_command, cmd_agent, cmd_execute, cmd_shape, cmd_watch
from journey.core.natural import shape_unstructured_journey
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


def test_fastapi_adapter_uses_shared_slug_and_enum_literals(tmp_path):
    spec = parse_string(
        '''
        journey "CRM Sales Pipeline" {
          entity Deal {
            stage enum(discovery, proposal)
          }

          step open_deal {
            actor anonymous
            action {
              deal = create Deal(stage: discovery)
            }
            output {
              deal_id deal.id
            }
          }

          test "open deal" {
            do open_deal()
              expect status 201
          }
        }
        '''
    )

    generate(spec, tmp_path)

    routes = (tmp_path / "routes.py").read_text()
    tests = (tmp_path / "test_journey.py").read_text()
    assert 'prefix="/journey/crm-sales-pipeline"' in routes
    assert '"/journey/crm-sales-pipeline/open-deal"' in tests
    assert "stage=DealStage.discovery" in routes


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


def test_shape_unstructured_journey_extracts_pages_and_design():
    journey = shape_unstructured_journey(
        """
        # Habit App

        design: ./design.md

        Build an app where people track small daily habits.

        pages:
          - Landing
          - Dashboard

        acceptance:
          - users can see today's habits
          - empty states are clear
        """,
        filename="habit.journey",
    )

    assert journey.name == "Habit App"
    assert journey.design == "./design.md"
    assert journey.pages == ("Landing", "Dashboard")
    assert "users can see today's habits" in journey.acceptance
    assert 'page "Dashboard"' in journey.shaped_text


def test_shape_command_writes_handoff(tmp_path):
    source = tmp_path / "idea.journey"
    source.write_text("Build a dashboard app.\n\npages:\n  - Dashboard\n")
    output = tmp_path / "handoff"
    args = Namespace(file=str(source), output=str(output))

    cmd_shape(args)

    assert (output / "shaped.journey").exists()
    assert (output / "JOURNEY.md").exists()
    assert json.loads((output / "journey.agent.json").read_text())["mode"] == "natural"


def test_execute_unstructured_autonomous_advances_one_item(tmp_path, monkeypatch):
    source = tmp_path / "idea.journey"
    source.write_text("Build a workspace app.\n\npages:\n  - Dashboard\n")
    output = tmp_path / "handoff"
    state_dir = tmp_path / "state"
    monkeypatch.setenv("JOURNEY_AGENT_COMMAND", "true")
    monkeypatch.setenv("JOURNEY_SKIP_PROJECT_QA", "1")
    args = Namespace(
        file=str(source),
        output=str(output),
        autonomous=True,
        state_dir=str(state_dir),
        once=True,
        max_cycles=1,
        robustness="strict",
        strict=False,
        clean=True,
        no_agent_manifest=False,
        no_markdown_summary=False,
    )

    cmd_execute(args)

    state_files = list(state_dir.glob("*.json"))
    assert state_files
    state = json.loads(state_files[0].read_text())
    assert state["completed"]
