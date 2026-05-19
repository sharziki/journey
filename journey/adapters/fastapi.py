"""FastAPI adapter for Journey specs."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from journey.codegen import generate as generate_fastapi_project
from journey.core.config import DEFAULT_ROBUSTNESS, RobustnessConfig
from journey.core.normalize import normalize
from journey.core.validation import validate
from journey.parser.ast_nodes import JourneySpec

from .base import AdapterResult
from .markdown import write_markdown


class FastAPIAdapter:
    name = "fastapi"

    def generate(
        self,
        spec: JourneySpec,
        output_dir: str | Path,
        *,
        config: RobustnessConfig = DEFAULT_ROBUSTNESS,
    ) -> AdapterResult:
        report = validate(spec, strict=config.strict_validation)
        if config.fail_on_warnings and report.warnings:
            report = validate(spec, strict=True)
        report.raise_for_errors()

        out = Path(output_dir)
        if config.clean_output and out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True, exist_ok=True)

        files = list(generate_fastapi_project(spec, str(out)))
        if config.generate_markdown_summary:
            files.append(write_markdown(spec, out))
        if config.generate_agent_manifest:
            files.append(_write_agent_manifest(spec, out, config))

        return AdapterResult(files=tuple(files), output_dir=str(out))


def generate(spec: JourneySpec, output_dir: str | Path, *, config: RobustnessConfig = DEFAULT_ROBUSTNESS) -> AdapterResult:
    return FastAPIAdapter().generate(spec, output_dir, config=config)


def _write_agent_manifest(spec: JourneySpec, output_dir: Path, config: RobustnessConfig) -> str:
    journey = normalize(spec)
    path = output_dir / "journey.agent.json"
    payload = {
        "schema": "journey.agent.v1",
        "name": journey.name,
        "slug": journey.slug,
        "description": journey.description,
        "robustness": asdict(config),
        "checklist": list(journey.checklist()),
        "entities": [
            {
                "name": entity.name,
                "slug": entity.slug,
                "fields": [asdict(field) for field in entity.fields],
            }
            for entity in journey.entities
        ],
        "steps": [
            {
                "name": step.name,
                "slug": step.slug,
                "requires": step.requires,
                "actor": step.actor,
                "authenticated": step.authenticated,
                "inputs": [asdict(field) for field in step.inputs],
                "outputs": list(step.outputs),
                "errors": list(step.errors),
            }
            for step in journey.steps
        ],
        "tests": [
            {"name": test.name, "slug": test.slug, "steps": list(test.steps)}
            for test in journey.tests
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return str(path)
