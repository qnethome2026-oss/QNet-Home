# Emergency knowledge skills (offline pack)

Offline, pre-distilled lay-rescuer guidance for QNet Home's emergency scenarios. The whole pack lives on disk, needs zero network, and each skill fits in a single small-LLM context — feasibility analysis and measured corpus sizes in `research/tech/offline-skill-packs.md`.

## How it's used

**The deterministic state machine selects the skill; the LLM only phrases it** (same reliability rule as everywhere else in Guardian — see `docs/SCOPE.md` §3). Mapping is direct: event type + response state → filename. No retrieval infra, no embeddings on the hot path — the matching file is loaded whole into the prompt (each is < 1k tokens).

```
fall + no reply            → fall-no-response.md
fall + any reply           → fall-responsive.md
  └ not breathing          → unresponsive-not-breathing-cpr.md
  └ breathing, no response → unresponsive-breathing.md
collapse + fast recovery   → faint-syncope.md
audio distress at mealtime → choking.md
```

## File format

Markdown + YAML frontmatter, deliberately OpenClaw-SKILL.md-compatible (`name`, `description` required there; our extra fields ride along). Extra frontmatter:

- `source` / `version` / `retrieved` — provenance; guidelines revise on ~5-year cycles (AHA/ILCOR), so packs must be rebuildable and dated.
- `region` / `emergency_number` — the only localization most protocols need. `{emergency_number}` and `{caregiver}` are substituted by Guardian at load time.

Body sections each skill follows:
- **Trigger** — which SemanticEvent/state reaches this skill
- **Steps** — numbered, with explicit decision branches; `[[skill-name]]` links are branch targets
- **Say this** — phrasing hints for Herald (tone, pacing, one-instruction-at-a-time rules)
- **Escalate when** — the policy line Guardian's state machine enforces deterministically

## Scope and safety framing

These skills relay established **lay-rescuer** guidance (IFRC 2020 International First Aid Guidelines, AHA 2020 Guidelines Highlights, CDC STEADI) — the same content taught in a public first-aid course. The system never diagnoses, and every severe path escalates to humans (caregiver + emergency services) *first*, guidance second. QNet Home is not a medical device.

Content was distilled by an LLM from the cited sources and needs a **human review pass against those sources before any demo claim** — that review is a Day-4 checklist item.
