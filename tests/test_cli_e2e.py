import json
import os
import socket
import subprocess
import sys
import textwrap
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cli_generates_tests_and_serves_a_backend(tmp_path):
    source = tmp_path / "smoke_e2e.journey"
    source.write_text(
        textwrap.dedent(
            '''
            journey "Smoke E2E" {
              entity Lead {
                email string unique
                status state(new -> contacted)
              }

              step capture_lead {
                actor anonymous
                input {
                  email string required format(email)
                }
                action {
                  lead = create Lead(email: input.email, status: new)
                }
                output {
                  lead_id lead.id
                  status lead.status
                }
              }

              step contact_lead {
                requires capture_lead
                actor anonymous
                input {
                  lead_id id required
                }
                action {
                  lead = find Lead(id: input.lead_id, status: new)
                  lead.status -> contacted
                }
                output {
                  lead_id lead.id
                  status lead.status
                }
                errors {
                  invalid_lead "Lead is missing or no longer new" 400
                }
              }

              test "lead gets contacted" {
                do capture_lead(email: "e2e@example.com")
                  expect status 201
                  capture lead_id

                do contact_lead(lead_id: lead_id)
                  expect status 200
              }
            }
            '''
        ).strip()
        + "\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)

    _run_cli(["validate", str(source), "--strict"], tmp_path, env)
    _run_cli(["test", str(source), "--clean", "--robustness", "strict"], tmp_path, env)
    _run_cli(["compile", str(source), "--clean", "--robustness", "strict"], tmp_path, env)

    port = _free_port()
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "generated.smoke_e2e.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        openapi = _wait_for_openapi(port, server)
        assert openapi["info"]["title"] == "Smoke E2E"
        assert "/journey/smoke-e2-e/leads" in openapi["paths"]
        assert "/journey/smoke-e2-e/contact-lead" in openapi["paths"]
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


def test_cli_creates_lightweight_graph_and_agent_handoff(tmp_path):
    app_page = tmp_path / "app" / "dashboard" / "page.tsx"
    api_route = tmp_path / "app" / "api" / "leads" / "route.ts"
    app_page.parent.mkdir(parents=True)
    api_route.parent.mkdir(parents=True)
    app_page.write_text(
        textwrap.dedent(
            """
            export default function Dashboard() {
              async function saveLead() {
                await fetch("/api/leads", { method: "POST" })
              }
              return <main><a href="/settings">Settings</a><button onClick={saveLead}>Save Lead</button></main>
            }
            """
        ).strip()
        + "\n"
    )
    api_route.write_text(
        textwrap.dedent(
            """
            export async function POST(request) {
              const body = await request.json()
              return Response.json({ ok: true, body }, { status: 201 })
            }
            """
        ).strip()
        + "\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)

    _run_cli(["create", ".", "--name", "Lead Desk"], tmp_path, env)
    _run_cli(["doctor", ".", "--strict"], tmp_path, env)
    _run_cli(["agent", ".", "--no-test", "-o", "handoff"], tmp_path, env)
    status = _run_cli(["status", "."], tmp_path, env)

    repo = tmp_path / ".journey" / "repo.journey"
    page = tmp_path / ".journey" / "pages" / "dashboard.journey"
    api = tmp_path / ".journey" / "apis" / "leads.journey"
    flow = tmp_path / ".journey" / "JOURNEY_FLOW.md"
    manifest = json.loads((tmp_path / "handoff" / "journey.agent.json").read_text())
    markdown = (tmp_path / "handoff" / "JOURNEY.md").read_text()

    assert repo.exists()
    assert page.exists()
    assert api.exists()
    assert flow.exists()
    assert "route: /dashboard" in page.read_text()
    assert "calls `/api/leads`" in page.read_text()
    assert "method `POST`" in api.read_text()
    assert "| page | `/dashboard` | `./pages/dashboard.journey` | `app/dashboard/page.tsx` |" in flow.read_text()
    assert manifest["mode"] == "lightweight"
    assert len(manifest["journeys"]) == 3
    assert "pages/dashboard.journey" in markdown
    assert "Journey: Lead Desk" in status.stdout
    assert "Drift: none" in status.stdout
    assert "Errors: 0" in status.stdout


def _run_cli(args, cwd, env):
    result = subprocess.run(
        [sys.executable, "-m", "journey", *args],
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert result.returncode == 0, result.stdout
    return result


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_openapi(port, server):
    last = None
    for _ in range(40):
        if server.poll() is not None:
            output = server.stdout.read() if server.stdout else ""
            raise AssertionError(f"server exited with {server.returncode}\n{output}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/openapi.json", timeout=1) as response:
                return json.load(response)
        except Exception as exc:
            last = exc
            time.sleep(0.25)
    output = server.stdout.read() if server.stdout else ""
    raise AssertionError(f"server did not serve OpenAPI: {last}\n{output}")
