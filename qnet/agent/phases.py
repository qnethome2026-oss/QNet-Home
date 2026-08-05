# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""The skill loader - markdown in, rails out (T2.1; DESIGN.md §6, §7).

A skill file is one markdown document with three parts, and this module is the
only thing that knows that:

    ---                     YAML frontmatter: name, trigger, urgency, source...
    ---
    ## Phases               one ```yaml fenced block: the phase list
    ## Guidance             prose, handed to the model as-is (T3.3)

Everything between the phase block and ``## Guidance`` is commentary for the
human editing the file; the loader ignores it, which is why DESIGN §7's file can
be copied in verbatim.

**Validation is load-time and loud.** A skill file is data, but it is data that
decides whether a caregiver gets called - so a typo must fail when the agent
starts, not silently do the wrong thing at 3am mid-incident:

* every ``timer`` is ``{after_s: <positive number>, goto: <an existing phase>}``
* every exit name either matches a phase id (a jump) or is a declared terminal
  state - see ``resolve_exit`` and the note on ``TERMINAL_EXITS`` below
* every ``on_enter`` action exists in the tool registry (injectable, so tests
  pass a fake one and the engine passes ``qnet.tools.TOOLS``)
* every name in a phase's ``tools:`` allowlist exists in that same registry

**Exit resolution, one rule (§6):** an exit whose name matches a phase id jumps
to that phase; any other name ends the session with that label as its final
state. That rule alone makes every name legal, which would make a typo
(``escalat:``) a silent session close instead of an escalation - the single most
dangerous failure this file can prevent. So the loader also keeps a vocabulary
of terminal states (``TERMINAL_EXITS``, extensible per-skill via a
``terminal_exits:`` frontmatter list). A name that is neither a phase nor a
known terminal state is a load error. The runtime rule is unchanged.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

log = logging.getLogger("qnet.agent.phases")

# The terminal states DESIGN uses by name: §6 ("ok, found, not_found, done and
# resolved are terminal") plus the two the engine itself can end a session with.
TERMINAL_EXITS = frozenset({"ok", "found", "not_found", "done", "resolved", "closed", "cancelled"})

# "resolve lazily" - the default registry is fetched at validation time, so
# importing this module never depends on qnet.tools being finished.
AUTO: Any = object()

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(?P<meta>.*?)\r?\n---[ \t]*\r?\n(?P<body>.*)\Z", re.DOTALL)
_SECTION_RE = re.compile(r"^##[ \t]+(?P<title>.+?)[ \t]*$", re.MULTILINE)
_YAML_FENCE_RE = re.compile(r"^```[ \t]*yaml[ \t]*\r?\n(?P<yaml>.*?)^```", re.DOTALL | re.MULTILINE)


class SkillError(ValueError):
    """A skill file that cannot be trusted to run. Always names the file."""


@dataclass(frozen=True)
class Timer:
    """The engine's timer for a phase: fire after ``after_s``, go to ``goto`` (§6).

    A missing ``timer`` means no timer - the one line of difference between a
    fall skill and a query skill.
    """

    after_s: float
    goto: str


@dataclass(frozen=True)
class Phase:
    """One phase: what to say first, what to achieve, what may be called, how to leave."""

    id: str
    goal: str = ""
    opening: str = ""
    tools: tuple[str, ...] = ()
    on_enter: tuple[str, ...] = ()
    exits: Mapping[str, str] = field(default_factory=dict)
    timer: Timer | None = None

    def allows_tool(self, name: str, registry: Mapping[str, Any] | None = None) -> bool:
        """Is this tool inside the phase's allowlist, and callable by the model?

        Two gates, both from DESIGN §11: the phase's own ``tools:`` list, and
        the registry's ``engine_only`` flag - ``notify_contacts`` and
        ``call_emergency`` are the engine's, never the model's, whatever a
        skill file says.
        """
        if name not in self.tools:
            return False
        spec = (registry or {}).get(name)
        return not (spec is not None and getattr(spec, "engine_only", False))

    def allows_exit(self, name: str) -> bool:
        """Only the exits the phase declares. Anything else is a refusal."""
        return name in self.exits


