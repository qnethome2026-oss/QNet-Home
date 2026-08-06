---
name: first-aid
region: US-CA
emergency_number: "911"
source: "California EMSA lay-rescuer guidance, harmonized with AHA/IFRC first-aid basics"
# Verified 2026-08-06: the agency (California Emergency Medical Services
# Authority, emsa.ca.gov) is real and publishes lay-rescuer-level first-aid
# guidance aligned with AHA guidelines ("Emergency First Aid Guidelines for
# California Schools"; Title 22 lay-rescuer training standards). The
# sentence-level claims below still await the §18 human medical review.
source_verified: true
version: 1
retrieved: 2026-08-06
review: "pending human medical review - DESIGN §18"
---

What the house may say when the person on the floor names a problem, while
help is already on the way. Loaded by `engine.parse_first_aid`; matched on the
engine rails (word-boundary, case-insensitive), never by the model — the model
only rewords a matched sentence, or never sees it at all.

Each `## topic` is one `keywords:` line and then ONE-TO-TWO sentences of
conservative lay-rescuer guidance for someone waiting for help on the floor.
**First match wins, so the file's order is its specificity order** — `head`
before `pain`, so "my head hurts" gets the head sentence. Keep it calm,
imperative-light, and thin: if a claim can't be safely generalized for a lay
rescuer, it is left out. Never promise anything; never tell them to get up —
that rule belongs to `fall.md` and it holds here too.

## bleeding
keywords: bleeding, bleed, blood, cut, gash
If you can reach it, press firmly on it with a clean cloth and keep the
pressure on.

## head
keywords: head, headache, hit my head, dizzy, dizziness, woozy, lightheaded, light-headed
Stay lying down for now, and don't try to get up quickly.

## nausea
keywords: nauseous, nauseated, nausea, sick, throw up, vomit, faint, fainting, pass out
If you can do it without straining, lie on your side.

## cold
keywords: cold, freezing, shivering, shiver, chilly
Cover yourself with whatever is in easy reach — a blanket, a towel, or a coat.

## scared
keywords: scared, afraid, frightened, anxious, panic, panicking, nervous, alone, lonely
Take slow, easy breaths; you're not alone.

## stuck
keywords: stuck, trapped, help, can't get up, cant get up, can't move, cant move, can't stand, cant stand
Don't strain or force yourself up; it's okay to rest right where you are.

## pain
keywords: pain, painful, hurts, hurt, hurting, sore, ache, aches, aching
Stay as still as is comfortable, and don't force any movement that hurts.
