#!/usr/bin/env bash
set -euo pipefail

dist_dir="${1:-dist}"
tag="${2:-}"

if [[ -z "$tag" ]]; then
  version="$(python - <<'PY'
import tomllib
from pathlib import Path

print(tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"])
PY
)"
  tag="v$version"
fi

wheel="$(ls "$dist_dir"/journey_lang-*-py3-none-any.whl | sort -V | tail -n 1)"
if [[ ! -f "$wheel" ]]; then
  echo "Wheel not found in $dist_dir" >&2
  exit 2
fi

hash="$(sha256sum "$wheel" | awk '{print $1}')"
wheel_name="$(basename "$wheel")"
output="$dist_dir/journey-install-requirements.txt"

cat > "$output" <<EOF
journey-lang @ https://github.com/sharziki/journey/releases/download/$tag/$wheel_name#sha256=$hash
EOF

echo "$output"