@dataclass(frozen=True)
class Skill:
    """A loaded, validated skill file."""

    name: str
    trigger: str
    urgency: str
    phases: tuple[Phase, ...]
    guidance: str = ""
    meta: Mapping[str, Any] = field(default_factory=dict)
    terminal_exits: frozenset[str] = TERMINAL_EXITS
    source_path: str = "<memory>"

    @property
    def first(self) -> Phase:
        """The phase a session starts in - the first one in the file."""
        return self.phases[0]

    @property
    def phase_ids(self) -> tuple[str, ...]:
        return tuple(p.id for p in self.phases)

    def phase(self, phase_id: str) -> Phase:
        """Look one phase up by id."""
        for phase in self.phases:
            if phase.id == phase_id:
                return phase
        raise SkillError(f"{self.source_path}: no phase {phase_id!r} (have: {', '.join(self.phase_ids)})")

    def resolve_exit(self, name: str) -> tuple[str, str]:
        """DESIGN §6's one rule, as a pair: ``("jump", phase_id)`` or ``("end", label)``.

        An exit whose name matches a phase id jumps to that phase; any other
        name ends the session with that label as its final state. This is why
        the skills need no explicit "closed" phase.
        """
        if name in self.phase_ids:
            return "jump", name
        return "end", name


# --- parsing -------------------------------------------------------------


def _sections(body: str) -> dict[str, str]:
    """Split the markdown body into ``## Heading`` -> text, lowercased keys."""
    out: dict[str, str] = {}
    marks = list(_SECTION_RE.finditer(body))
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(body)
        out[mark.group("title").strip().lower()] = body[mark.end() : end]
    return out


