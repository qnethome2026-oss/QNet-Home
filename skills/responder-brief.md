---
name: responder-brief
trigger: kind=responder_brief
mode: interrupt            # no session, no phases, no urgency - one call, speak, done
---

## Brief
```yaml
goal: "Give a clear, factual timeline: when the fall was detected, what
       the person said or did, what actions were taken and when, current
       status, and total elapsed time. One flowing summary, not a list."
reads: latest fall-response file    # via get_session_summary (§11)
```

**This file carries content, not rails.** DESIGN §12: the responder brief is an
engine-level *interrupt*, not a session — pause the comfort loop → read the
room's latest fall file → one LLM call to word the timeline → speak it → resume.
There are no phases to walk, so there is no `## Phases` block and no `urgency`:
`qnet/agent/phases.py`'s `load_interrupt_skill` reads this shape, and the phase
loader would (correctly) refuse it.

**Scoped deliberately to fall response.** It reads only sessions where
`skill: fall-response`; a find session is invisible to it and vice versa.

**Every fact it reports is already on disk** as the fall session runs (§6). This
is a formatter over data that exists — no new sensing, no new model. The file is
read *live*: ask thirty seconds into an escalation and the summary is what has
been appended so far, with no "finalize the log" step to wait for.

If there is no fall-response file for the room it says so plainly, and stops:
*"No fall has been recorded in this room."*

**One honest limitation:** there is no identity check. Anyone who says the phrase
gets the brief, including anything the person said (e.g. reported pain). Fine for
a demo; a real deployment needs real access control.

## Guidance
Speak to a first responder who has just walked in and knows nothing: facts,
times and current status, in the order they happened, as one flowing spoken
summary rather than a read-out list.
Use only what the log actually holds. Never soften it, never add a diagnosis, an
instruction, or a reassurance — and never invent a fact, a name or a time.
Quote what the person said in their own words where the log has it, and say
plainly when they did not answer.
End with where things stand right now and how long it has been.
