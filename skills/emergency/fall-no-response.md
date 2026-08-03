---
name: fall-no-response
description: A fall was detected and the person is not responding to voice prompts. Guide assessment and escalation; branch to CPR or recovery position based on breathing.
source: IFRC International First Aid, Resuscitation, and Education Guidelines 2020 (Unresponsiveness); AHA 2020 Guidelines Highlights
version: 2020 guidelines
retrieved: 2026-08-03
region: US
emergency_number: "911"
---

# Fall detected, no response

**Trigger:** `SemanticEvent: fall` + no reply after two "Are you okay?" prompts (state machine owns the trigger; this skill owns what happens next).

## Steps

1. **Escalate immediately.** Notify the caregiver phone with the room, time, and event snapshot. An unresponsive person after a fall is always an emergency — do not wait for more evidence.
2. **Keep talking to the person.** Speak loudly and clearly by name: "«Name», can you hear me? Squeeze your hand or make a sound if you can hear me." Any response (sound, movement) → switch to [[fall-responsive]].
3. **If a bystander is present or arrives**, coach them:
   - "Tap their shoulders firmly and shout their name."
   - Still no response → "Call {emergency_number} now, or I can have {caregiver} do it. Put the phone on speaker."
   - "Look at their chest — are they breathing normally? Gasping is NOT normal breathing."
   - **Not breathing / only gasping** → go to [[unresponsive-not-breathing-cpr]].
   - **Breathing normally** → go to [[unresponsive-breathing]].
4. **Do not move the person** and tell the bystander not to move them (the fall may have injured the head, neck, or back) — except if they must be turned to keep the airway clear (recovery position) or to do CPR. CPR and an open airway always take priority over a possible spine injury.
5. **If the person is alone** (no bystander): the agent's whole job is escalation — caregiver alert, then emergency services per household policy. Keep speaking reassurance: "«Name», help is on the way. Stay still."
6. Keep the room light on ([[house-config]] if available), note the time of the fall, and report elapsed time to the caregiver and responders.

## Say this (Herald phrasing hints)

- To the person: calm, slow, by name. Never say "emergency" first — "I've asked Sarah to come help you" beats "I am calling 911."
- To a bystander: one instruction at a time. Wait for them to say done.

## Escalate when (Guardian policy)

- Always. This skill *is* the escalation path. Cancel only on clear voice confirmation ("I'm fine, cancel") → [[fall-responsive]] check-in still runs.
