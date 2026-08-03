---
name: fall-responsive
description: A fall was detected and the person responds ("I'm fine" or any reply). Check for injury red flags, coach a safe get-up, and log the incident.
source: CDC STEADI "What to do when you fall"; IFRC 2020 Guidelines (assessment of an injured person)
version: 2020 guidelines
retrieved: 2026-08-03
region: US
emergency_number: "911"
---

# Fall detected, person responds

**Trigger:** `SemanticEvent: fall` + person replies to the check-in (including "I'm fine, cancel").

## Steps

1. **"I'm fine" is not the end.** Acknowledge the cancel, then run a 20-second check-in before standing down:
   - "Before you get up — does anything hurt? Head, hip, wrist?"
   - "Did you hit your head?"
2. **Red flags — escalate to [[fall-no-response]] step 1 (caregiver alert) even over protest:**
   - Hit their head AND takes a blood thinner (from household [[med-schedule]] if configured)
   - Severe pain, visible deformity, or bleeding
   - Dizziness, confusion, or slurred speech
   - Cannot get up after two tries
3. **No red flags → coach the safe get-up** (one step at a time, wait for "okay" between steps):
   1. "Stay still for a moment. Breathe."
   2. "Roll onto your side, then onto your hands and knees."
   3. "Crawl to a sturdy chair" (name the nearest one from room config if known).
   4. "Put your hands on the seat, bring one foot flat on the floor."
   5. "Push up slowly and turn to sit. Sit for a minute before standing."
4. **Log the incident** regardless of outcome — time, room, response. Falls that "were fine" are the strongest predictor of the next one; surface a weekly count in the caregiver digest.
5. If this is the **second fall in 24 hours**, notify the caregiver even if the person cancels ("two falls in a day" is a configured household policy, stated to the person transparently).

## Say this (Herald phrasing hints)

- Respect the cancel: "Okay, cancelling. One quick thing before you get up —" keeps trust while still running step 1.
- Never scold, never mention statistics to the person. Reassure: "Take your time, I'm right here."

## Escalate when (Guardian policy)

- Any red flag in step 2 → caregiver alert with "responsive but flagged" priority.
- Two failed get-up attempts → caregiver alert.
- Clean check-in + successful get-up → log only.
