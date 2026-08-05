# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""GenieX client - Gemma 4 E2B on the IQ-9075 (DESIGN.md §10, T3.3).

``geniex serve`` is OpenAI-compatible, so this is the stock ``openai`` client
with a different ``base_url`` (``http://127.0.0.1:18181/v1``). **The prompt
templates live here and only here** - the engine never builds a string for the
model, it hands over a phase and a few facts.

Verified on-device constraints (DESIGN §10, ``setup/iq9-gemma-geniex/README.md``)
that this module must honour, every one of them the result of something that
broke on the real board:

* **Never send** ``response_format``, ``enable_json``, ``grammar`` or
  ``grammar_string``: on GenieX v0.3.18 they crash the server (systemd restarts
  it ~10 s later, which is not a hot path to build on). So there is no
  server-side constraint here at all - v1 is *prompt -> strip -> validate
  against the phase's closed option set -> one retry -> give up*.
* **SDK-native tool-calling does not work** (``tool_calls`` comes back null),
  so no ``tools=`` argument is ever passed.
* **Every request carries GenieX's field names, not OpenAI's:**
  ``enable_think: false`` (``think`` is silently ignored, and Gemma otherwise
  reasons at length before answering) and ``max_completion_tokens``
  (``max_tokens`` is silently ignored). ``nctx: 16384`` is the 16k context §10
  specifies. Sent on *every* call, via ``extra_body``.
* Belt-and-braces: strip everything up to the last ``<channel|>`` marker - a
  no-op when thinking is off, and the difference between an answer and a
  monologue if a future release ignores the flag.
* **Requests serialize** - one model, one queue on the device. Caps are small
  (a classification is one word) and the client-side timeout is 6 s.

**Nothing here ever raises.** Every failure - timeout, connection refused, a
model that will not answer with one of the words it was given - returns
``None``, and the engine falls back to its regex classifier / its own assembled
sentence. A brain that is having a bad day must never be able to stop a fall
session walking its rails (DESIGN §6: "degraded, not broken").
"""

from __future__ import annotations

import logging
import re
from typing import Any, Mapping, Sequence

log = logging.getLogger("qnet.agent.llm")

BASE_URL = "http://127.0.0.1:18181/v1"
MODEL = "google/gemma-4-E2B-it-qat-q4_0-gguf"
API_KEY = "geniex"          # the server does not check it; the SDK insists on one
NCTX = 16384                # DESIGN §10: 16k context, per request (T3.2 residual)
TIMEOUT_S = 6.0             # client-side; the engine's timers do not wait on us

# Caps are deliberately tiny: one word, or one sentence. They also bound how
# long a queued request can block the next one (requests serialize on-device).
CLASSIFY_MAX_TOKENS = 12
WORD_LINE_MAX_TOKENS = 80

CHANNEL_MARK = "<channel|>"  # Gemma 4's thinking-channel terminator
MAX_LINE_CHARS = 200         # a spoken line, not a paragraph

_WS_RE = re.compile(r"\s+")
_EDGE_RE = re.compile(r"^[\s\"'`*_.:,;!?()\[\]-]+|[\s\"'`*_.:,;()\[\]-]+$")


def strip_thinking(text: str) -> str:
    """Everything after the last ``<channel|>`` marker (DESIGN §10).

    With ``enable_think: false`` no marker is emitted and this is the identity
    function - which is exactly why it is safe to always apply.
    """
    return (text or "").rsplit(CHANNEL_MARK, 1)[-1].strip()


def options_for(phase: Any) -> tuple[str, ...]:
    """The closed set of decisions this phase allows - and nothing else.

    This mirrors ``engine.classify_reply``'s contract exactly, phase-shaped
    rather than fall-shaped, so a skill with different phase names still works:

    * a ``check``-shaped phase (offers both ``ok`` and ``escalate``) -> the
      model picks between them. It never gets a "wait" option: a phase whose
      whole job is deciding whether someone needs help must resolve, and
      ambiguity resolving toward help is the engine's rule, not the model's.
    * an ``escalate``-shaped phase (offers ``check``) -> ``check`` or ``wait``:
      did they respond coherently enough to go back and reassess?
    * anything else (``call_help``, whose only exit is the manual ``resolved``)
      -> **no options at all, so no request is made**. The regex classifier
      returns ``wait`` there and nothing else; "a responder has arrived" is not
      a claim a language model gets to make on the strength of a transcript.
    """
    exits = getattr(phase, "exits", {}) or {}
    if "ok" in exits and "escalate" in exits:
        return ("ok", "escalate")
    if "check" in exits:
        return ("check", "wait")
    return ()


class LlmClient:
    """One Gemma endpoint, two jobs: classify a reply, word a status line.

    Both jobs are single-turn by construction (DESIGN §6: "small models are
    reliable single-turn, unreliable multi-turn") and both are wrapped in the
    same *ask -> strip -> validate -> one terser retry -> None* recipe.

    Synchronous on purpose: the ``openai`` client's sync path is the
    well-trodden one, and the engine calls both methods through
    ``asyncio.to_thread`` so the event loop keeps its timers while the device
    thinks.
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        model: str = MODEL,
        timeout_s: float = TIMEOUT_S,
        api_key: str = API_KEY,
        client: Any = None,
    ) -> None:
        self.base_url = base_url or BASE_URL
        self.model = model
        self.timeout_s = float(timeout_s)
        self.calls = 0  # how many requests actually went out (the tests read it)
        if client is not None:
            self.client = client
        else:
            from openai import OpenAI  # imported here so --no-llm never needs it

            self.client = OpenAI(base_url=self.base_url, api_key=api_key, timeout=self.timeout_s, max_retries=0)

    # --- the one place a request is built --------------------------------

    def ask(self, prompt: str, temperature: float, max_tokens: int) -> str | None:
        """One completion, or ``None``. The only method that touches the network.

        ``extra_body`` is not optional garnish - see the module docstring: these
        are the field names the server actually reads.
        """
        self.calls += 1
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                extra_body={
                    "enable_think": False,             # GenieX's name; `think` is ignored
                    "max_completion_tokens": max_tokens,  # GenieX's name; `max_tokens` is ignored
                    "nctx": NCTX,
                },
            )
        except Exception as exc:  # noqa: BLE001 - timeouts, refused connections, 5xx: all the same to us
            log.warning("llm request failed (%s) - falling back", exc.__class__.__name__)
            return None
        try:
            content = response.choices[0].message.content or ""
        except (AttributeError, IndexError, TypeError):
            log.warning("llm returned no choices - falling back")
            return None
        return strip_thinking(content)

    # --- job 1: which exit does this reply take? -------------------------

    def classify_reply(self, phase: Any, session_context: Mapping[str, Any], heard_text: str) -> str | None:
        """One transcript -> one of the phase's legal decisions, or ``None``.

        The return value is a decision *word* from ``options_for(phase)``; the
        engine turns it into an ``Action``, which is what keeps the pain
        double-check (§3, §6) engine-owned rather than something the model can
        skip. ``None`` means "no usable answer" - the caller uses its regex.
        """
        options = options_for(phase)
        if not options or not (heard_text or "").strip():
            return None

        answer = self.ask(
            self._classify_prompt(phase, session_context, heard_text, options),
            temperature=0.0,
            max_tokens=CLASSIFY_MAX_TOKENS,
        )
        decision = _match(answer, options)
        if decision is not None:
            return decision

        # One retry, terser - the observed failure mode is a model that answered
        # the question in a sentence instead of a word, not one that disagreed.
        log.info("llm classification %r not in %s - retrying once", answer, list(options))
        answer = self.ask(
            self._retry_prompt(heard_text, options),
            temperature=0.0,
            max_tokens=CLASSIFY_MAX_TOKENS,
        )
        decision = _match(answer, options)
        if decision is None:
            log.warning("llm classification failed twice (%r) - engine falls back", answer)
        return decision

    def _classify_prompt(
        self,
        phase: Any,
        session_context: Mapping[str, Any],
        heard_text: str,
        options: Sequence[str],
    ) -> str:
        """Role line + the phase's goal + its exits + the transcript. That is all.

        Deliberately built from the *skill file's own words* - ``phase.goal`` and
        each exit's plain-English condition - so changing when a fall escalates
        is an edit to ``skills/fall.md``, never to this file (DESIGN §7).

        **Short on purpose, and measured that way** (5 replays x 9 replies each,
        live E2B, 2026-08-05; verify/T3.3.txt has the table). Two "obviously
        helpful" additions were tried and both made this model *worse*:

        * a closing "if you cannot tell, choose escalate" safety line: 41/45,
          against **44/45** without it - and it cost the accuracy on exactly the
          demo's headline reply, "I'm fine" (2/5 vs 5/5). The rule it states is
          real, but it belongs where it already is: ``engine.classify_reply``
          escalates on anything it cannot read, and it is what runs whenever
          this method returns ``None``.
        * a standing note that "ok" does not close the session: 25-26/30. Only
          the pain double-check's polarity note earns its place (24/25 against
          20/25 without it, because ``fall.md``'s escalate condition says "they
          say no" and a "no" to *"any pain?"* means the opposite).

        A 2B model reads the last thing you tell it hardest. Every sentence in
        here has to pay for itself.
        """
        exits: Mapping[str, str] = getattr(phase, "exits", {}) or {}
        lines = [
            "You are the voice of a home safety assistant. Someone in the house may have fallen.",
            "Read what the person just said and decide what should happen next.",
            "",
            f"Your goal right now: {getattr(phase, 'goal', '') or 'work out what this reply means.'}",
        ]
        asked = session_context.get("asked")
        if asked:
            lines.append(f'You just asked them: "{asked}"')
        note = session_context.get("note")
        if note:
            # One sentence of engine truth the model cannot read off the skill
            # file - see `engine.llm_context`. Used sparingly and measured:
            # every *extra* sentence tried here made this model worse (below).
            lines.append(note)
        if session_context.get("contacts_notified"):
            lines.append("Their emergency contact has already been messaged.")
        lines += ["", "Choose one:"]
        for name in options:
            lines.append(f"- {name}: {exits.get(name) or _FALLBACK_CONDITION.get(name, name)}")
        lines += [
            "",
            f'The person said: "{(heard_text or "").strip()}"',
            "",
            f"Answer with exactly one word from: {', '.join(options)}",
        ]
        return "\n".join(lines)

    def _retry_prompt(self, heard_text: str, options: Sequence[str]) -> str:
        """The terser second ask: no context, no room to write a sentence."""
        return (
            f'Someone who may have fallen said: "{(heard_text or "").strip()}"\n'
            f"Reply with one word and nothing else: {' or '.join(options)}"
        )

    # --- job 2: word one short line from facts we already know -----------

    def word_line(self, kind: str, facts: Sequence[str]) -> str | None:
        """Turn known-true facts into one spoken sentence, or ``None``.

        The facts come from the session log (what tools actually did, how long
        it has actually been) - the model's whole job is wording, never
        content. §6: "grounded in what tools actually returned, never filler".
        """
        facts = [f for f in (facts or []) if f]
        if not facts:
            return None

        line = _clean_line(self.ask(self._word_prompt(kind, facts), temperature=0.4, max_tokens=WORD_LINE_MAX_TOKENS))
        if line:
            return line
        log.info("llm %s line unusable - retrying once", kind)
        line = _clean_line(
            self.ask(
                f"Facts: {'; '.join(facts)}.\n"
                "Write one short, calm sentence for a person lying on the floor, using only those facts. "
                "One sentence, under 25 words, no quotes.",
                temperature=0.4,
                max_tokens=WORD_LINE_MAX_TOKENS,
            )
        )
        if line is None:
            log.warning("llm %s line failed twice - engine words it instead", kind)
        return line

    def _word_prompt(self, kind: str, facts: Sequence[str]) -> str:
        """Facts in, one sentence out. Nothing may be added to the facts."""
        listed = "\n".join(f"- {fact}" for fact in facts)
        return (
            "You are a calm home assistant staying with an older person who has fallen and is "
            "waiting for help. Speak to them directly, warmly, and briefly.\n\n"
            f"These are the only facts you know ({kind} update):\n{listed}\n\n"
            "Write ONE short sentence they will hear out loud. Rules:\n"
            "- Let them know you are still there with them.\n"
            "- Include every fact above, the elapsed time included, and use only those facts. "
            "Never invent a fact, a name, a time or a promise.\n"
            "- Do not tell them to move, stand up, or get comfortable.\n"
            "- No quotes, no emoji, no lists. Under 30 words.\n"
            "Sentence:"
        )


