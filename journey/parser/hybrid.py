"""
Hybrid parser for Journey files that mix natural-language sections with
structured blocks (entity, step, test).

The hybrid parser is line-oriented: it reads section headers, collects
natural-language body content, and delegates structured blocks to the
existing token-based Lexer + Parser.

A hybrid journey file looks like:

    journey "Workspace Invite"

    design: ./design.md

    mission:
      Let a workspace owner invite a teammate.

    pages:
      - Signup
      - Dashboard

    page "Signup":
      purpose:
        Create a pending user account.
      user sees:
        - email input
        - password input
      rules:
        - email is required
      acceptance:
        - valid signup creates a pending user

    flows:
      onboarding:
        first: Signup
        then: Dashboard

    entity User {
      email string unique
    }

    step signup {
      input { email string required }
    }

    acceptance:
      - core flow works end to end

    crew:
      planner: Find the next missing item.

    done when:
      - every page has implementation
"""

from __future__ import annotations

import re
from dataclasses import field as dataclass_field

from .ast_nodes import (
    CrewRole,
    Entity,
    FlowDef,
    HybridJourneySpec,
    PageSpec,
    Step,
    TestBlock,
)
from .lexer import Lexer
from .parser import Parser


class HybridParseError(Exception):
    def __init__(self, message: str, line: int, filename: str):
        self.line = line
        self.filename = filename
        super().__init__(f"{filename}:{line}: {message}")


def parse_hybrid(source: str, filename: str = "<string>") -> HybridJourneySpec:
    """Parse a hybrid journey file that mixes natural-language and structured blocks."""
    return _HybridParser(source, filename).parse()


def is_hybrid_source(source: str) -> bool:
    """Heuristic: a file is hybrid if it has 'journey "..."' at the top but the
    next significant token after the name is NOT '{'.  It may also contain
    natural-language section headers like 'mission:', 'page "X":', etc."""
    stripped = source.strip()
    # Must start with journey "..."
    m = re.match(r'^\s*journey\s+"[^"]*"', stripped)
    if not m:
        return False
    rest = stripped[m.end():].lstrip()
    # If the very next non-whitespace char is '{', it's structured
    if rest.startswith("{"):
        return False
    # Otherwise it's hybrid (brace-free top level)
    return True


# ---------------------------------------------------------------------------
# Section header patterns
# ---------------------------------------------------------------------------

_JOURNEY_HEADER = re.compile(r'^\s*journey\s+"([^"]+)"')
_DESIGN_LINE = re.compile(r"^\s*design\s*:\s*(.+)$")
_MISSION_HEADER = re.compile(r"^\s*mission\s*:\s*$")
_PAGES_HEADER = re.compile(r"^\s*pages\s*:\s*$")
_PAGE_HEADER = re.compile(r'^\s*page\s+"([^"]+)"\s*:\s*$')
_FLOWS_HEADER = re.compile(r"^\s*flows\s*:\s*$")
_ACCEPTANCE_HEADER = re.compile(r"^\s*acceptance\s*:\s*$")
_CREW_HEADER = re.compile(r"^\s*crew\s*:\s*$")
_DONE_WHEN_HEADER = re.compile(r"^\s*done\s+when\s*:\s*$")
_ENTITY_HEADER = re.compile(r"^\s*entity\s+(\w+)\s*\{")
_STEP_HEADER = re.compile(r"^\s*step\s+(\w+)\s*\{")
_TEST_HEADER = re.compile(r'^\s*test\s+"([^"]+)"\s*\{')

# Sub-section headers inside a page spec
_PURPOSE_HEADER = re.compile(r"^\s*purpose\s*:\s*$")
_USER_SEES_HEADER = re.compile(r"^\s*user\s+sees\s*:\s*$")
_RULES_HEADER = re.compile(r"^\s*rules\s*:\s*$")

# Bullet line
_BULLET = re.compile(r"^\s*-\s+(.+)$")

# Flow sub-entry
_FLOW_NAME_HEADER = re.compile(r"^\s*(\w[\w\s]*):\s*$")
_FLOW_FIRST = re.compile(r"^\s*first\s*:\s*(.+)$")
_FLOW_THEN = re.compile(r"^\s*then\s*:\s*(.+)$")

