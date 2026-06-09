"""
AST node definitions for the Journey language.

The AST mirrors the structure of a .journey file:
  JourneySpec
    ├── entities: [Entity]
    │     ├── fields: [Field]
    │     └── (field modifiers: unique, hashed, auto, state, enum, format, min, max)
    ├── steps: [Step]
    │     ├── actor
    │     ├── inputs: [InputField]
    │     ├── actions: [Action]
    │     ├── outputs: [OutputField]
    │     └── errors: [ErrorDef]
    └── tests: [TestBlock]
          └── commands: [TestCommand]
"""

from dataclasses import dataclass, field
from typing import Optional


# --- Top-level ---


@dataclass
class JourneySpec:
    name: str
    description: Optional[str]
    entities: list["Entity"]
    steps: list["Step"]
    tests: list["TestBlock"]

    def get_entity(self, name: str) -> Optional["Entity"]:
        for e in self.entities:
            if e.name == name:
                return e
        return None

    def get_step(self, name: str) -> Optional["Step"]:
        for s in self.steps:
            if s.name == name:
                return s
        return None


# --- Entities ---


@dataclass
class StateType:
    """state(pending -> active -> suspended)"""
    states: list[str]
    transitions: dict[str, list[str]]  # {from: [to, ...]}


@dataclass
class EnumType:
    """enum(admin, member, viewer)"""
    values: list[str]


@dataclass
class FieldModifiers:
    unique: bool = False
    hashed: bool = False
    auto: bool = False
    format_type: Optional[str] = None  # "email", etc.
    min_val: Optional[int] = None
    max_val: Optional[int] = None


@dataclass
class Field:
    name: str
    type_name: str  # "string", "timestamp", "id", or entity name
    state_type: Optional[StateType] = None
    enum_type: Optional[EnumType] = None
    modifiers: FieldModifiers = field(default_factory=FieldModifiers)
    ref_entity: Optional[str] = None  # If type is an entity reference


@dataclass
class Entity:
    name: str
    fields: list[Field]


# --- Steps ---


@dataclass
class Actor:
    name: str  # "anonymous" or entity name like "User"
    authenticated: bool = False


@dataclass
class InputField:
    name: str
    type_name: str
    required: bool = False
    enum_type: Optional[EnumType] = None
    modifiers: FieldModifiers = field(default_factory=FieldModifiers)
    default: Optional[str] = None


@dataclass
class Action:
    """Raw action line from the spec. The codegen interprets these."""
    raw: str
    kind: str  # "create", "find", "transition", "send", "verify", "call"
    target: Optional[str] = None  # Entity or function name
    variable: Optional[str] = None  # LHS variable assignment
    params: dict[str, str] = field(default_factory=dict)


@dataclass
class OutputField:
    name: str
    expression: str  # e.g. "user.id", literal string, etc.


@dataclass
class ErrorDef:
    code_name: str  # e.g. "email_taken"
    message: str
    http_status: int


@dataclass
class Step:
    name: str
    requires: Optional[str] = None  # Name of prerequisite step
    actor: Actor = field(default_factory=lambda: Actor("anonymous"))
    inputs: list[InputField] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    outputs: list[OutputField] = field(default_factory=list)
    errors: list[ErrorDef] = field(default_factory=list)


# --- Tests ---


@dataclass
class TestExpectation:
    kind: str  # "status", "output", "error"
    target: str  # status code, field path, or error name
    value: Optional[str] = None  # Expected value (None = "exists")


@dataclass
class TestCommand:
    step_name: str
    args: dict[str, str]
    auth_token_var: Optional[str] = None  # "as authenticated(token)"
    expectations: list[TestExpectation] = field(default_factory=list)
    capture: Optional[str] = None  # Variable name to capture from response


@dataclass
class TestBlock:
    name: str
    commands: list[TestCommand]


# --- Natural-language sections (hybrid mode) ---


@dataclass
class PageRule:
    """A single rule or acceptance item inside a page spec."""
    text: str


@dataclass
class PageSpec:
    """A natural-language page specification."""
    name: str
    purpose: Optional[str] = None
    user_sees: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    acceptance: list[str] = field(default_factory=list)


@dataclass
class FlowDef:
    """A named flow: an ordered sequence of page names."""
    name: str
    steps: list[str] = field(default_factory=list)


@dataclass
class CrewRole:
    """A crew role with a description."""
    role: str
    description: str


@dataclass
class HybridJourneySpec:
    """A journey spec that can contain both natural-language sections and
    structured blocks (entities, steps, tests).

    This is the first-class representation for handwritten journey files
    that mix prose intent with structured backend definitions.
    """
    name: str
    description: Optional[str] = None
    mission: Optional[str] = None
    design: Optional[str] = None
    pages: list[PageSpec] = field(default_factory=list)
    page_names: list[str] = field(default_factory=list)
    flows: list[FlowDef] = field(default_factory=list)
    acceptance: list[str] = field(default_factory=list)
    crew: list[CrewRole] = field(default_factory=list)
    done_when: list[str] = field(default_factory=list)
    # Structured blocks (same as JourneySpec)
    entities: list[Entity] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    tests: list[TestBlock] = field(default_factory=list)

    def get_entity(self, name: str) -> Optional[Entity]:
        for e in self.entities:
            if e.name == name:
                return e
        return None

    def get_step(self, name: str) -> Optional[Step]:
        for s in self.steps:
            if s.name == name:
                return s
        return None

    def as_journey_spec(self) -> "JourneySpec":
        """Downcast to a plain JourneySpec for adapters that only understand
        structured blocks."""
        return JourneySpec(
            name=self.name,
            description=self.description or self.mission,
            entities=self.entities,
            steps=self.steps,
            tests=self.tests,
        )
