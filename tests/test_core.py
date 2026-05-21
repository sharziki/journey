import json
from argparse import Namespace

import pytest

from journey.adapters.fastapi import generate
from journey.cli.main import (
    _autonomous_agent_command,
    cmd_agent,
    cmd_create,
    cmd_diff,
    cmd_doctor,
    cmd_execute,
    cmd_inspect,
    cmd_manifest,
    cmd_shape,
    cmd_status,
    cmd_sync,
    cmd_validate,
    cmd_watch,
)
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


def test_fastapi_adapter_generates_runtime_config_hooks(tmp_path):
    spec = parse_file("examples/auth_workspaces.journey")

    generate(spec, tmp_path)

    database = (tmp_path / "database.py").read_text()
    routes = (tmp_path / "routes.py").read_text()
    assert 'os.getenv("JOURNEY_DATABASE_URL", "sqlite:///./journey.db")' in database
    assert 'connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}' in database
    assert 'SESSION_TTL_HOURS = int(os.getenv("JOURNEY_SESSION_TTL_HOURS", "24"))' in routes
    assert 'if session["expires_at"] <= datetime.now(timezone.utc):' in routes


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


def test_create_command_writes_route_and_feature_flow(tmp_path):
    args = Namespace(file="examples/auth_workspaces.journey", output=str(tmp_path), filename="FLOW.md")

    cmd_create(args)

    flow = (tmp_path / "FLOW.md").read_text()
    assert "# User Onboarding Journey Flow" in flow
    assert "`POST` | `/journey/user-onboarding/signup`" in flow
    assert "## Feature Flow" in flow
    assert "### 1. signup" in flow
    assert "transition `user.status` to `active`" in flow
    assert "## Acceptance Walkthroughs" in flow


def test_create_command_scaffolds_folder_level_journeys(tmp_path):
    app_page = tmp_path / "app" / "dashboard" / "page.tsx"
    api_route = tmp_path / "app" / "api" / "leads" / "route.ts"
    app_page.parent.mkdir(parents=True)
    api_route.parent.mkdir(parents=True)
    app_page.write_text("export default function Dashboard() { return null }\n")
    api_route.write_text("export async function POST() { return Response.json({ ok: true }) }\n")
    args = Namespace(
        file=str(tmp_path),
        output=None,
        filename="JOURNEY_FLOW.md",
        name="Example App",
        force=False,
    )

    cmd_create(args)

    repo = tmp_path / ".journey" / "repo.journey"
    page = tmp_path / ".journey" / "pages" / "dashboard.journey"
    api = tmp_path / ".journey" / "apis" / "leads.journey"
    assert repo.exists()
    assert page.exists()
    assert api.exists()
    assert "children:" in repo.read_text()
    assert "  - ./apis/leads.journey" in repo.read_text()
    assert "  - ./pages/dashboard.journey" in repo.read_text()
    assert "parent: ../repo.journey" in page.read_text()
    assert "source: ../../app/dashboard/page.tsx" in page.read_text()
    assert "level: api" in api.read_text()
    assert "source: ../../app/api/leads/route.ts" in api.read_text()


def test_create_command_treats_dotted_existing_path_as_directory(tmp_path):
    project = tmp_path / "app.v1"
    app_page = project / "app" / "dashboard" / "page.tsx"
    app_page.parent.mkdir(parents=True)
    app_page.write_text("export default function Dashboard() { return null }\n")
    args = Namespace(
        file=str(project),
        output=None,
        filename="JOURNEY_FLOW.md",
        name="Dotted App",
        force=False,
    )

    cmd_create(args)

    assert (project / ".journey" / "repo.journey").exists()
    assert (project / ".journey" / "pages" / "dashboard.journey").exists()


