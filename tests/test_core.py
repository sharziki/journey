import json

import pytest

from journey.adapters.fastapi import generate
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
