"""Runtime/compiler options for Journey adapters."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class RobustnessConfig:
    """Checkbox-style generation and verification options."""

    strict_validation: bool = True
    run_generated_tests: bool = True
    generate_agent_manifest: bool = True
    generate_markdown_summary: bool = True
    fail_on_warnings: bool = False
    clean_output: bool = False

    @classmethod
    def from_profile(cls, profile: str) -> "RobustnessConfig":
        profiles = {
            "fast": cls(
                strict_validation=False,
                run_generated_tests=False,
                generate_agent_manifest=True,
                generate_markdown_summary=True,
                fail_on_warnings=False,
                clean_output=False,
            ),
            "standard": cls(),
            "strict": cls(
                strict_validation=True,
                run_generated_tests=True,
                generate_agent_manifest=True,
                generate_markdown_summary=True,
                fail_on_warnings=True,
                clean_output=True,
            ),
        }
        try:
            return profiles[profile]
        except KeyError as exc:
            valid = ", ".join(sorted(profiles))
            raise ValueError(f"Unknown robustness profile '{profile}'. Use one of: {valid}") from exc

    def with_overrides(self, **kwargs) -> "RobustnessConfig":
        return replace(self, **{key: value for key, value in kwargs.items() if value is not None})


DEFAULT_ROBUSTNESS = RobustnessConfig.from_profile("standard")
