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
# The responder brief is the one deliberately longer line in the system: a whole
# spoken timeline (§12), not a status sentence. Still capped - at ~16 tok/s
# (§10) this is a few seconds of speech, and the fall session's timers are
# engine-owned so nothing waits on it.
BRIEF_MAX_TOKENS = 180
# ...and the one request that needs longer than the 6 s client timeout: 180
# tokens at the measured 15.7-16.2 tok/s (§10) is ~11 s of decode, so a 6 s
# timeout would mean the brief *always* fell back to the engine's own wording.
# Nothing waits on it - the fall session's timers are engine-owned - and the
# comfort loop is paused for the duration by design (§12).
BRIEF_TIMEOUT_S = 20.0

CHANNEL_MARK = "<channel|>"  # Gemma 4's thinking-channel terminator
MAX_LINE_CHARS = 200         # a spoken line, not a paragraph
BRIEF_MAX_CHARS = 900        # ...except the brief, which is a whole timeline

# Per-kind caps for `word_line`. A kind that is not listed gets the one-sentence
# defaults, so adding a new kind never needs an entry here.
LINE_LIMITS: dict[str, tuple[int, int]] = {"brief": (BRIEF_MAX_TOKENS, BRIEF_MAX_CHARS)}
LINE_TIMEOUTS: dict[str, float] = {"brief": BRIEF_TIMEOUT_S}

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
    """One Gemma endpoint, three jobs: classify a reply, word a line, name an object.

    "Word a line" covers all three places the model speaks - the fall comfort
    update, the find answer (§13) and the responder brief (§12) - because they
    are the same request with a different prompt and a different cap. The model
    never chooses *what* is true in any of them; the engine hands it the facts.

    Every job is single-turn by construction (DESIGN §6: "small models are
    reliable single-turn, unreliable multi-turn") and every one is wrapped in
    the same *ask -> strip -> validate -> one terser retry -> None* recipe.

    Synchronous on purpose: the ``openai`` client's sync path is the
    well-trodden one, and the engine calls every method through
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

    def ask(self, prompt: str, temperature: float, max_tokens: int, timeout_s: float | None = None) -> str | None:
        """One completion, or ``None``. The only method that touches the network.

        ``extra_body`` is not optional garnish - see the module docstring: these
        are the field names the server actually reads.

        ``timeout_s`` overrides the client's default for this one request, and
        is only passed when a caller asks for it (the responder brief, which
        decodes a paragraph rather than a sentence). Every other request goes
        out exactly as it always did.
        """
        self.calls += 1
        extra: dict[str, Any] = {"timeout": timeout_s} if timeout_s else {}
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
                **extra,
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

    def word_line(self, kind: str, facts: Sequence[str], goal: str = "") -> str | None:
        """Turn known-true facts into one spoken line, or ``None``.

        The facts come from the engine (what tools actually did, what nodes
        actually replied, how long it has actually been) - the model's whole job
        is wording, never content. §6: "grounded in what tools actually
        returned, never filler".

        **Three kinds share this one method and one recipe** (T6.1, T6.2):
        ``comfort`` is the fall loop's status line, ``find`` is the answer to
        "where are my glasses", ``brief`` is the responder timeline. Only the
        prompt and the caps differ - a kind with no entry in ``LINE_LIMITS``
        gets the one-sentence defaults, so ``comfort``'s measured behaviour
        (T3.3) is untouched, byte for byte.

        ``goal`` is the skill file's own goal text, passed straight through
        where a skill has one (``skills/responder-brief.md``) - the same rule as
        ``_classify_prompt``: what to achieve is markdown, never Python.
        """
        facts = [f for f in (facts or []) if f]
        if not facts:
            return None
        max_tokens, max_chars = LINE_LIMITS.get(kind, (WORD_LINE_MAX_TOKENS, MAX_LINE_CHARS))
        timeout_s = LINE_TIMEOUTS.get(kind)

        line = _clean_line(
            self.ask(self._word_prompt(kind, facts, goal), 0.4, max_tokens, timeout_s),
            max_chars,
        )
        if line:
            return line
        log.info("llm %s line unusable - retrying once", kind)
        line = _clean_line(
            self.ask(self._retry_word_prompt(kind, facts), 0.4, max_tokens, timeout_s),
            max_chars,
        )
        if line is None:
            log.warning("llm %s line failed twice - engine words it instead", kind)
        return line

    def _word_prompt(self, kind: str, facts: Sequence[str], goal: str = "") -> str:
        """Facts in, one line out. Nothing may be added to the facts."""
        listed = "\n".join(f"- {fact}" for fact in facts)
        if kind == "brief":
            return (
                "You are a home safety system briefing a first responder who has just walked in and "
                "knows nothing about what happened. Speak to them, not to the person who fell.\n\n"
                f"{goal or _BRIEF_GOAL}\n\n"
                f"These are the only facts you have, in the order they happened:\n{listed}\n\n"
                "Speak the summary out loud. Rules:\n"
                "- One flowing spoken summary, not a list, not bullet points, not headings.\n"
                "- Use only the facts above, all of them, in that order. Never invent a fact, a name, "
                "a time, a diagnosis or a reassurance.\n"
                "- Keep the names straight: the person who fell and the contact who was messaged are "
                "different people. Attribute every quote to whoever the facts say said it.\n"
                "- Plain past tense, calm and factual. End with where things stand right now.\n"
                "- No quotes around the whole answer, no emoji. Under 120 words.\n"
                "Summary:"
            )
        if kind == "find":
            return (
                "You are a calm home assistant answering someone who asked where one of their "
                "belongings is. Each room of the house looked with its own camera and reported back.\n\n"
                f"These are the only facts you have:\n{listed}\n\n"
                "Write ONE short sentence they will hear out loud. Rules:\n"
                "- Say where it is, room first, then the landmark that was reported.\n"
                "- Name only the rooms above, and say plainly if a room could not be reached. "
                "Never claim to have looked somewhere that is not listed.\n"
                "- Use only those facts. Never invent a location, a room or an object.\n"
                "- No quotes, no emoji, no lists. Under 30 words.\n"
                "Sentence:"
            )
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

    def _retry_word_prompt(self, kind: str, facts: Sequence[str]) -> str:
        """The terser second ask - facts and one instruction, no persona."""
        joined = "; ".join(facts)
        if kind == "brief":
            return (
                f"Facts, in order: {joined}.\n"
                "Tell a first responder what happened, out loud, using only those facts. "
                "One flowing summary, no list, under 120 words."
            )
        if kind == "find":
            return (
                f"Facts: {joined}.\n"
                "Answer, in one short spoken sentence, where the object is - or which rooms were "
                "checked and which could not be reached. Use only those facts, under 25 words, no quotes."
            )
        return (
            f"Facts: {joined}.\n"
            "Write one short, calm sentence for a person lying on the floor, using only those facts. "
            "One sentence, under 25 words, no quotes."
        )

    # --- job 3: what are they looking for? -------------------------------

    def extract_object(self, text: str) -> str | None:
        """The thing to look for, out of a transcript, or ``None`` (T6.2, §13).

        The engine's plain-string heuristic handles "where are my glasses" and
        friends; this is only reached when that fails, and it is allowed to fail
        too - the engine then asks the person what to look for, which is a
        better answer than searching the house for a hallucination.

        Same closed-answer discipline as ``classify_reply``: one short noun
        phrase or the literal word ``none``, validated here, never trusted raw.
        """
        said = (text or "").strip()
        if not said:
            return None
        answer = self.ask(
            "Someone spoke to a home assistant that can look around the house for lost objects.\n"
            f'They said: "{said}"\n\n'
            "What object are they asking it to find? Answer with just the object, in one or two "
            'words, lower case, no article. If they did not name an object, answer exactly: none\n'
            "Object:",
            temperature=0.0,
            max_tokens=CLASSIFY_MAX_TOKENS,
        )
        return _clean_object(answer)


# Only used if `skills/responder-brief.md` could not be loaded - the engine
# passes that file's own `goal:` through, per DESIGN §12.
_BRIEF_GOAL = (
    "Give a clear, factual timeline: when the fall was detected, what the person said or did, "
    "what actions were taken and when, current status, and total elapsed time. "
    "One flowing summary, not a list."
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


def _clean_line(answer: str | None, max_chars: int = MAX_LINE_CHARS) -> str | None:
    """One spoken line: collapsed whitespace, unquoted, within the kind's cap."""
    if not answer:
        return None
    line = _WS_RE.sub(" ", answer).strip().strip('"').strip("'").strip()
    if not line or len(line) > max_chars:
        return None
    return line


# A model that answers the object question with a pronoun has told us nothing:
# "where are they" is exactly the follow-up §13 routes to `guide` by remembering
# the last object, not by searching for the word "them".
_PRONOUNS = frozenset(
    {"none", "it", "them", "they", "that", "this", "these", "those", "thing", "something", "anything", "one"}
)


def _clean_object(answer: str | None) -> str | None:
    """A short object phrase, or ``None`` - the same closed-answer discipline."""
    if not answer:
        return None
    word = _EDGE_RE.sub("", _WS_RE.sub(" ", answer).strip().lower())
    word = re.sub(r"^(my|the|a|an|our|his|her|their)\s+", "", word)
    if not word or len(word.split()) > 3 or len(word) > 40:
        return None
    return None if word in _PRONOUNS else word
