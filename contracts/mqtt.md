# QNet Home MQTT wire contract

This file is the source of truth for communication between room nodes, the
IQ-9075 agent, and the dashboard. Any topic or payload change must update this
file and the matching `contracts/fixtures/*.json` file in the same commit.

## Transport rules

- Broker: IQ-9075, MQTT 3.1.1 on TCP port 1883.
- Encoding: UTF-8 JSON object for every application message.
- QoS: 1 for every application topic. Consumers must tolerate duplicates.
- Retain: false except the latest node health message on `status`.
- Topic room names and payload `room` values use the configured stable room id.
- Timestamps use Unix epoch seconds in the numeric `ts` field.
- IDs are opaque non-empty strings. UUID and ULID values are both valid.
- Audio, images, and video never appear in MQTT payloads.

## Topics

| Topic | Direction | QoS | Retain | Purpose |
|---|---|---:|---:|---|
| `qnet/<room>/event` | node → agent | 1 | no | A semantic room event such as a detected fall |
| `qnet/<room>/ask` | node → agent | 1 | no | A rolling idle transcript for IQ9 activation/intent routing, or a responder-brief request |
| `qnet/<room>/say` | agent → node | 1 | no | Speak text in one room |
| `qnet/<room>/heard` | node → agent | 1 | no | Transcript or explicit silence during an active session |
| `qnet/look` | agent → all nodes | 1 | no | Ask every node, or one named room in guide mode, to inspect its current frame |
| `qnet/<room>/looked` | node → agent | 1 | no | Text-only result of a local VLM inspection |
| `qnet/<room>/status` | node → agent/dashboard | 1 | yes | Latest node health; the broker Last Will publishes `offline` |
| `qnet/session/<id>` | agent → dashboard/nodes | 1 | no | One live session event, identical to the event appended to JSONL |

The agent subscribes to `qnet/+/event`, `qnet/+/ask`, `qnet/+/heard`,
`qnet/+/looked`, and `qnet/+/status`. A room node subscribes only to its own
`qnet/<room>/say`, plus session events when it needs to track whether its room
has an active conversation. The dashboard subscribes to `qnet/+/status` and
`qnet/session/+`.

There is deliberately no global speech topic. Whole-home or group speech is
fanned out by the agent as one `qnet/<room>/say` publication per destination
room. This keeps room identity explicit and makes the asking room the natural
reply destination.

## Payloads

### Event

Topic: `qnet/<room>/event`

Required fields: `id`, `ts`, `room`, `kind`, `conf`, `meta`.

For v1, `kind` is `fall.detected`, `conf` is between 0 and 1, and `meta` is an
object containing detector-specific semantic evidence. See `event.json`.

### Ask

Topic: `qnet/<room>/ask`

Required fields: `id`, `ts`, `room`, `kind`, `text`.

`kind` is one of:

- `query`: `text` contains up to 10 seconds of rolling local ASR text. It may
  include background speech before "Hey Home" and the wake phrase itself. IQ9
  owns activation and intent routing; consumers must not assume the wake phrase
  starts the string or has already been removed.
- `responder_brief`: `text` is the empty string; room identity is sufficient.

See `ask-query.json` and `ask-responder-brief.json`.

### Say

Topic: `qnet/<room>/say`

Required fields: `id`, `ts`, `room`, `text`, `prio`.

`prio` is `safety` or `comfort`. Room nodes process `safety` before queued
`comfort` speech. `id` provides QoS-1 deduplication. See `say.json`.

### Heard

Topic: `qnet/<room>/heard`

Required fields: `id`, `ts`, `room`, `text`, `silence`.

When `silence` is true, `text` must be empty. When false, `text` must be
non-empty. `heard` is used only during an active session; idle ASR candidates
use `ask`. See `heard.json`.

### Look

Topic: `qnet/look`

Required fields: `qid`, `ts`, `object`, `mode`, `room`.

`mode` is `find` or `guide`. In `find` mode, `room` is null and all nodes inspect
their current frame. In `guide` mode, `room` names the single room that should
produce a more precise description. See `look.json`.

### Looked

Topic: `qnet/<room>/looked`

Required fields: `qid`, `ts`, `room`, `found`, `answer`.

The `qid` correlates the response with `look`. Only semantic text leaves the
node. When `found` is false, `answer` may be empty. See `looked.json`.

### Status

Topic: `qnet/<room>/status`

Required fields: `ts`, `room`, `node_id`, `state`, `voice_state`.

`state` is `online` or `offline`. `voice_state` is `starting`, `idle`,
`listening`, `speaking`, or `error`. The node publishes retained `online`
health at connection and installs a retained `offline` Last Will.

### Session event

Topic: `qnet/session/<id>`

Required fields: `id`, `ts`, `room`, `skill`, `urgency`, `phase`, `state`,
`event`, and `data`.

`urgency` is `safety` or `routine`; `state` is `active`, `closed`, or
`cancelled`. `event` identifies the individual log entry, such as `detected`,
`say`, `heard`, `phase`, `tool`, or `refusal`. `data` holds event-specific
fields. The same object is appended as one JSONL line and published live. See
`session.json`.

## Compatibility policy

Fixtures represent the current contract, not examples to copy loosely. A
producer must emit every required field with the documented type; a consumer
may ignore unknown extra fields so the contract can be extended compatibly.
Breaking changes require a deliberate contract version and coordinated rollout.
