# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""T2.1 - the skill loader: does ``skills/fall.md`` load, and does a bad file fail?

The point of load-time validation is that a typo in a markdown file must not be
discoverable only at 3am, mid-incident - so every check has a test that a broken
file is *rejected*, not just that a good one passes.

The tool registry is injected everywhere (``tools=FAKE_TOOLS``): these tests
never depend on ``qnet/tools/`` existing or on what is in it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from qnet.agent import phases

FALL_MD = Path(__file__).resolve().parent.parent / "skills" / "fall.md"


@dataclass
class FakeSpec:
    """Stands in for ``qnet.tools.ToolSpec`` - the engine only reads these two."""

    fn: object = None
    engine_only: bool = True


FAKE_TOOLS = {
    "notify_contacts": FakeSpec(),
    "call_emergency": FakeSpec(),
    "look_in_rooms": FakeSpec(engine_only=False),
}

# A minimal, valid skill used as the base for the "one thing is broken" cases.
GOOD = """---
name: toy
trigger: toy.event
urgency: safety
---

## Phases
```yaml
- id: check
  opening: "hello"
  goal: "find out"
  tools: []
  exits:
    ok:       "they are fine"
    escalate: "they are not"
  timer: { after_s: 30, goto: escalate }

- id: escalate
  goal: "get help"
  tools: []
  on_enter: [notify_contacts]
  exits:
    check: "they respond"
```

## Guidance
Be calm.
"""


def load(text: str):
    return phases.load_skill_text(text, source="toy.md", tools=FAKE_TOOLS)


def test_fall_md_loads() -> None:
    """The file on disk parses into the ladder it describes (§7 + T-contact-ack)."""
    skill = phases.load_skill(FALL_MD, tools=FAKE_TOOLS)

    assert skill.name == "fall-response"
    assert skill.trigger == "fall.detected"
    assert skill.urgency == "safety"
    assert skill.meta["emergency_number"] == "911"
    assert "IFRC 2020 First Aid Guidelines" in skill.meta["source"]

    assert skill.phase_ids == ("check", "escalate", "contact_engaged", "call_help")
    assert skill.first.id == "check"

    check = skill.phase("check")
    assert check.opening == "I saw you fall. Take a breath — are you okay?"
    assert check.tools == ()
    assert check.on_enter == ()
    assert set(check.exits) == {"ok", "escalate"}
    assert check.timer == phases.Timer(after_s=30.0, goto="escalate")

    escalate = skill.phase("escalate")
    assert escalate.on_enter == ("notify_contacts",)
    # 30 s (was 15): the escalation Telegram promises the contact a 30-second
    # reply window before the call (T-contact-ack).
    assert escalate.timer == phases.Timer(after_s=30.0, goto="call_help")
    assert set(escalate.exits) == {"check"}
    # The folded opening keeps DESIGN's wording on one line.
    assert escalate.opening == (
        "It's okay — I'm getting you help. Try to get comfortable, and don't strain to move."
    )

    # T-contact-ack: reached only by the engine, on a contact's ack. NOT one of
    # escalate's exits - the LLM must never be offered contact routing.
    engaged = skill.phase("contact_engaged")
    assert engaged.on_enter == ("notify_contacts",)  # the "I'll hold off" confirmation
    assert engaged.timer == phases.Timer(after_s=180.0, goto="call_help")  # the backstop
    assert set(engaged.exits) == {"check"}
    assert "{contact}" in engaged.opening  # the engine fills the real name in

    call_help = skill.phase("call_help")
    assert call_help.on_enter == ("call_emergency", "notify_contacts")
    assert call_help.timer is None  # a missing timer means no timer (§6)
    assert set(call_help.exits) == {"resolved"}

    # The guidance is carried through for the model (T3.3) - prose, not parsed.
    assert "One instruction at a time" in skill.guidance
    assert "never repeated by the comfort loop" in skill.guidance


def test_exit_naming_missing_phase_fails() -> None:
    """A typo'd exit must be rejected, not silently become a terminal state.

    ``escalat`` is neither a phase id nor a known terminal state; under §6's
    resolution rule alone it would quietly *end* the session instead of
    escalating it - the worst possible failure for this particular file.
    """
    broken = GOOD.replace("escalate: \"they are not\"", "escalat: \"they are not\"")
    with pytest.raises(phases.SkillError) as exc:
        load(broken)
    assert "escalat" in str(exc.value)
    assert "toy.md" in str(exc.value)

    # A timer pointing at a phase that does not exist is the same class of bug.
    with pytest.raises(phases.SkillError) as exc:
        load(GOOD.replace("goto: escalate", "goto: escalte"))
    assert "escalte" in str(exc.value)


