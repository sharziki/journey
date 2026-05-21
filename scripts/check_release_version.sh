#!/usr/bin/env bash
set -euo pipefail

tag="${1:-}"

if [[ -z "$tag" ]]; then
  if [[ "${GITHUB_REF_TYPE:-}" == "tag" && -n "${GITHUB_REF_NAME:-}" ]]; then
    tag="$GITHUB_REF_NAME"
  else
    version="$(python - <<'PY'
import tomllib
from pathlib import Path

print(tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"])
PY
)"
    tag="v$version"
  fi
fi

if [[ ! "$tag" =~ ^v[0-9]+[.][0-9]+[.][0-9]+$ ]]; then
  echo "Release tag must look like vX.Y.Z, got: $tag" >&2
  exit 2
fi

version="$(python - <<'PY'
import tomllib
from pathlib import Path

print(tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"])
PY
)"

expected="v$version"

if [[ "$tag" != "$expected" ]]; then
  echo "Release tag/version mismatch: tag is $tag but pyproject.toml is $version" >&2
  exit 1
fi

echo "release version ok: $tag"
