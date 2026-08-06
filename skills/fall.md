---
name: fall-response
trigger: fall.detected
urgency: safety            # safety takes over the dashboard; routine does not
source: IFRC 2020 First Aid Guidelines; AHA 2020 Highlights; "In Case of a Fall"
        (California DSS / IHSS Training Academy, adapted from US National
        Library of Medicine, 2013)
emergency_number: "911"
---

## Phases
```yaml
- id: check
  opening: "I saw you fall. Take a breath — are you okay?"   # canned, spoken instantly
  goal: "Find out whether they are hurt or need help."
  tools: []
  exits:
    ok:       "they clearly say they are fine and deny pain or hitting their head"
    escalate: "they say no, ask for help, report pain, or do not respond"
  timer: { after_s: 30, goto: escalate }

- id: escalate
  opening: "It's okay — I'm getting you help. Try to get comfortable, and
            don't strain to move."
  goal: "Keep them informed while help is on the way. Say what is actually
         happening, never filler — you have no tools to call, just talk."
  tools: []
  on_enter: [notify_contacts]     # fires automatically, canned message, no model
  exits:
    check: "they respond coherently — go back and reassess how they are"
  timer: { after_s: 30, goto: call_help }   # the contact's reply window: the
                                            # Telegram question promises 30 s

- id: contact_engaged
  # Reached ONLY by the engine, when a trusted contact replies "ok"/"on my
  # way"/... to the escalation question (engine rails, never an LLM exit —
  # which is exactly why it is not in escalate's exits). {contact} is rendered
  # by the engine from the contact who actually acknowledged.
  opening: "Good news — {contact} saw my message and is coming to check on you.
            I'll stay with you until they arrive."
  goal: "A trusted contact is on the way. Keep them company with true updates —
         you have no tools to call, just talk."
  tools: []
  on_enter: [notify_contacts]     # the "I'll hold off" confirmation to the contact
  exits:
    check: "they respond coherently — go back and reassess how they are"
  timer: { after_s: 180, goto: call_help }  # backstop: an acked-then-silence
                                            # must never strand someone

- id: call_help
  opening: "You haven't answered, so I'm calling emergency services now."
  goal: "Stay with them and keep talking. You have no tools to call — the
         call is already being placed automatically."
  tools: []
  on_enter: [call_emergency, notify_contacts]
  exits:
    resolved: "a responder has arrived"
```

**`on_enter` replaces `must` for these two.** `must` meant "guaranteed before exit, enforced by the timer as a fallback" — reliable, but still routed through the agent's turn. `on_enter` is stronger: the action fires the instant the phase starts, no agent turn involved at all. Given how consequential these two are, "instant and automatic" is worth being more explicit than "guaranteed eventually."

**The four possible Telegram messages, templated, sent with no model call:**

```
escalate        on_enter → "🔴 Possible fall — {resident.name}, {room}. Reply OK if you can
                            check on {resident.name} — otherwise I'll call emergency services
                            in 30 seconds."
contact_engaged on_enter → "🤝 Got it — I'll hold off on emergency services. I'll still call
                            in 3 minutes unless someone resolves this."
call_help       on_enter → "📞 No response from {resident.name} — calling emergency services now ({room})."
cancel, if notified      → "✅ False alarm — {resident.name} confirmed they're okay ({room}). No action needed."
```

**`{room}` is in the alarm messages, deliberately — it's already known (the event carries it, §4) and it's the one fact a trusted contact needs most to act on the message: which room to go to or describe to a dispatcher. Free to include, easy to forget, so it's spelled out here rather than left implicit.**

**The escalation message is a question, and the reply is matched on the engine rails — never by the model.** "ok / okay / on it / got it / omw / on my way / i got this / handling" (case-insensitive, word-boundary) from a configured contact during `escalate` jumps the session to `contact_engaged`; "call 911 / call emergency (services)" from a contact at any point while the session is escalating jumps straight to `call_help`. The numbers the messages promise are the timers above: 30 s is `escalate`'s window, 3 minutes is `contact_engaged`'s backstop — change one, change the other.

## Guidance
One instruction at a time, by name, calm and slow. Never say "emergency" first.
Do not tell them to get up. If they mention hip pain or hitting their head, escalate even if they said they were fine.
Say what is actually happening — "Sarah has been messaged", "it's been two minutes" — never filler.
Comfort/positioning guidance is said once, in the opening line — never repeated by the comfort loop. The loop's job is status, not instructions; repeating "get comfortable" every 20 seconds would read as nagging, not care.
