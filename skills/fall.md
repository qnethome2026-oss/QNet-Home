---
name: fall-response
trigger: fall.detected
urgency: safety            # safety takes over the dashboard; routine does not
source: IFRC 2020 First Aid Guidelines; AHA 2020 Highlights; "In Case of a Fall"
        (California Dept. of Social Services / IHSS Training Academy, adapted
        from "Falls," U.S. National Library of Medicine, October 2013)
source_url: "https://www.cdss.ca.gov/agedblinddisabled/res/VPTC2/5%20Injury%20and%20Fall%20Prevention/In_Case_of_a_Fall.pdf"
source_retrieved: 2026-08-07
source_verified: true      # verified = the agency exists and the document says what
                           # this file attributes to it (re-read 2026-08-07). It is
                           # NOT a medical sign-off: the spoken wording remains
                           # pending human medical review (DESIGN.md, Limits).
emergency_number: "911"
---

## Phases
```yaml
- id: check
  # CDSS "In Case of a Fall": "Take several deep breaths to try to relax" and
  # "Remain still on the floor or ground for a few moments ... to decide if
  # there is an injury before getting up." Asking before any movement is the
  # source's assess-first rule.
  opening: "I saw you fall. Take a breath — are you okay?"   # canned, spoken instantly
  goal: "Find out whether they are hurt or need help."
  tools: []
  exits:
    ok:       "they clearly say they are fine and deny pain or hitting their head"
    escalate: "they say no, ask for help, report pain, or do not respond"
  timer: { after_s: 30, goto: escalate }

- id: escalate
  # CDSS: "If there is an injury or the person cannot get up on his own: Ask
  # someone for help or call 911. If alone, try to get into a comfortable
  # position and wait for help to arrive." "Don't strain to move" condenses
  # "Remain still ... Getting up too quickly or in the wrong way could make an
  # injury worse." (This resolves the wording flag in DESIGN.md's Limits: both
  # halves now trace to the source; medical review still pending.)
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
  # No "you haven't answered" claim in this opening: call_help is reached by
  # more than the pure-silence path (live 3PM test: the person had spoken
  # seconds earlier and was told "I haven't heard from you"). The line must
  # be true on every route here.
  opening: "I'm calling emergency services for you right now. Help is coming
            — stay with me."
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

**Source fidelity notes (CDSS "In Case of a Fall", retrieved 2026-08-07).** The document *does* teach a safe get-up sequence for an uninjured person who can manage it alone (roll onto a side → push to seated → rest to let blood pressure adjust → hands and knees, crawl to a sturdy chair → hands on the seat, one foot flat → rise and turn to sit). This file deliberately does not speak it: a detected fall means injury has not been ruled out, and coaching a get-up over a speaker with no eyes on the person fails the source's own "decide if there is an injury before getting up" precondition. If a future revision adds it, it belongs as a new phase reached only from `check`'s explicit "I'm fine, I just need to get up" path — noted here, not added. Two honest gaps: the source never mentions keeping the person **warm** (only "comfortable"), so this file makes no warmth claim; and the source's closing advice — "Any fall should be reported to the doctor. Write down information about when, where, and how the fall occurred" — is served by the session log every fall already produces, not by anything spoken.

## Guidance
One instruction at a time, by name, calm and slow. Never say "emergency" first.
Do not tell them to get up. If they mention hip pain or hitting their head, escalate even if they said they were fine.
If they say they cannot get up, treat that alone as a reason to escalate, injured or not — the source's rule is "injury *or* the person cannot get up on his own."
Say what is actually happening — "Sarah has been messaged", "it's been two minutes" — never filler.
Comfort/positioning guidance is said once, in the opening line — never repeated by the comfort loop. The loop's job is status, not instructions; repeating "get comfortable" every 20 seconds would read as nagging, not care.
