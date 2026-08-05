# QNet Home — the MQTT wire contract (frozen, T0.1)

*Source of truth: `docs/DESIGN.md` §4, with the session log lines from §6. This
file is the machine-referenced copy. **Contracts are sacred:** any change to a
topic or a payload updates this file **and** `contracts/fixtures/*.json` in the
same commit, or it didn't happen (IMPLEMENTATION.md, standing rules).*

MQTT is the only coupling between devices. Broker: Mosquitto on the IQ-9075.
Clients: `paho-mqtt` on the nodes and the agent. The dashboard and
`dev/sim.html` subscribe over Mosquitto's WebSocket listener on `:9001` — there
is no backend API.

`<room>` is the room id from `config/house.yaml`'s `rooms:` map (`kitchen`,
`bedroom`, …), and it is also the node's identity: the node's `config/node.yaml`
carries `room`, and every message it publishes goes out under that room.

## Topics

| Topic | Direction | QoS | Purpose |
|---|---|---|---|
| `qnet/<room>/event` | node → agent | 1 | Something happened (a fall) |
| `qnet/<room>/ask` | node → agent | 1 | A query — find ("hey home…") or a first-responder brief request |
| `qnet/<room>/say` | agent → node | 1 | Speak this |
| `qnet/<room>/heard` | node → agent | 1 | What was said |
| `qnet/look` | agent → **all** nodes | 1 | Look for X right now (broadcast) |
| `qnet/<room>/looked` | node → agent | 1 | What that node's VLM saw |
| `qnet/<room>/status` | node → all | 0 | Health |
| `qnet/session/<id>` | agent → dashboard | 1 | Session updates |

**Why these QoS levels.** Everything that carries a decision or a person's words
is QoS 1 — losing a fall event, a spoken line, a transcript, a search request or
a search result changes what the system does or fails to say. `status` is a
repeating heartbeat, so QoS 0 is correct: the next one is along shortly and a
dropped beat costs nothing. Session updates are QoS 1 because the dashboard and
the JSONL file are two destinations for one stream (§6) and the dashboard must
not silently miss a phase transition or a `SIMULATED` emergency line.

QoS 1 is at-least-once, so a subscriber may see a duplicate. Every message that
matters carries an id (`id` on `event`/`ask`, `qid` on `look`/`looked`), which
is what de-duplication uses if it ever proves necessary.

## Payloads

One valid sample of each lives in `contracts/fixtures/` — three consumers
(`tests/test_contracts.py`, `dev/inject.py`, `dev/sim.html`), one source of
truth. Types below are the required fields; the fixtures are the shapes.

### `qnet/<room>/event` — `contracts/fixtures/event_fall.json`

```json
{ "id": "01JQ...", "ts": 1785790153.4, "room": "kitchen",
  "kind": "fall.detected", "conf": 0.87,
  "meta": { "cls": "Fallen", "frames": "5/8" } }
```

| Field | Type | Notes |
|---|---|---|
| `id` | string | Event id (ULID) |
| `ts` | number | Unix epoch seconds, fractional |
| `room` | string | Must match the room in the topic |
| `kind` | string | `fall.detected` is the only kind in v1 |
| `conf` | number | Model confidence, 0.0–1.0; see `vision.conf_floor` |
| `meta` | object | Detector detail — `cls` (class name), `frames` (the N-of-M that fired) |

### `qnet/<room>/ask` — `contracts/fixtures/ask_query.json`, `ask_responder_brief.json`

```json
{ "id": "01JR...", "ts": 1785790212.7, "room": "kitchen",
  "text": "where are my glasses", "kind": "query" }
```

| Field | Type | Notes |
|---|---|---|
| `id` | string | Ask id (ULID) |
| `ts` | number | Unix epoch seconds, fractional |
| `room` | string | Must match the room in the topic — this is how the answer finds its way home |
| `text` | string | The transcript with the wake phrase stripped |
| `kind` | string | `query` \| `responder_brief` |

`kind` is `responder_brief` when the phrase "I'm the first responder…" matches
(§12) — `text` is then **empty**: the request needs no free text, just the room.
The responder phrase is checked before the wake phrase, in any state.

### `qnet/<room>/say` — `contracts/fixtures/say.json`

```json
{ "text": "I saw you fall. Are you okay?", "prio": "safety" }
```

| Field | Type | Notes |
|---|---|---|
| `text` | string | The line to speak |
| `prio` | string | `safety` \| `comfort` \| `routine` |

`routine` was added in **T6.2**, for the lines that belong to neither the fall
ladder (`safety`) nor its comfort loop (`comfort`): a find answer (§13), the
"what should I look for?" question, and a responder brief asked in a room with no
live fall session (§12). A brief asked *during* an escalation is `safety`, like
everything else that speaks over a live fall. Nothing consumes `prio` as an enum
today — the node adapter and the dashboard both pass it through — so this is an
addition, not a change: `safety` and `comfort` mean exactly what they meant.

Room identity comes for free: the `ask` arrived on `qnet/<room>/ask`, so the
answer goes back on `qnet/<same room>/say`. No person tracking, no speaker
localisation, no cross-room correlation.

### `qnet/<room>/heard` — `contracts/fixtures/heard.json`