def test_agent_command_uses_lightweight_graph_for_folder_journeys(tmp_path):
    app_page = tmp_path / "app" / "dashboard" / "page.tsx"
    app_page.parent.mkdir(parents=True)
    app_page.write_text("export default function Dashboard() { return null }\n")
    create_args = Namespace(
        file=str(tmp_path),
        output=None,
        filename="JOURNEY_FLOW.md",
        name="Example App",
        force=False,
    )
    cmd_create(create_args)
    output = tmp_path / "handoff"
    agent_args = Namespace(
        file=str(tmp_path),
        output=str(output),
        robustness="strict",
        strict=False,
        clean=True,
        no_agent_manifest=False,
        no_markdown_summary=False,
        no_test=True,
    )

    cmd_agent(agent_args)

    manifest = json.loads((output / "journey.agent.json").read_text())
    markdown = (output / "JOURNEY.md").read_text()
    assert manifest["mode"] == "lightweight"
    assert len(manifest["journeys"]) == 2
    assert "app runtime, database, or code generator" in markdown
    assert "pages/dashboard.journey" in markdown


def test_manifest_command_uses_lightweight_graph_for_folder_journeys(tmp_path):
    app_page = tmp_path / "app" / "dashboard" / "page.tsx"
    app_page.parent.mkdir(parents=True)
    app_page.write_text("export default function Dashboard() { return null }\n")
    cmd_create(Namespace(file=str(tmp_path), output=None, filename="JOURNEY_FLOW.md", name="Example App", force=False))
    output = tmp_path / "manifest"

    cmd_manifest(
        Namespace(
            file=str(tmp_path),
            output=str(output),
            robustness="strict",
            strict=False,
            clean=True,
            no_agent_manifest=False,
            no_markdown_summary=False,
        )
    )

    assert (output / "JOURNEY.md").exists()
    assert json.loads((output / "journey.agent.json").read_text())["mode"] == "lightweight"


def test_sync_adds_new_journeys_without_overwriting_existing_specs(tmp_path):
    app_page = tmp_path / "app" / "dashboard" / "page.tsx"
    app_page.parent.mkdir(parents=True)
    app_page.write_text("export default function Dashboard() { return null }\n")
    cmd_create(Namespace(file=str(tmp_path), output=None, filename="JOURNEY_FLOW.md", name="Example App", force=False))
    page = tmp_path / ".journey" / "pages" / "dashboard.journey"
    page.write_text(page.read_text() + "\ncustom note: keep this\n")

    settings_page = tmp_path / "app" / "settings" / "page.tsx"
    api_route = tmp_path / "app" / "api" / "leads" / "route.ts"
    settings_page.parent.mkdir(parents=True)
    api_route.parent.mkdir(parents=True)
    settings_page.write_text("export default function Settings() { return null }\n")
    api_route.write_text("export async function POST() { return Response.json({ ok: true }) }\n")

    cmd_sync(Namespace(file=str(tmp_path), name="Example App", force=False))

    repo = (tmp_path / ".journey" / "repo.journey").read_text()
    assert "custom note: keep this" in page.read_text()
    assert (tmp_path / ".journey" / "pages" / "settings.journey").exists()
    assert (tmp_path / ".journey" / "apis" / "leads.journey").exists()
    assert "./pages/settings.journey" in repo
    assert "./apis/leads.journey" in repo


def test_doctor_accepts_healthy_lightweight_graph(tmp_path, capsys):
    app_page = tmp_path / "app" / "dashboard" / "page.tsx"
    api_route = tmp_path / "app" / "api" / "leads" / "route.ts"
    app_page.parent.mkdir(parents=True)
    api_route.parent.mkdir(parents=True)
    app_page.write_text("export default function Dashboard() { return null }\n")
    api_route.write_text("export async function POST() { return Response.json({ ok: true }) }\n")
    cmd_create(Namespace(file=str(tmp_path), output=None, filename="JOURNEY_FLOW.md", name="Example App", force=False))
    capsys.readouterr()

    cmd_doctor(Namespace(file=str(tmp_path), strict=False))

    assert capsys.readouterr().out.strip() == "Journey doctor: ok"