# Crew entry: "  role_name: description"
_CREW_ENTRY = re.compile(r"^\s*(\w+)\s*:\s*(.+)$")

# Design inline: "design: path"
_DESIGN_INLINE = re.compile(r"^\s*design\s*:\s*(.+)$")


def _is_section_header(line: str) -> bool:
    """Return True if the line starts a new top-level or page-level section."""
    for pattern in (
        _JOURNEY_HEADER, _DESIGN_LINE, _MISSION_HEADER, _PAGES_HEADER,
        _PAGE_HEADER, _FLOWS_HEADER, _ACCEPTANCE_HEADER, _CREW_HEADER,
        _DONE_WHEN_HEADER, _ENTITY_HEADER, _STEP_HEADER, _TEST_HEADER,
    ):
        if pattern.match(line):
            return True
    return False


def _is_page_subsection_header(line: str) -> bool:
    """Return True if the line is a page sub-section header."""
    stripped = line.strip()
    for pattern in (_PURPOSE_HEADER, _USER_SEES_HEADER, _RULES_HEADER, _ACCEPTANCE_HEADER):
        if pattern.match(stripped):
            return True
    return False


class _HybridParser:
    def __init__(self, source: str, filename: str):
        self.source = source
        self.filename = filename
        self.lines = source.splitlines()
        self.pos = 0  # current line index

    def _line(self) -> str:
        if self.pos < len(self.lines):
            return self.lines[self.pos]
        return ""

    def _at_end(self) -> bool:
        return self.pos >= len(self.lines)

    def _advance(self) -> str:
        line = self._line()
        self.pos += 1
        return line

    def _skip_blank(self):
        while not self._at_end() and self._line().strip() == "":
            self.pos += 1

    def _skip_blank_and_comments(self):
        while not self._at_end():
            stripped = self._line().strip()
            if stripped == "" or stripped.startswith("#"):
                self.pos += 1
            else:
                break

    def _error(self, msg: str) -> HybridParseError:
        return HybridParseError(msg, self.pos + 1, self.filename)

    # ------------------------------------------------------------------
    # Indented text collection helpers
    # ------------------------------------------------------------------

    def _collect_indented_text(self, *, stop_at_page_subsections: bool = False) -> str:
        """Collect lines that are indented (continuation of a block)."""
        lines = []
        while not self._at_end():
            line = self._line()
            if line.strip() == "":
                lines.append("")
                self.pos += 1
                continue
            if line.startswith((" ", "\t")) and not _is_section_header(line):
                # Stop at page sub-section headers if requested
                if stop_at_page_subsections and _is_page_subsection_header(line):
                    break
                lines.append(line.strip())
                self.pos += 1
            else:
                break
        # Trim trailing blanks
        while lines and lines[-1] == "":
            lines.pop()
        return " ".join(line for line in lines if line)

    def _collect_bullet_items(self, *, stop_at_page_subsections: bool = False) -> list[str]:
        """Collect bullet items (lines starting with '- ')."""
        items = []
        while not self._at_end():
            line = self._line()
            if line.strip() == "" or line.strip().startswith("#"):
                self.pos += 1
                continue
            # Stop at page sub-section headers if requested
            if stop_at_page_subsections and _is_page_subsection_header(line):
                break
            m = _BULLET.match(line)
            if m:
                items.append(m.group(1).strip())
                self.pos += 1
            elif line.startswith((" ", "\t")) and not _is_section_header(line):
                # Continuation of previous bullet or indented text we skip
                if items:
                    items[-1] += " " + line.strip()
                self.pos += 1
            else:
                break
        return items

    # ------------------------------------------------------------------
    # Structured block extraction
    # ------------------------------------------------------------------

    def _extract_braced_block(self) -> str:
        """Extract a complete braced block (entity/step/test) starting at
        the current line.  Returns the full text including the opening line."""
        start = self.pos
        depth = 0
        block_lines = []
        while not self._at_end():
            line = self._line()
            block_lines.append(line)
            depth += line.count("{") - line.count("}")
            self.pos += 1
            if depth <= 0:
                break
        if depth > 0:
            raise self._error("Unterminated braced block")
        return "\n".join(block_lines)

    def _parse_entity_block(self) -> Entity:
        block = self._extract_braced_block()
        # Wrap in a minimal journey so the structured parser can handle it
        wrapped = f'journey "__hybrid_temp__" {{\n{block}\n}}'
        spec = _parse_structured(wrapped, self.filename)
        if not spec.entities:
            raise self._error("Failed to parse entity block")
        return spec.entities[0]

    def _parse_step_block(self) -> Step:
        block = self._extract_braced_block()
        wrapped = f'journey "__hybrid_temp__" {{\n{block}\n}}'
        spec = _parse_structured(wrapped, self.filename)
        if not spec.steps:
            raise self._error("Failed to parse step block")
        return spec.steps[0]

    def _parse_test_block(self) -> TestBlock:
        block = self._extract_braced_block()
        wrapped = f'journey "__hybrid_temp__" {{\n{block}\n}}'
        spec = _parse_structured(wrapped, self.filename)
        if not spec.tests:
            raise self._error("Failed to parse test block")
        return spec.tests[0]

    # ------------------------------------------------------------------
    # Section parsers
    # ------------------------------------------------------------------

    def _parse_mission(self) -> str:
        self._advance()  # skip "mission:" line
        return self._collect_indented_text()

    def _parse_pages_list(self) -> list[str]:
        self._advance()  # skip "pages:" line
        return self._collect_bullet_items()

    def _parse_page_spec(self, name: str) -> PageSpec:
        self._advance()  # skip 'page "Name":' line
        page = PageSpec(name=name)

        while not self._at_end():
            self._skip_blank_and_comments()
            if self._at_end():
                break
            line = self._line()

            # Check if we've left the page section (hit a top-level header)
            if _is_section_header(line) and not _PURPOSE_HEADER.match(line) and not _USER_SEES_HEADER.match(line) and not _RULES_HEADER.match(line) and not _ACCEPTANCE_HEADER.match(line):
                break

            if _PURPOSE_HEADER.match(line):
                self._advance()
                page.purpose = self._collect_indented_text(stop_at_page_subsections=True)
            elif _USER_SEES_HEADER.match(line):
                self._advance()
                page.user_sees = self._collect_bullet_items(stop_at_page_subsections=True)
            elif _RULES_HEADER.match(line):
                self._advance()
                page.rules = self._collect_bullet_items(stop_at_page_subsections=True)
            elif _ACCEPTANCE_HEADER.match(line):
                self._advance()
                page.acceptance = self._collect_bullet_items(stop_at_page_subsections=True)
            elif line.startswith((" ", "\t")):
                # Sub-section headers within a page must be indented
                # If it's indented but not a known sub-header, skip
                self._advance()
            else:
                break

        return page

    def _parse_flows(self) -> list[FlowDef]:
        self._advance()  # skip "flows:" line
        flows = []

        while not self._at_end():
            line = self._line()
            stripped = line.strip()
            if stripped == "" or stripped.startswith("#"):
                self.pos += 1
                continue

            # Check if we've left the flows section
            if not line.startswith((" ", "\t")):
                break

            # Try named flow header: "  flow_name:"
            m = _FLOW_NAME_HEADER.match(stripped)
            if m:
                flow_name = m.group(1).strip()
                self._advance()
                steps = self._parse_flow_steps()
                flows.append(FlowDef(name=flow_name, steps=steps))
            else:
                # Bullet-style flow (simple list)
                bullet = _BULLET.match(stripped)
                if bullet:
                    flows.append(FlowDef(name=bullet.group(1).strip(), steps=[]))
                self._advance()

        return flows

    def _parse_flow_steps(self) -> list[str]:
        steps = []
        while not self._at_end():
            line = self._line()
            stripped = line.strip()
            if stripped == "" or stripped.startswith("#"):
                self.pos += 1
                continue
            m_first = _FLOW_FIRST.match(stripped)
            m_then = _FLOW_THEN.match(stripped)
            if m_first:
                steps.append(m_first.group(1).strip())
                self._advance()
            elif m_then:
                steps.append(m_then.group(1).strip())
                self._advance()
            elif stripped.startswith(("first:", "then:")):
                # Shouldn't happen but handle gracefully
                self._advance()
            elif line.startswith((" ", "\t")) and not _is_section_header(line) and not _FLOW_NAME_HEADER.match(stripped):
                # Continuation/unknown indented content
                self._advance()
            else:
                break
        return steps

    def _parse_crew(self) -> list[CrewRole]:
        self._advance()  # skip "crew:" line
        roles = []
        while not self._at_end():
            line = self._line()
            stripped = line.strip()
            if stripped == "" or stripped.startswith("#"):
                self.pos += 1
                continue
            if not line.startswith((" ", "\t")):
                break
            m = _CREW_ENTRY.match(stripped)
            if m:
                role_name = m.group(1).strip()
                desc_start = m.group(2).strip()
                self._advance()
                # Collect continuation lines
                continuation = []
                while not self._at_end():
                    next_line = self._line()
                    if next_line.strip() == "":
                        self.pos += 1
                        break
                    if next_line.startswith((" ", "\t")) and not _CREW_ENTRY.match(next_line.strip()):
                        continuation.append(next_line.strip())
                        self.pos += 1
                    else:
                        break
                desc = " ".join([desc_start] + continuation)
                roles.append(CrewRole(role=role_name, description=desc))
            else:
                self._advance()
        return roles

    def _parse_done_when(self) -> list[str]:
        self._advance()  # skip "done when:" line
        return self._collect_bullet_items()

    # ------------------------------------------------------------------
    # Main parse loop
    # ------------------------------------------------------------------

    def parse(self) -> HybridJourneySpec:
        self._skip_blank_and_comments()

        # Parse journey header
        m = _JOURNEY_HEADER.match(self._line())
        if not m:
            raise self._error("Expected 'journey \"Name\"'")
        name = m.group(1)
        self._advance()

        spec = HybridJourneySpec(name=name)

        while not self._at_end():
            self._skip_blank_and_comments()
            if self._at_end():
                break

            line = self._line()

            # design: path
            m = _DESIGN_INLINE.match(line)
            if m:
                spec.design = m.group(1).strip()
                self._advance()
                continue

            # mission:
            if _MISSION_HEADER.match(line):
                spec.mission = self._parse_mission()
                continue

            # pages:
            if _PAGES_HEADER.match(line):
                spec.page_names = self._parse_pages_list()
                continue

            # page "Name":
            m = _PAGE_HEADER.match(line)
            if m:
                spec.pages.append(self._parse_page_spec(m.group(1)))
                continue

            # flows:
            if _FLOWS_HEADER.match(line):
                spec.flows = self._parse_flows()
                continue

            # acceptance:
            if _ACCEPTANCE_HEADER.match(line):
                self._advance()  # skip "acceptance:" line
                spec.acceptance = self._collect_bullet_items()
                continue

            # crew:
            if _CREW_HEADER.match(line):
                spec.crew = self._parse_crew()
                continue

            # done when:
            if _DONE_WHEN_HEADER.match(line):
                spec.done_when = self._parse_done_when()
                continue

            # entity Block {
            if _ENTITY_HEADER.match(line):
                spec.entities.append(self._parse_entity_block())
                continue

            # step block {
            if _STEP_HEADER.match(line):
                spec.steps.append(self._parse_step_block())
                continue

            # test "name" {
            if _TEST_HEADER.match(line):
                spec.tests.append(self._parse_test_block())
                continue

            # description "..." on same line as journey header — unlikely in hybrid
            # but handle gracefully
            if line.strip().startswith("description "):
                m = re.match(r'^\s*description\s+"([^"]*)"', line)
                if m:
                    spec.description = m.group(1)
                    self._advance()
                    continue

            # Unknown line — skip (comments are already handled)
            self._advance()

        return spec


def _parse_structured(source: str, filename: str):
    """Parse a wrapped structured block using the standard lexer/parser."""
    from .lexer import Lexer
    from .parser import Parser

    lexer = Lexer(source, filename)
    tokens = lexer.tokenize()
    parser = Parser(tokens, filename)
    return parser.parse()
