#!/usr/bin/env bash
set -euo pipefail

wheel="${1:-}"
if [[ -z "$wheel" ]]; then
  wheel="$(ls dist/journey_lang-*.whl | sort -V | tail -n 1)"
fi

if [[ ! -f "$wheel" ]]; then
  echo "Wheel not found: $wheel" >&2
  exit 2
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

python -m venv "$tmpdir/venv"
"$tmpdir/venv/bin/python" -m pip install --upgrade pip >/dev/null
"$tmpdir/venv/bin/python" -m pip install "$wheel" >/dev/null
"$tmpdir/venv/bin/journey" --version | grep -E '^journey [0-9]+\.[0-9]+\.[0-9]+'
"$tmpdir/venv/bin/python" -m journey --version | grep -E '^journey [0-9]+\.[0-9]+\.[0-9]+'
"$tmpdir/venv/bin/python" -c 'import importlib.metadata, journey; assert journey.__version__ == importlib.metadata.version("journey-lang")'
"$tmpdir/venv/bin/python" -c 'import journey.__main__'

cp examples/library_borrowing.journey "$tmpdir/library_borrowing.journey"
(
  cd "$tmpdir"
  "$tmpdir/venv/bin/journey" validate library_borrowing.journey --strict
  "$tmpdir/venv/bin/journey" test library_borrowing.journey --robustness strict --clean
)

project="$tmpdir/lightweight-app"
mkdir -p "$project/app/dashboard" "$project/app/api/leads"
cat > "$project/app/dashboard/page.tsx" <<'EOF'
export default function Dashboard() {
  async function saveLead() {
    await fetch("/api/leads", { method: "POST" })
  }
  return <main><a href="/settings">Settings</a><button onClick={saveLead}>Save Lead</button></main>
}
EOF
cat > "$project/app/api/leads/route.ts" <<'EOF'
export async function POST(request) {
  const body = await request.json()
  return Response.json({ ok: true, body }, { status: 201 })
}
EOF

"$tmpdir/venv/bin/journey" create "$project" --name "Wheel Smoke"
"$tmpdir/venv/bin/journey" doctor "$project" --strict
"$tmpdir/venv/bin/journey" agent "$project" --no-test -o "$project/handoff"
"$tmpdir/venv/bin/journey" status "$project"

test -f "$project/.journey/JOURNEY_FLOW.md"
test -f "$project/handoff/JOURNEY.md"
test -f "$project/handoff/journey.agent.json"

echo "wheel smoke ok: $wheel"