def test_doctor_reports_missing_orphan_stale_and_acceptance_issues(tmp_path, capsys):
    app_page = tmp_path / "app" / "dashboard" / "page.tsx"
    app_page.parent.mkdir(parents=True)
    app_page.write_text("export default function Dashboard() { return null }\n")
    cmd_create(Namespace(file=str(tmp_path), output=None, filename="JOURNEY_FLOW.md", name="Example App", force=False))
    (tmp_path / ".journey" / "pages" / "orphan.journey").write_text(
        'journey "Orphan"\n\nlevel: page\nsource: ../../app/orphan/page.tsx\n'
    )
    page = tmp_path / ".journey" / "pages" / "dashboard.journey"
    page.write_text('journey "Dashboard"\n\nparent: ../repo.journey\nlevel: page\nsource: ../../app/missing/page.tsx\n')
    settings_page = tmp_path / "app" / "settings" / "page.tsx"
    settings_page.parent.mkdir(parents=True)
    settings_page.write_text("export default function Settings() { return null }\n")
    capsys.readouterr()

    cmd_doctor(Namespace(file=str(tmp_path), strict=False))

    output = capsys.readouterr().out
    assert "missing_journey" in output
    assert "orphan_journey" in output
    assert "stale_source" in output
    assert "missing_acceptance" in output


def test_doctor_strict_exits_on_warnings(tmp_path):
    journey_dir = tmp_path / ".journey"
    journey_dir.mkdir()
    (journey_dir / "repo.journey").write_text(
        'journey "Broken App"\n\nlevel: repo\n\nchildren:\n  - ./pages/missing.journey\n'
    )

    with pytest.raises(SystemExit) as exc:
        cmd_doctor(Namespace(file=str(tmp_path), strict=True))

    assert exc.value.code == 1


def test_diff_reports_no_drift_for_synced_graph(tmp_path, capsys):
    app_page = tmp_path / "app" / "dashboard" / "page.tsx"
    app_page.parent.mkdir(parents=True)
    app_page.write_text("export default function Dashboard() { return null }\n")
    cmd_create(Namespace(file=str(tmp_path), output=None, filename="JOURNEY_FLOW.md", name="Example App", force=False))
    capsys.readouterr()

    cmd_diff(Namespace(file=str(tmp_path), check=False))

    assert capsys.readouterr().out.strip() == "Journey diff: no drift"


def test_diff_reports_drift_and_suggests_sync(tmp_path, capsys):
    app_page = tmp_path / "app" / "dashboard" / "page.tsx"
    app_page.parent.mkdir(parents=True)
    app_page.write_text("export default function Dashboard() { return null }\n")
    cmd_create(Namespace(file=str(tmp_path), output=None, filename="JOURNEY_FLOW.md", name="Example App", force=False))
    (tmp_path / ".journey" / "pages" / "orphan.journey").write_text(
        'journey "Orphan"\n\nlevel: page\nsource: ../../app/orphan/page.tsx\nacceptance:\n  - ok\n'
    )
    page = tmp_path / ".journey" / "pages" / "dashboard.journey"
    page.write_text(page.read_text().replace("source: ../../app/dashboard/page.tsx", "source: ../../app/missing/page.tsx"))
    settings_page = tmp_path / "app" / "settings" / "page.tsx"
    settings_page.parent.mkdir(parents=True)
    settings_page.write_text("export default function Settings() { return null }\n")
    capsys.readouterr()

    cmd_diff(Namespace(file=str(tmp_path), check=False))

    output = capsys.readouterr().out
    assert "+ missing_journey" in output
    assert "- stale_source" in output
    assert "? orphan_journey" in output
    assert f"journey sync {tmp_path}" in output