def parse_skill(text: str, source: str = "<memory>") -> tuple[dict, list, str]:
    """Frontmatter, raw phase list and guidance prose - no validation yet."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise SkillError(f"{source}: no YAML frontmatter - the file must start with a '---' line")
    try:
        meta = yaml.safe_load(match.group("meta")) or {}
    except yaml.YAMLError as exc:
        raise SkillError(f"{source}: frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(meta, dict):
        raise SkillError(f"{source}: frontmatter must be a mapping, got {type(meta).__name__}")

    sections = _sections(match.group("body"))
    if "phases" not in sections:
        raise SkillError(f"{source}: no '## Phases' section")
    fence = _YAML_FENCE_RE.search(sections["phases"])
    if not fence:
        raise SkillError(f"{source}: '## Phases' has no ```yaml block")
    try:
        raw_phases = yaml.safe_load(fence.group("yaml"))
    except yaml.YAMLError as exc:
        raise SkillError(f"{source}: the phases block is not valid YAML: {exc}") from exc
    if not isinstance(raw_phases, list) or not raw_phases:
        raise SkillError(f"{source}: the phases block must be a non-empty YAML list")

    return meta, raw_phases, sections.get("guidance", "").strip()


def _build_timer(source: str, phase_id: str, raw: Any) -> Timer | None:
    """``{after_s: <positive number>, goto: <phase id>}``, or nothing at all (§6)."""
    if raw is None:
        return None
    where = f"{source}: phase {phase_id!r}: timer"
    if not isinstance(raw, dict):
        raise SkillError(f"{where} must be a mapping like {{after_s: 30, goto: escalate}}, got {raw!r}")
    unknown = set(raw) - {"after_s", "goto"}
    if unknown:
        raise SkillError(f"{where} has unknown key(s) {sorted(unknown)} - only after_s and goto exist")
    if "after_s" not in raw or "goto" not in raw:
        raise SkillError(f"{where} needs both after_s and goto, got {sorted(raw)}")
    after_s = raw["after_s"]
    if isinstance(after_s, bool) or not isinstance(after_s, (int, float)):
        raise SkillError(f"{where}: after_s must be a number of seconds, got {after_s!r}")
    if after_s <= 0:
        raise SkillError(f"{where}: after_s must be positive, got {after_s!r}")
    if not isinstance(raw["goto"], str) or not raw["goto"]:
        raise SkillError(f"{where}: goto must name a phase, got {raw['goto']!r}")
    return Timer(after_s=float(after_s), goto=raw["goto"])


def _build_phase(source: str, raw: Any) -> Phase:
    """One entry of the phase list, shape-checked."""
    if not isinstance(raw, dict):
        raise SkillError(f"{source}: every phase must be a mapping, got {raw!r}")
    phase_id = raw.get("id")
    if not isinstance(phase_id, str) or not phase_id:
        raise SkillError(f"{source}: every phase needs a string id, got {phase_id!r}")

    def _names(key: str) -> tuple[str, ...]:
        value = raw.get(key) or []
        if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
            raise SkillError(f"{source}: phase {phase_id!r}: {key} must be a list of names, got {value!r}")
        return tuple(value)

    exits = raw.get("exits") or {}
    if not isinstance(exits, dict):
        raise SkillError(f"{source}: phase {phase_id!r}: exits must be a mapping of name -> when, got {exits!r}")
    for name, when in exits.items():
        if not isinstance(name, str) or not name:
            raise SkillError(f"{source}: phase {phase_id!r}: exit names must be strings, got {name!r}")
        if not isinstance(when, str) or not when.strip():
            raise SkillError(f"{source}: phase {phase_id!r}: exit {name!r} needs a description of when to take it")

    return Phase(
        id=phase_id,
        goal=str(raw.get("goal") or ""),
        opening=str(raw.get("opening") or ""),
        tools=_names("tools"),
        on_enter=_names("on_enter"),
        exits=dict(exits),
        timer=_build_timer(source, phase_id, raw.get("timer")),
    )


# --- validation ----------------------------------------------------------


def _registry(tools: Mapping[str, Any] | None | Any) -> Mapping[str, Any] | None:
    """The tool registry to validate against, resolved as late as possible.

    ``AUTO`` (the default) means "use ``qnet.tools.TOOLS`` if it exists yet" -
    and if it does not, skip tool validation with a warning rather than
    refusing to start, so the engine and its tests are not held hostage by
    another lane's task. An explicit mapping is always validated against.
    """
    if tools is not AUTO:
        return tools
    try:
        from qnet.tools import TOOLS
    except Exception:  # noqa: BLE001 - any import failure means "not landed yet"
        log.warning("qnet.tools has no TOOLS registry yet - skipping on_enter/tool validation")
        return None
    return TOOLS


def validate(skill: Skill, tools: Mapping[str, Any] | None | Any = AUTO) -> Skill:
    """Every check that must pass before a skill file is allowed to run."""
    source = skill.source_path
    ids = skill.phase_ids
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise SkillError(f"{source}: duplicate phase id(s) {duplicates}")

    known_exits = set(ids) | set(skill.terminal_exits)
    for phase in skill.phases:
        if phase.timer and phase.timer.goto not in ids:
            raise SkillError(
                f"{source}: phase {phase.id!r}: timer goto {phase.timer.goto!r} is not a phase "
                f"(have: {', '.join(ids)})"
            )
        for name in phase.exits:
            if name not in known_exits:
                raise SkillError(
                    f"{source}: phase {phase.id!r}: exit {name!r} names neither a phase "
                    f"({', '.join(ids)}) nor a terminal state ({', '.join(sorted(skill.terminal_exits))}) - "
                    f"a typo here would silently end the session instead of jumping"
                )

    registry = _registry(tools)
    if registry is None:
        return skill
    for phase in skill.phases:
        for action in phase.on_enter:
            if action not in registry:
                raise SkillError(
                    f"{source}: phase {phase.id!r}: on_enter action {action!r} is not a registered tool "
                    f"(have: {', '.join(sorted(registry)) or 'none'})"
                )
        for name in phase.tools:
            if name not in registry:
                raise SkillError(
                    f"{source}: phase {phase.id!r}: tool {name!r} is not a registered tool "
                    f"(have: {', '.join(sorted(registry)) or 'none'})"
                )
    return skill


# --- the front door ------------------------------------------------------


def load_skill_text(
    text: str,
    source: str = "<memory>",
    tools: Mapping[str, Any] | None | Any = AUTO,
) -> Skill:
    """Parse and validate a skill file held in memory (the tests' entry point)."""
    meta, raw_phases, guidance = parse_skill(text, source)
    for key in ("name", "trigger", "urgency"):
        if not meta.get(key):
            raise SkillError(f"{source}: frontmatter needs a {key!r}")
    if meta["urgency"] not in {"safety", "routine"}:
        raise SkillError(f"{source}: urgency must be 'safety' or 'routine', got {meta['urgency']!r}")

    extra_terminals = meta.get("terminal_exits") or []
    if not isinstance(extra_terminals, list) or any(not isinstance(t, str) for t in extra_terminals):
        raise SkillError(f"{source}: terminal_exits must be a list of names, got {extra_terminals!r}")

    skill = Skill(
        name=str(meta["name"]),
        trigger=str(meta["trigger"]),
        urgency=str(meta["urgency"]),
        phases=tuple(_build_phase(source, raw) for raw in raw_phases),
        guidance=guidance,
        meta=meta,
        terminal_exits=TERMINAL_EXITS | frozenset(extra_terminals),
        source_path=source,
    )
    return validate(skill, tools)


def load_skill(path: str | Path, tools: Mapping[str, Any] | None | Any = AUTO) -> Skill:
    """Load ``skills/<name>.md`` from disk. Raises ``SkillError`` with the path in it."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillError(f"{path}: cannot read skill file: {exc}") from exc
    return load_skill_text(text, source=str(path), tools=tools)
