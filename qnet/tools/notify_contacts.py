# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""notify_contacts - message the caregiver (DESIGN.md §7, §11).

**Invoked by the engine's ``on_enter``, never by the LLM** - it is registered
``engine_only=True`` so nothing accidentally offers it to the model as a
callable tool. The four possible messages are templated and sent with no
model call (DESIGN §7, skills/fall.md); ``{room}`` is in the alarm messages
deliberately - it is the one fact a trusted contact needs most to act on.

The ``escalate`` message is a QUESTION (T-contact-ack): the contact gets 30
seconds to reply OK before the (SIMULATED) emergency call fires, and
``contact_engaged`` is the confirmation sent back when they do. The numbers in
both templates mirror skills/fall.md's timers (30 s escalate window, 180 s
backstop) - change one, change the other.

Delivery: one HTTPS POST to the Telegram Bot API per configured contact, 5 s
timeout, one retry. If ``telegram_bot_token`` or every contact's
``telegram_chat_id`` is missing/"TODO", this falls back to console + file only
- ``delivered`` is False and ``channel`` is "console". Either way the message
is always appended to ``data/outbox/telegram.log``, and this function never
raises: a broken network, a bad token, a locked file - all become a returned
dict, not an exception, because the engine treats tool outcomes as facts.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from qnet.tools import ToolContext, console_print, register

TEMPLATES = {
    "escalate": (
        "\U0001F534 Possible fall — {resident}, {room}. Reply OK if you can check on "
        "{resident} — otherwise I'll call emergency services in 30 seconds."
    ),
    "contact_engaged": (
        "\U0001F91D Got it — I'll hold off on emergency services. "
        "I'll still call in 3 minutes unless someone resolves this."
    ),
    "call_help": "\U0001F4DE No response from {resident} — calling emergency services now ({room}).",
    "false_alarm": "✅ False alarm — {resident} confirmed they're okay ({room}). No action needed.",
}

# Fixed per DESIGN §11 - not configurable. data/ is gitignored (see repo root
# .gitignore); the directory is created on demand.
OUTBOX = Path("data/outbox/telegram.log")

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _resident_name(config: dict) -> str:
    return ((config or {}).get("resident") or {}).get("name") or "the resident"


def _valid_chat_ids(config: dict) -> list[str]:
    """Contacts with a real ``telegram_chat_id`` - "TODO" and blank don't count."""
    ids: list[str] = []
    for contact in (config or {}).get("contacts") or []:
        chat_id = (contact or {}).get("telegram_chat_id")
        if chat_id and chat_id != "TODO":
            ids.append(str(chat_id))
    return ids


def _append_outbox(kind: str, text: str) -> None:
    """Always-on record, regardless of delivery outcome - console fallback's memory."""
    OUTBOX.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": round(time.time(), 1), "kind": kind, "text": text}
    # utf-8 explicitly: the templates carry emoji, and Windows' default file
    # encoding is not utf-8.
    with OUTBOX.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


async def _send_one(client: httpx.AsyncClient, token: str, chat_id: str, text: str) -> bool:
    """One Telegram send, 5 s timeout, one retry. False on any failure - never raises."""
    url = TELEGRAM_API.format(token=token)
    for _attempt in range(2):
        try:
            resp = await client.post(url, data={"chat_id": chat_id, "text": text}, timeout=5.0)
            if resp.status_code == 200:
                return True
        except httpx.HTTPError:
            continue
    return False


@register("notify_contacts", engine_only=True)
async def notify_contacts(ctx: ToolContext, kind: str = "escalate") -> dict:
    """Send the templated milestone message for ``kind`` (escalate/call_help/false_alarm)."""
    template = TEMPLATES.get(kind, TEMPLATES["escalate"])
    text = template.format(resident=_resident_name(ctx.config), room=ctx.room)

    delivered = False
    channel = "console"

    try:
        token = (ctx.config or {}).get("telegram_bot_token")
        chat_ids = _valid_chat_ids(ctx.config)
        if token and token != "TODO" and chat_ids:
            async with httpx.AsyncClient() as client:
                results = [await _send_one(client, token, chat_id, text) for chat_id in chat_ids]
            delivered = bool(results) and all(results)
            channel = "telegram" if delivered else "console"
        else:
            console_print(f"[notify_contacts:console] {kind}: {text}")
    except Exception as exc:  # a tool never raises - the engine treats this as a fact
        console_print(f"[notify_contacts:error] {kind}: {text} ({exc!r})")
        delivered = False
        channel = "console"

    try:
        _append_outbox(kind, text)
    except OSError as exc:
        console_print(f"[notify_contacts:outbox-write-failed] {exc!r}")

    try:
        ctx.log({"event": "tool", "tool": "notify_contacts", "result": channel if delivered else "console"})
    except Exception:
        pass

    return {"delivered": delivered, "channel": channel, "text": text}