def test_diff_check_exits_when_drift_exists(tmp_path):
    journey_dir = tmp_path / ".journey"
    journey_dir.mkdir()
    (journey_dir / "repo.journey").write_text(
        'journey "Broken App"\n\nlevel: repo\n\nchildren:\n  - ./pages/missing.journey\n'
    )

    with pytest.raises(SystemExit) as exc:
        cmd_diff(Namespace(file=str(tmp_path), check=True))

    assert exc.value.code == 1


def test_status_summarizes_lightweight_graph(tmp_path, capsys):
    app_page = tmp_path / "app" / "dashboard" / "page.tsx"
    api_route = tmp_path / "app" / "api" / "leads" / "route.ts"
    app_page.parent.mkdir(parents=True)
    api_route.parent.mkdir(parents=True)
    app_page.write_text("export default function Dashboard() { return null }\n")
    api_route.write_text("export async function POST() { return Response.json({ ok: true }) }\n")
    cmd_create(Namespace(file=str(tmp_path), output=None, filename="JOURNEY_FLOW.md", name="Example App", force=False))
    capsys.readouterr()

    cmd_status(Namespace(file=str(tmp_path)))

    output = capsys.readouterr().out
    assert "Journey: Example App" in output
    assert "Mode: lightweight graph" in output
    assert "Pages: 1 covered / 0 missing" in output
    assert "APIs: 1 covered / 0 missing" in output
    assert "Drift: none" in output
    assert f"Next: journey watch {tmp_path} --once" in output


def test_status_summarizes_lightweight_drift(tmp_path, capsys):
    app_page = tmp_path / "app" / "dashboard" / "page.tsx"
    app_page.parent.mkdir(parents=True)
    app_page.write_text("export default function Dashboard() { return null }\n")
    cmd_create(Namespace(file=str(tmp_path), output=None, filename="JOURNEY_FLOW.md", name="Example App", force=False))
    settings_page = tmp_path / "app" / "settings" / "page.tsx"
    settings_page.parent.mkdir(parents=True)
    settings_page.write_text("export default function Settings() { return null }\n")
    capsys.readouterr()

    cmd_status(Namespace(file=str(tmp_path)))

    output = capsys.readouterr().out
    assert "Pages: 1 covered / 1 missing" in output
    assert "Drift: 1 issue(s)" in output
    assert f"Next: journey diff {tmp_path}" in output


def test_status_summarizes_structured_journey(capsys):
    cmd_status(Namespace(file="examples/auth_workspaces.journey"))

    output = capsys.readouterr().out
    assert "Journey: User Onboarding" in output
    assert "Mode: structured backend" in output
    assert "Entities: 3" in output
    assert "Steps: 6" in output
    assert "Tests: 3" in output


def test_lightweight_example_is_healthy(tmp_path):
    output = tmp_path / "handoff"
    cmd_validate(Namespace(file="examples/lightweight_client_portal", strict=False))
    cmd_doctor(Namespace(file="examples/lightweight_client_portal", strict=False))
    cmd_diff(Namespace(file="examples/lightweight_client_portal", check=True))
    cmd_agent(
        Namespace(
            file="examples/lightweight_client_portal",
            output=str(output),
            robustness="strict",
            strict=False,
            clean=True,
            no_agent_manifest=False,
            no_markdown_summary=False,
            no_test=True,
        )
    )

    assert json.loads((output / "journey.agent.json").read_text())["mode"] == "lightweight"


def test_validate_accepts_lightweight_graph(tmp_path, capsys):
    app_page = tmp_path / "app" / "dashboard" / "page.tsx"
    app_page.parent.mkdir(parents=True)
    app_page.write_text("export default function Dashboard() { return null }\n")
    cmd_create(Namespace(file=str(tmp_path), output=None, filename="JOURNEY_FLOW.md", name="Example App", force=False))
    capsys.readouterr()

    cmd_validate(Namespace(file=str(tmp_path), strict=False))

    assert capsys.readouterr().out.strip() == "ok"


