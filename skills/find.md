---
name: find-object
trigger: kind=query
urgency: routine           # routine never takes over the dashboard (§14)
---

## Phases
```yaml
- id: search
  goal: "Work out which room the object is in, then say so plainly."
  tools: [look_in_rooms]
  exits:
    found:     "at least one room reports seeing it"
    not_found: "no room reports seeing it"

- id: guide
  goal: "They are in the right room but can't see it. Describe where it is
         relative to something obvious nearby."
  tools: [look_in_rooms]
  exits:
    done: "they have found it, or there is nothing more useful to say"
```

**No timers, no `on_enter` actions — that's the whole difference from `fall.md`**
(DESIGN §13). A fall is system-initiated and urgent; finding something is
person-initiated and calm, so nothing here fires on a clock and nothing here
messages anybody.

**How "I still don't see it" reaches `guide`.** A follow-up is a *new* `ask`, so
something has to connect it to the search it follows. The rule is deliberately
dumb: the agent remembers the last find result for two minutes
(`find.last_find_window_s`). A new `ask` that names no object within that window
uses `guide`, with the remembered object and the room the person is speaking
from *now*. Any `ask` that names an object starts a fresh `search`.

**Which room answers.** The `ask` arrived on `qnet/<room>/ask`, so the answer
goes back on `qnet/<same room>/say` — the person is told where the object is in
the room they are standing in, not in the room the object turned up in.

## Guidance
Say where it is, plainly, in one sentence — the room first, then the landmark
the node named ("in the bedroom, on the nightstand").
**Name what was actually checked.** If a node never answered, say so in the same
breath rather than reporting a clean "not found": "I looked in the kitchen and
don't see them — I couldn't reach the bedroom." Silently reporting "not found"
when only half the house was checked is what makes people stop trusting a system.
Never claim to have looked somewhere that did not reply, and never invent a
location a node did not describe.
In `guide`, describe the position relative to something obvious nearby, in the
node's own words — "left of the lamp, just behind the book".
