# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""Tools - one file per tool, registered in a dict (DESIGN.md §11).

Adding a tool never edits the engine. Not every tool is something the LLM
chooses to call; anything consequential enough that it must not depend on the
model is invoked by the engine directly:

    notify_contacts      engine, on_enter    Telegram, one HTTPS POST
    call_emergency       engine, on_enter    SIMULATED - renders the payload
    look_in_rooms        LLM, in find.md     broadcast look, collect looked
    get_session_summary  engine, brief       latest fall-response session file

Session logging follows the same rule and is not a tool at all (§6).

STUB - the registry and the tools themselves land in T2.3.
"""

from __future__ import annotations

REGISTRY: dict = {}
