"""Adapter protocol for compiling Journey specs to concrete artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from journey.core.config import DEFAULT_ROBUSTNESS, RobustnessConfig
from journey.parser.ast_nodes import JourneySpec


@dataclass(frozen=True)
class AdapterResult:
    files: tuple[str, ...]
    output_dir: str


class JourneyAdapter(Protocol):
    name: str

    def generate(
        self,
        spec: JourneySpec,
        output_dir: str | Path,
        *,
        config: RobustnessConfig = DEFAULT_ROBUSTNESS,
    ) -> AdapterResult:
        """Generate artifacts from a Journey spec."""
