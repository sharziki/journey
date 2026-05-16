"""
Recursive descent parser for the Journey language.

Consumes tokens from the Lexer and produces an AST (JourneySpec).
"""

from typing import Optional

from .ast_nodes import (
    Action,
    Actor,
    Entity,
    EnumType,
    ErrorDef,
    Field,
    FieldModifiers,
    InputField,
    JourneySpec,
    OutputField,
    StateType,
    Step,
    TestBlock,
    TestCommand,
    TestExpectation,
)
from .lexer import Token, TokenType


class ParseError(Exception):
    def __init__(self, message: str, token: Token, filename: str):
        self.token = token
        self.filename = filename
        super().__init__(
            f"{filename}:{token.line}:{token.col}: {message} (got {token.type.name} {token.value!r})"
        )


class Parser:
    def __init__(self, tokens: list[Token], filename: str = "<string>"):
        self.tokens = tokens
        self.filename = filename
        self.pos = 0

    def error(self, msg: str) -> ParseError:
        return ParseError(msg, self.current(), self.filename)

    def current(self) -> Token:
        return self.tokens[self.pos]

    def peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]  # EOF

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def skip_newlines(self):
        while self.current().type == TokenType.NEWLINE:
            self.advance()

    def expect(self, ttype: TokenType, value: Optional[str] = None) -> Token:
        tok = self.current()
        if tok.type != ttype:
            raise self.error(f"Expected {ttype.name}" + (f" '{value}'" if value else ""))
        if value is not None and tok.value != value:
            raise self.error(f"Expected '{value}'")
        self.advance()
        return tok

    def match(self, ttype: TokenType, value: Optional[str] = None) -> Optional[Token]:
        tok = self.current()
        if tok.type == ttype and (value is None or tok.value == value):
            self.advance()
            return tok
        return None

    def at(self, ttype: TokenType, value: Optional[str] = None) -> bool:
        tok = self.current()
        return tok.type == ttype and (value is None or tok.value == value)

    # ========================================
    # Top-level
    # ========================================

    def parse(self) -> JourneySpec:
        self.skip_newlines()
        self.expect(TokenType.JOURNEY)
        name = self.expect(TokenType.STRING).value
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        self.skip_newlines()

        description = None
        entities = []
        steps = []
        tests = []

        while not self.at(TokenType.RBRACE):
            self.skip_newlines()
            if self.at(TokenType.RBRACE):
                break

            tok = self.current()

            if tok.type == TokenType.DESCRIPTION:
                self.advance()
                description = self.expect(TokenType.STRING).value
                self.skip_newlines()
            elif tok.type == TokenType.ENTITY:
                entities.append(self.parse_entity())
            elif tok.type == TokenType.STEP:
                steps.append(self.parse_step())
            elif tok.type == TokenType.TEST:
                tests.append(self.parse_test_block())
            else:
                raise self.error(f"Unexpected token at journey level")

        self.expect(TokenType.RBRACE)
        return JourneySpec(
            name=name,
            description=description,
            entities=entities,
            steps=steps,
            tests=tests,
        )

    # ========================================
    # Entity
    # ========================================

    def parse_entity(self) -> Entity:
        self.expect(TokenType.ENTITY)
        name = self.expect(TokenType.IDENTIFIER).value
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        self.skip_newlines()

        fields = []
        while not self.at(TokenType.RBRACE):
            self.skip_newlines()
            if self.at(TokenType.RBRACE):
                break
            fields.append(self.parse_field())
            self.skip_newlines()

        self.expect(TokenType.RBRACE)
        self.skip_newlines()
        return Entity(name=name, fields=fields)

    def parse_field(self) -> Field:
        name = self.expect(TokenType.IDENTIFIER).value

        # Type: could be a simple identifier, state(...), or enum(...)
        state_type = None
        enum_type = None
        ref_entity = None
        type_name = ""

        if self.at(TokenType.STATE):
            self.advance()
            state_type = self.parse_state_type()
            type_name = "state"
        elif self.at(TokenType.ENUM):
            self.advance()
            enum_type = self.parse_enum_type()
            type_name = "enum"
        else:
            tok = self.advance()
            type_name = tok.value
            # Check if it's an entity reference (starts with uppercase)
            if type_name[0].isupper():
                ref_entity = type_name

        # Parse modifiers
        modifiers = self.parse_field_modifiers()

        return Field(
            name=name,
            type_name=type_name,
            state_type=state_type,
            enum_type=enum_type,
            modifiers=modifiers,
            ref_entity=ref_entity,
        )

    def parse_state_type(self) -> StateType:
        """Parse state(pending -> active -> suspended)"""
        self.expect(TokenType.LPAREN)
        states = []
        transitions = {}

        first = self.expect(TokenType.IDENTIFIER).value
        states.append(first)

        while self.match(TokenType.ARROW):
            next_state = self.expect(TokenType.IDENTIFIER).value
            # Record transition from previous state to this one
            prev = states[-1]
            if prev not in transitions:
                transitions[prev] = []
            transitions[prev].append(next_state)
            states.append(next_state)

        # Last state has no outgoing transitions
        if states[-1] not in transitions:
            transitions[states[-1]] = []

        self.expect(TokenType.RPAREN)
        return StateType(states=states, transitions=transitions)

    def parse_enum_type(self) -> EnumType:
        """Parse enum(admin, member, viewer)"""
        self.expect(TokenType.LPAREN)
        values = [self.expect(TokenType.IDENTIFIER).value]
        while self.match(TokenType.COMMA):
            self.skip_newlines()
            values.append(self.expect(TokenType.IDENTIFIER).value)
        self.expect(TokenType.RPAREN)
        return EnumType(values=values)

    def parse_field_modifiers(self) -> FieldModifiers:
        mods = FieldModifiers()
        while True:
            if self.match(TokenType.UNIQUE):
                mods.unique = True
            elif self.match(TokenType.HASHED):
                mods.hashed = True
            elif self.match(TokenType.AUTO):
                mods.auto = True
            elif self.match(TokenType.REQUIRED):
                mods.required = True  # Only used in InputField but parsed generically
            elif self.at(TokenType.FORMAT):
                self.advance()
                self.expect(TokenType.LPAREN)
                mods.format_type = self.expect(TokenType.IDENTIFIER).value
                self.expect(TokenType.RPAREN)
            elif self.at(TokenType.MIN):
                self.advance()
                self.expect(TokenType.LPAREN)
                mods.min_val = int(self.expect(TokenType.NUMBER).value)
                self.expect(TokenType.RPAREN)
            elif self.at(TokenType.MAX):
                self.advance()
                self.expect(TokenType.LPAREN)
                mods.max_val = int(self.expect(TokenType.NUMBER).value)
                self.expect(TokenType.RPAREN)
            else:
                break
        return mods

    # ========================================
    # Step
    # ========================================

    def parse_step(self) -> Step:
        self.expect(TokenType.STEP)
        name = self.expect(TokenType.IDENTIFIER).value
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        self.skip_newlines()

        step = Step(name=name)

        while not self.at(TokenType.RBRACE):
            self.skip_newlines()
            if self.at(TokenType.RBRACE):
                break

            tok = self.current()

            if tok.type == TokenType.REQUIRES:
                self.advance()
                step.requires = self.expect(TokenType.IDENTIFIER).value
                self.skip_newlines()
            elif tok.type == TokenType.ACTOR:
                self.advance()
                actor_name = self.advance().value  # "anonymous" or entity name
                authenticated = bool(self.match(TokenType.AUTHENTICATED))
                step.actor = Actor(name=actor_name, authenticated=authenticated)
                self.skip_newlines()
            elif tok.type == TokenType.INPUT:
                self.advance()
                self.skip_newlines()
                self.expect(TokenType.LBRACE)
                self.skip_newlines()
                while not self.at(TokenType.RBRACE):
                    self.skip_newlines()
                    if self.at(TokenType.RBRACE):
                        break
                    step.inputs.append(self.parse_input_field())
                    self.skip_newlines()
                self.expect(TokenType.RBRACE)
                self.skip_newlines()
            elif tok.type == TokenType.ACTION:
                self.advance()
                self.skip_newlines()
                self.expect(TokenType.LBRACE)
                self.skip_newlines()
                while not self.at(TokenType.RBRACE):
                    self.skip_newlines()
                    if self.at(TokenType.RBRACE):
                        break
                    step.actions.append(self.parse_action())
                    self.skip_newlines()
                self.expect(TokenType.RBRACE)
                self.skip_newlines()
            elif tok.type == TokenType.OUTPUT:
                self.advance()
                self.skip_newlines()
                self.expect(TokenType.LBRACE)
                self.skip_newlines()
                while not self.at(TokenType.RBRACE):
                    self.skip_newlines()
                    if self.at(TokenType.RBRACE):
                        break
                    step.outputs.append(self.parse_output_field())
                    self.skip_newlines()
                self.expect(TokenType.RBRACE)
                self.skip_newlines()
            elif tok.type == TokenType.ERRORS:
                self.advance()
                self.skip_newlines()
                self.expect(TokenType.LBRACE)
                self.skip_newlines()
                while not self.at(TokenType.RBRACE):
                    self.skip_newlines()
                    if self.at(TokenType.RBRACE):
                        break
                    step.errors.append(self.parse_error_def())
                    self.skip_newlines()
                self.expect(TokenType.RBRACE)
                self.skip_newlines()
            else:
                raise self.error(f"Unexpected token in step '{name}'")

        self.expect(TokenType.RBRACE)
        self.skip_newlines()
        return step

    def parse_input_field(self) -> InputField:
        name = self.expect(TokenType.IDENTIFIER).value

        # Type
        enum_type = None
        type_name = ""

        if self.at(TokenType.ENUM):
            self.advance()
            enum_type = self.parse_enum_type()
            type_name = "enum"
        else:
            type_name = self.advance().value

        # Modifiers (required, format, min, max, etc.)
        required = False
        default = None
        modifiers = FieldModifiers()

        while True:
            if self.match(TokenType.REQUIRED):
                required = True
            elif self.at(TokenType.FORMAT):
                self.advance()
                self.expect(TokenType.LPAREN)
                modifiers.format_type = self.expect(TokenType.IDENTIFIER).value
                self.expect(TokenType.RPAREN)
            elif self.at(TokenType.MIN):
                self.advance()
                self.expect(TokenType.LPAREN)
                modifiers.min_val = int(self.expect(TokenType.NUMBER).value)
                self.expect(TokenType.RPAREN)
            elif self.at(TokenType.MAX):
                self.advance()
                self.expect(TokenType.LPAREN)
                modifiers.max_val = int(self.expect(TokenType.NUMBER).value)
                self.expect(TokenType.RPAREN)
            elif self.at(TokenType.DEFAULT):
                self.advance()
                self.expect(TokenType.LPAREN)
                if self.at(TokenType.STRING):
                    default = self.advance().value
                else:
                    default = self.advance().value
                self.expect(TokenType.RPAREN)
            elif self.match(TokenType.UNIQUE):
                modifiers.unique = True
            else:
                break

        return InputField(
            name=name,
            type_name=type_name,
            required=required,
            enum_type=enum_type,
            modifiers=modifiers,
            default=default,
        )

    def parse_action(self) -> Action:
        """Parse an action line. Actions are flexible — we capture the structure."""
        # Check for variable assignment: var = ...
        variable = None
        if (
            self.current().type == TokenType.IDENTIFIER
            and self.peek(1).value == "="
        ):
            variable = self.advance().value
            self.advance()  # skip =

        tok = self.current()

        if tok.type == TokenType.CREATE:
            return self._parse_create_action(variable)
        elif tok.type == TokenType.FIND:
            return self._parse_find_action(variable)
        elif tok.type == TokenType.SEND:
            return self._parse_send_action(variable)
        elif tok.type == TokenType.VERIFY:
            return self._parse_verify_action(variable)
        elif tok.type == TokenType.IDENTIFIER:
            # Could be a dotted transition: entity.field -> value
            # Or a function call: add_member(...)
            return self._parse_generic_action(variable)
        else:
            raise self.error("Expected action (create, find, send, verify, or identifier)")

    def _parse_create_action(self, variable: Optional[str]) -> Action:
        self.advance()  # skip 'create'
        target = self.advance().value  # Entity name
        params = {}
        if self.match(TokenType.LPAREN):
            params = self._parse_params()
            self.expect(TokenType.RPAREN)
        return Action(
            raw=f"create {target}",
            kind="create",
            target=target,
            variable=variable,
            params=params,
        )

    def _parse_find_action(self, variable: Optional[str]) -> Action:
        self.advance()  # skip 'find'
        target = self.advance().value
        params = {}
        if self.match(TokenType.LPAREN):
            params = self._parse_params()
            self.expect(TokenType.RPAREN)
        return Action(
            raw=f"find {target}",
            kind="find",
            target=target,
            variable=variable,
            params=params,
        )

    def _parse_send_action(self, variable: Optional[str]) -> Action:
        self.advance()  # skip 'send'
        target = self.advance().value  # "email"
        params = {}
        if self.match(TokenType.LPAREN):
            params = self._parse_params()
            self.expect(TokenType.RPAREN)
        return Action(
            raw=f"send {target}",
            kind="send",
            target=target,
            variable=variable,
            params=params,
        )

    def _parse_verify_action(self, variable: Optional[str]) -> Action:
        self.advance()  # skip 'verify'
        target = self.advance().value
        params = {}
        if self.match(TokenType.LPAREN):
            params = self._parse_params()
            self.expect(TokenType.RPAREN)
        return Action(
            raw=f"verify {target}",
            kind="verify",
            target=target,
            variable=variable,
            params=params,
        )

    def _parse_generic_action(self, variable: Optional[str]) -> Action:
        """Handle dotted transitions (user.status -> active) or function calls."""
        name = self.advance().value

        # Dotted access: user.status -> active
        if self.match(TokenType.DOT):
            field_name = self.advance().value
            if self.match(TokenType.ARROW):
                new_value = self.advance().value
                return Action(
                    raw=f"{name}.{field_name} -> {new_value}",
                    kind="transition",
                    target=name,
                    variable=variable,
                    params={"field": field_name, "to": new_value},
                )
            # Just a dotted access (shouldn't be standalone, but handle it)
            return Action(
                raw=f"{name}.{field_name}",
                kind="access",
                target=name,
                variable=variable,
                params={"field": field_name},
            )

        # Function call: add_member(workspace, actor, invitation.role)
        if self.match(TokenType.LPAREN):
            params = self._parse_params()
            self.expect(TokenType.RPAREN)
            return Action(
                raw=f"{name}(...)",
                kind="call",
                target=name,
                variable=variable,
                params=params,
            )

        return Action(
            raw=name,
            kind="reference",
            target=name,
            variable=variable,
        )

    def _parse_params(self) -> dict[str, str]:
        """Parse key: value pairs or positional params inside parens."""
        params = {}
        self.skip_newlines()
        if self.at(TokenType.RPAREN):
            return params

        idx = 0
        while True:
            self.skip_newlines()
            if self.at(TokenType.RPAREN):
                break

            # Check for nested block: { key: value, ... }
            if self.at(TokenType.LBRACE):
                self.advance()
                self.skip_newlines()
                nested = self._parse_params()
                self.skip_newlines()
                self.expect(TokenType.RBRACE)
                for k, v in nested.items():
                    params[k] = v
                self.match(TokenType.COMMA)
                continue

            # Read key or positional value
            key_tok = self.advance()
            key = key_tok.value

            # Dotted key: input.email, user.password, invitation.role, etc.
            while self.match(TokenType.DOT):
                key += "." + self.advance().value

            if self.match(TokenType.COLON):
                self.skip_newlines()
                # Value can be dotted, a string, a number, or a block
                if self.at(TokenType.LBRACE):
                    self.advance()
                    self.skip_newlines()
                    nested = self._parse_params()
                    self.skip_newlines()
                    self.expect(TokenType.RBRACE)
                    # Store nested as sub-keys
                    for nk, nv in nested.items():
                        params[f"{key}.{nk}"] = nv
                else:
                    val = self.advance().value
                    while self.match(TokenType.DOT):
                        val += "." + self.advance().value
                    params[key] = val
            else:
                # Positional param
                params[str(idx)] = key
                idx += 1

            self.skip_newlines()
            if not self.match(TokenType.COMMA):
                break

        return params

    def parse_output_field(self) -> OutputField:
        name = self.expect(TokenType.IDENTIFIER).value
        # Expression: could be dotted (user.id) or a string literal
        if self.at(TokenType.STRING):
            expr = self.advance().value
        else:
            expr = self.advance().value
            while self.match(TokenType.DOT):
                expr += "." + self.advance().value
        return OutputField(name=name, expression=expr)

    def parse_error_def(self) -> ErrorDef:
        code_name = self.expect(TokenType.IDENTIFIER).value
        message = self.expect(TokenType.STRING).value
        http_status = int(self.expect(TokenType.NUMBER).value)
        return ErrorDef(code_name=code_name, message=message, http_status=http_status)

    # ========================================
    # Test blocks
    # ========================================

    def parse_test_block(self) -> TestBlock:
        self.expect(TokenType.TEST)
        name = self.expect(TokenType.STRING).value
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        self.skip_newlines()

        commands = []
        while not self.at(TokenType.RBRACE):
            self.skip_newlines()
            if self.at(TokenType.RBRACE):
                break
            if self.at(TokenType.DO):
                commands.append(self.parse_test_command())
            else:
                raise self.error("Expected 'do' in test block")

        self.expect(TokenType.RBRACE)
        self.skip_newlines()
        return TestBlock(name=name, commands=commands)

    def parse_test_command(self) -> TestCommand:
        self.expect(TokenType.DO)
        step_name = self.expect(TokenType.IDENTIFIER).value

        # Args in parens
        args = {}
        if self.match(TokenType.LPAREN):
            args = self._parse_params()
            self.expect(TokenType.RPAREN)

        # Optional: as authenticated(token)
        auth_token_var = None
        if self.match(TokenType.AS):
            self.expect(TokenType.AUTHENTICATED)
            self.expect(TokenType.LPAREN)
            auth_token_var = self.advance().value
            self.expect(TokenType.RPAREN)

        self.skip_newlines()

        # Expect/capture lines
        expectations = []
        capture = None

        while self.at(TokenType.EXPECT) or self.at(TokenType.CAPTURE):
            if self.match(TokenType.EXPECT):
                # Read the full path: "status 201", "output.user_id exists", "error email_taken"
                # First token is the kind (status, output, error)
                kind = self.advance().value

                # If followed by DOT, it's a dotted path like output.user_id
                if self.match(TokenType.DOT):
                    target = self.advance().value
                    while self.match(TokenType.DOT):
                        target += "." + self.advance().value
                else:
                    # Next token is the target (status code, error name, etc.)
                    target = self.advance().value

                value = None
                # Optional trailing value (e.g., "exists" after output.user_id)
                end_tokens = {TokenType.NEWLINE, TokenType.EOF, TokenType.EXPECT,
                              TokenType.CAPTURE, TokenType.DO, TokenType.RBRACE}
                if self.current().type not in end_tokens:
                    value = self.advance().value

                expectations.append(TestExpectation(kind=kind, target=target, value=value))
            elif self.match(TokenType.CAPTURE):
                capture = self.advance().value
            self.skip_newlines()

        return TestCommand(
            step_name=step_name,
            args=args,
            auth_token_var=auth_token_var,
            expectations=expectations,
            capture=capture,
        )
