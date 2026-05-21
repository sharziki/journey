#!/usr/bin/env bash
set -euo pipefail

tag="${1:-}"

if [[ -z "$tag" ]]; then
  version="$(python - <<'PY'
import tomllib
from pathlib import Path

print(tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"])
PY
)"
  tag="v$version"
fi

version="${tag#v}"
base_url="https://github.com/sharziki/journey/releases/download/$tag"
wheel_name="journey_lang-$version-py3-none-any.whl"
sdist_name="journey_lang-$version.tar.gz"
repo_root="$(pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

cd "$tmpdir"

for name in "$wheel_name" "$sdist_name" SHA256SUMS journey-install-requirements.txt; do
  curl --retry 8 --retry-delay 3 --retry-all-errors -fsSLO "$base_url/$name"
done

sha256sum -c SHA256SUMS

python -m venv req-venv
req-venv/bin/python -m pip install --upgrade pip >/dev/null
req-venv/bin/python -m pip install -r journey-install-requirements.txt >/dev/null
req-venv/bin/python -m pip check
req-venv/bin/journey --version | grep -F "journey $version"
req-venv/bin/python -m journey --version | grep -F "journey $version"

cp "$repo_root/examples/library_borrowing.journey" library_borrowing.journey
req-venv/bin/journey validate library_borrowing.journey --strict
req-venv/bin/journey test library_borrowing.journey --robustness strict --clean

for artifact in "$wheel_name" "$sdist_name"; do
  venv="$tmpdir/venv-${artifact//[^a-zA-Z0-9]/-}"
  python -m venv "$venv"
  "$venv/bin/python" -m pip install --upgrade pip >/dev/null
  "$venv/bin/python" -m pip install "$tmpdir/$artifact" >/dev/null
  "$venv/bin/python" -m pip check
  "$venv/bin/journey" --version | grep -F "journey $version"
  "$venv/bin/python" -m journey --version | grep -F "journey $version"
  echo "public artifact install ok: $artifact"
done

echo "public release smoke ok: $tag"
