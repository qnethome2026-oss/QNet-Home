# Judging notes — submission requirements + rubric

*Condensed from the `judging/` folder on branch `asr-tts-mqtt` (teammate's
transcriptions of the Hackathon SharePoint "Final Submission Requirements" and
"How It Works" pages, from photos taken 2026-08-03). Kept here so the checklist
survives the branch's retirement.*

## Final submission requirements

- All code open source, in a GitHub repository, containing:
  - **README** with: application description; names and emails of all eligible
    team members; setup instructions from scratch (incl. dependencies); run and
    usage instructions.
  - **An open-source license** (ours: AGPL-3.0-or-later, `LICENSE`).
  - **Compute applications**: a packaged Windows executable (.EXE) — or a
    packaged Windows app (.MSIX) — including all functionality, to streamline
    judging and Windows app store submission (ours: `packaging/`).
  - Mobile applications instead need an .APK (not applicable to us).
- The application must be runnable using the provided instructions, and must
  install and run on the Copilot+ PC for which it is intended, functioning as
  depicted in the text description.
- Must be developed/commercially ready to the extent it could be deployed on an
  app store or other open-source platform.
- **Deadline: repository link submitted via the Microsoft Form by 1:00 PM,
  August 7.**
- Optional but highly recommended: tests + testing instructions; a notes
  section; references; well-commented code.

## Judging rubric (100 points)

| Criterion | Points | Judged on |
|---|---|---|
| Technical Implementation | 40 | resource utilization, optimization, latency and performance, energy efficiency |
| Application Use-Case and Innovation | 25 | problem solving, creativity and uniqueness, user experience |
| Deployment and Accessibility | 20 | ease of installation and use |
| Presentation and Documentation | 15 | clarity of the presentation, code quality and documentation |

## Event context (from "How It Works")

Snapdragon Multiverse internal hackathon: teams of 3–5, five days
(Aug 3–7), each with a Copilot+ PC (Snapdragon X Series) as the central hub
plus a mobile device, Arduino UNO Q, and Qualcomm AI Cloud 100. No predefined
tracks — the focus is on how systems work together across devices, not what
runs on a single one. Final presentations Aug 7, 1:30 PM.