def test_validate_rejects_missing_lightweight_child(tmp_path):
    journey_dir = tmp_path / ".journey"
    journey_dir.mkdir()
    (journey_dir / "repo.journey").write_text(
        'journey "Broken App"\n\nlevel: repo\n\nchildren:\n  - ./pages/missing.journey\n'
    )

    with pytest.raises(SystemExit) as exc:
        cmd_validate(Namespace(file=str(tmp_path), strict=False))

    assert exc.value.code == 1


def test_inspect_prints_lightweight_graph(tmp_path, capsys):
    app_page = tmp_path / "app" / "dashboard" / "page.tsx"
    app_page.parent.mkdir(parents=True)
    app_page.write_text("export default function Dashboard() { return null }\n")
    cmd_create(Namespace(file=str(tmp_path), output=None, filename="JOURNEY_FLOW.md", name="Example App", force=False))
    capsys.readouterr()

    cmd_inspect(Namespace(file=str(tmp_path), strict=False))

    output = capsys.readouterr().out
    assert "Journey Graph: Example App" in output
    assert "pages/dashboard.journey" in output
    assert "Validation:\n  ok" in output


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


def test_watch_command_advances_lightweight_graph(tmp_path, monkeypatch):
    app_page = tmp_path / "app" / "dashboard" / "page.tsx"
    output = tmp_path / "handoff"
    state_dir = tmp_path / "state"
    app_page.parent.mkdir(parents=True)
    app_page.write_text("export default function Dashboard() { return null }\n")
    cmd_create(Namespace(file=str(tmp_path), output=None, filename="JOURNEY_FLOW.md", name="Example App", force=False))
    monkeypatch.setenv("JOURNEY_SKIP_PROJECT_QA", "1")
    args = Namespace(
        file=str(tmp_path),
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

    state = json.loads((state_dir / "example-app.json").read_text())
    assert state["completed"] == ["Read root journey 'Example App'"]
    assert json.loads((output / "journey.agent.json").read_text())["mode"] == "lightweight"


def test_execute_lightweight_non_autonomous_prepares_agent_handoff(tmp_path, monkeypatch):
    app_page = tmp_path / "app" / "dashboard" / "page.tsx"
    output = tmp_path / "handoff"
    app_page.parent.mkdir(parents=True)
    app_page.write_text("export default function Dashboard() { return null }\n")
    cmd_create(Namespace(file=str(tmp_path), output=None, filename="JOURNEY_FLOW.md", name="Example App", force=False))
    monkeypatch.setenv("JOURNEY_SKIP_PROJECT_QA", "1")
    args = Namespace(
        file=str(tmp_path),
        output=str(output),
        autonomous=False,
        state_dir=str(tmp_path / "state"),
        once=True,
        max_cycles=1,
        robustness="strict",
        strict=False,
        clean=True,
        no_agent_manifest=False,
        no_markdown_summary=False,
    )

    with pytest.raises(SystemExit) as exc:
        cmd_execute(args)

    assert exc.value.code == 0
    assert json.loads((output / "journey.agent.json").read_text())["mode"] == "lightweight"


def test_execute_lightweight_autonomous_advances_one_item(tmp_path, monkeypatch):
    app_page = tmp_path / "app" / "dashboard" / "page.tsx"
    output = tmp_path / "handoff"
    state_dir = tmp_path / "state"
    app_page.parent.mkdir(parents=True)
    app_page.write_text("export default function Dashboard() { return null }\n")
    cmd_create(Namespace(file=str(tmp_path), output=None, filename="JOURNEY_FLOW.md", name="Example App", force=False))
    monkeypatch.setenv("JOURNEY_AGENT_COMMAND", "true")
    monkeypatch.setenv("JOURNEY_SKIP_PROJECT_QA", "1")
    args = Namespace(
        file=str(tmp_path),
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

    state = json.loads((state_dir / "example-app.json").read_text())
    assert state["completed"] == ["Read root journey 'Example App'"]


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