# Only used if a skill file leaves an exit's condition blank - the loader
# already refuses that, so this is belt-and-braces for hand-built phases.
_FALLBACK_CONDITION = {
    "ok": "they clearly say they are fine and deny any pain",
    "escalate": "they ask for help, report pain, or do not really answer",
    "check": "they respond coherently, so go back and reassess how they are",
    "wait": "they said nothing meaningful; keep listening",
}


def _match(answer: str | None, options: Sequence[str]) -> str | None:
    """Exact match against the closed set, after lowercasing and trimming.

    "Exact" is the point: no substring search, no "starts with", no fuzzy
    nearest-option. A model that writes a paragraph gets a retry, not a guess -
    the phase allowlist would refuse an invented exit anyway (§6), and a
    misparsed one is worse than no answer.
    """
    if not answer:
        return None
    word = _EDGE_RE.sub("", _WS_RE.sub(" ", answer).strip().lower())
    return word if word in options else None


def _clean_line(answer: str | None) -> str | None:
    """One spoken line: collapsed whitespace, unquoted, ``<= 200`` chars."""
    if not answer:
        return None
    line = _WS_RE.sub(" ", answer).strip().strip('"').strip("'").strip()
    if not line or len(line) > MAX_LINE_CHARS:
        return None
    return line