def test_unknown_on_enter_action_fails() -> None:
    """Every ``on_enter`` name must exist in the registry that was handed in."""
    with pytest.raises(phases.SkillError) as exc:
        load(GOOD.replace("on_enter: [notify_contacts]", "on_enter: [notify_the_neighbours]"))
    assert "notify_the_neighbours" in str(exc.value)

    # ...and the same for a phase's tool allowlist.
    with pytest.raises(phases.SkillError) as exc:
        load(GOOD.replace("  tools: []\n  on_enter", "  tools: [teleport]\n  on_enter"))
    assert "teleport" in str(exc.value)

    # Validation is injectable, so a registry that has the action passes.
    assert load(GOOD).phase("escalate").on_enter == ("notify_contacts",)


def test_timer_shape_validated() -> None:
    """``{after_s: <positive number>, goto: <phase>}`` - anything else is an error."""
    for bad, expect in [
        ("timer: { after_s: 30 }", "goto"),
        ("timer: { goto: escalate }", "after_s"),
        ('timer: { after_s: "soon", goto: escalate }', "after_s"),
        ("timer: { after_s: -5, goto: escalate }", "positive"),
        ("timer: { after_s: 30, goto: escalate, unless: rain }", "unless"),
        ("timer: 30", "mapping"),
    ]:
        with pytest.raises(phases.SkillError) as exc:
            load(GOOD.replace("timer: { after_s: 30, goto: escalate }", bad))
        assert expect in str(exc.value), bad

    # A phase with no timer at all is legal - that is the one line of difference
    # between a fall skill and a query skill (§6).
    no_timer = load(GOOD.replace("  timer: { after_s: 30, goto: escalate }\n", ""))
    assert no_timer.phase("check").timer is None


def test_exit_resolution_rule() -> None:
    """§6's one rule: a phase name jumps, any other name ends the session."""
    skill = phases.load_skill(FALL_MD, tools=FAKE_TOOLS)

    # check's `escalate` is a jump; escalate's `check` is a jump back.
    assert skill.resolve_exit("escalate") == ("jump", "escalate")
    assert skill.resolve_exit("check") == ("jump", "check")
    assert skill.resolve_exit("call_help") == ("jump", "call_help")

    # ok / resolved / cancelled are terminal - which is why the skill needs no
    # explicit "closed" phase.
    assert skill.resolve_exit("ok") == ("end", "ok")
    assert skill.resolve_exit("resolved") == ("end", "resolved")
    assert skill.resolve_exit("cancelled") == ("end", "cancelled")

    # The rails: only the exits a phase declares, and no tool at all in fall.md.
    check = skill.phase("check")
    assert check.allows_exit("escalate") and check.allows_exit("ok")
    assert not check.allows_exit("resolved")
    assert not check.allows_tool("call_emergency", FAKE_TOOLS)  # not in tools: []


def test_engine_only_tools_are_never_the_models_to_call() -> None:
    """DESIGN §11: `notify_contacts` and `call_emergency` are the engine's alone."""
    skill = load(GOOD.replace("  tools: []\n  on_enter", "  tools: [notify_contacts]\n  on_enter"))
    escalate = skill.phase("escalate")
    # Allowlisted by the file, still refused: the registry flags it engine_only.
    assert not escalate.allows_tool("notify_contacts", FAKE_TOOLS)
    assert phases.Phase(id="x", tools=("look_in_rooms",)).allows_tool("look_in_rooms", FAKE_TOOLS)


def test_malformed_files_name_themselves() -> None:
    """Every error carries the file it came from - the loader is the only parser."""
    for text, expect in [
        ("no frontmatter here\n", "frontmatter"),
        ("---\nname: x\ntrigger: y\nurgency: safety\n---\n\nnothing\n", "## Phases"),
        ("---\nname: x\ntrigger: y\nurgency: safety\n---\n\n## Phases\nno block\n", "```yaml"),
        ("---\ntrigger: y\nurgency: safety\n---\n\n## Phases\n```yaml\n- id: a\n```\n", "name"),
        ("---\nname: x\ntrigger: y\nurgency: loud\n---\n\n## Phases\n```yaml\n- id: a\n```\n", "urgency"),
    ]:
        with pytest.raises(phases.SkillError) as exc:
            load(text)
        assert expect in str(exc.value)
        assert "toy.md" in str(exc.value)