```json
{ "text": "i'm fine", "silence": false }
```

| Field | Type | Notes |
|---|---|---|
| `text` | string | The transcript; empty string when `silence` is true |
| `silence` | boolean | True when the listen window timed out with nothing said |

### `qnet/look` — `contracts/fixtures/look.json`

```json
{ "qid": "q7", "object": "glasses", "mode": "find", "room": null }
```

| Field | Type | Notes |
|---|---|---|
| `qid` | string | Correlates the broadcast with the `looked` replies |
| `object` | string | What to look for |
| `mode` | string | `find` \| `guide` |
| `room` | string \| null | `null` broadcasts to every node; guide mode targets one room |

Broadcast on a single unqualified topic — every node subscribes. Replies come
back per-room on `looked`; the agent waits up to the configured timeout
(`find.look_timeout_s`, default 8 s — §13's ceiling, not its goal) and answers
with whatever arrived, naming what it actually checked. It returns as soon as
every room in `house.yaml`'s `rooms:` map has answered, so the timeout is only
ever paid for a room that is actually silent. A `looked` whose `qid` is not the
one just broadcast is ignored: the reply topics are shared, and a late answer to
the previous question must never be read as an answer to this one.

### `qnet/<room>/looked` — `contracts/fixtures/looked.json`

```json
{ "qid": "q7", "room": "kitchen", "found": true,
  "answer": "on the counter next to the kettle" }
```

| Field | Type | Notes |
|---|---|---|
| `qid` | string | Echoes the `look` that asked |
| `room` | string | Which node answered |
| `found` | boolean | Whether this node's VLM saw the object |
| `answer` | string | One sentence of location, relative to something obvious nearby |

Only text crosses the wire: each node runs its own VLM on its own frame and
never sends the frame.

### `qnet/<room>/status` — health

Heartbeat published by each node, starting at boot — this is how the dashboard
learns which rooms exist, with no registration protocol. DESIGN §4 lists the
topic but pins no payload, so **the shape is not frozen by T0.1**: it is settled
in T4.2, when `node/vision.py` starts emitting it. There is deliberately no
fixture for it.

### `qnet/session/<id>` — `contracts/fixtures/session.json`

```json
{ "id": "01JQ...", "room": "kitchen", "skill": "fall-response",
  "urgency": "safety", "phase": "escalate", "state": "active", "log": [ ] }
```

| Field | Type | Notes |
|---|---|---|
| `id` | string | Session id; also the last segment of the topic |
| `room` | string | Where the session is running |
| `skill` | string | `fall-response` \| `find-object` |
| `urgency` | string | `safety` \| `routine` — `safety` takes over the dashboard |
| `phase` | string | Current phase id from the skill file |
| `state` | string | `active` \| `closed` \| `cancelled` |
| `log` | array | The session's log lines, in order (see below) |

**A "session" is one skill run, trigger to exit.** A fall is a session; a
question is a session. A session ends one of three ways: the agent takes a
terminal exit (`closed`), the cancel matcher fires (`cancelled`), or a human
resolves it from the dashboard. The responder brief is **not** a session — it is
an engine-level interrupt (§12), so it never appears here.

**Log lines (DESIGN §6).** Every line is appended to
`data/sessions/<room>__<skill>__<started_at ISO8601>.jsonl` *and* published here
the instant it happens — one stream, two destinations, not two mechanisms.
Every line carries `ts` and `event`; the rest depends on `event`:

| `event` | Additional fields |
|---|---|
| `detected` | `kind`, `conf` |
| `say` | `text` |
| `heard` | `text`, `silence` |
| `phase` | `from`, `to` |
| `tool` | `tool`, `result` |
| `refusal` | `tool`, `phase` |
| `brief` | `ask_id`, `spoken` (+ optional `text`) — **frozen in T6.1**, see below |

### The `brief` log line — frozen (T6.1)

DESIGN §12 has the responder brief append one `brief` line to the file it
summarised. §6 gave no shape for it, so T0.1 left it unfrozen; **T6.1 settles
it**:

```json
{ "ts": 1785790268.4, "event": "brief", "ask_id": "01JRC4G7XPZ5M1NAKQ8VT3WEHJ",
  "spoken": true, "text": "Here's what happened. A fall was detected in the kitchen..." }
```

| Field | Type | Notes |
|---|---|---|
| `ask_id` | string \| null | The `id` of the `ask` that requested the brief — the only link back, since the brief is not a session |
| `spoken` | boolean | True when the summary was actually published to `qnet/<room>/say` |
| `text` | string | Optional: the summary as spoken. Present whenever there was one; the dashboard renders it |

**Exactly one line per brief, and only into a file that already existed.** The
brief is an interrupt, not a session (§12): it never appears on
`qnet/session/<id>` as a session of its own, and it appends nothing to a room
with no fall on file — that case is spoken (*"No fall has been recorded in this
room."*) and nothing more. The read itself (`get_session_summary`) deliberately
logs no `tool` line: §12 allows the interrupt one line in the file it summarised,
and this is it. If the summarised session is still live in the agent, the same
line also goes out on `qnet/session/<id>`, like every other log line — one
stream, two destinations.
