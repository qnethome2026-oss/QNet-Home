# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""Inbound Telegram - the trusted contact's replies (T-contact-ack).

The escalation message is a question ("Reply OK if you can check on {resident}
- otherwise I'll call emergency services in 30 seconds"), so the agent needs
ears on Telegram. This module is those ears and nothing more: a long-poll on
the Bot API's ``getUpdates``, accepting messages ONLY from configured contact
chat ids, mapping chat id -> contact name, and handing ``(name, text)`` to the
engine (``Agent.on_contact_reply``). What a reply *means* is decided on the
engine rails - this module never interprets text.

Deliberate properties, each load-bearing:

* **Cleanly absent without real credentials.** ``Agent.serve`` starts the
  poller only when ``enabled()`` says the bot token AND at least one contact
  chat id are real (not blank, not "TODO"). Tests, ``--no-llm`` dev runs and
  the shipped template config therefore never open a network connection.
* **The offset is persisted** (``data/telegram_offset.json``) so a restart
  never replays a reply it already routed - replaying an old "ok" into a new
  incident would be routing a stale decision.
* **First ever start skips the ENTIRE backlog.** The bot's chat history holds
  old test messages ("hi"); processing them on first boot would feed stale
  text into whatever session happens to be live. The drain loop reads and
  discards everything pending, then persists the high-water mark.
* **The poller never raises.** Any network or API failure waits and retries;
  a bad update is logged and skipped. Ears that crash are worse than no ears,
  because the escalation timer is still the guaranteed path either way.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

log = logging.getLogger("qnet.agent.telegram")

API_URL = "https://api.telegram.org/bot{token}/getUpdates"

# Fixed like notify_contacts' OUTBOX (DESIGN §11): data/ is gitignored and
# created on demand. Tests override via the constructor.
STATE_PATH = Path("data/telegram_offset.json")

# Telegram long-poll: the server holds the request up to this many seconds.
POLL_TIMEOUT_S = 20
# How long to wait after a failed poll before trying again.
RETRY_DELAY_S = 3.0


def contact_map(config: dict | None) -> dict[str, str]:
    """chat id -> contact name, for contacts whose chat id is real."""
    out: dict[str, str] = {}
    for contact in (config or {}).get("contacts") or []:
        chat_id = (contact or {}).get("telegram_chat_id")
        if chat_id and chat_id != "TODO":
            out[str(chat_id)] = (contact or {}).get("name") or "your contact"
    return out


def enabled(config: dict | None) -> bool:
    """May a poller run at all? Real token AND at least one real chat id."""
    token = (config or {}).get("telegram_bot_token")
    return bool(token and token != "TODO" and contact_map(config))


class TelegramPoller:
    """One long-poll loop against ``getUpdates``, for the life of the agent."""

    def __init__(
        self,
        config: dict,
        on_reply: Callable[[str, str], Awaitable[None]],
        state_path: str | Path = STATE_PATH,
        client: Any = None,
    ) -> None:
        self.token: str = str((config or {}).get("telegram_bot_token") or "")
        self.contacts = contact_map(config)
        self.on_reply = on_reply
        self.state_path = Path(state_path)
        # None means "never ran before" - which is what triggers the backlog
        # drain. 0 or a real update id means "initialized, resume from here".
        self.offset: int | None = self._load_offset()
        self._client = client  # tests inject a fake; production builds httpx

    # --- offset persistence ----------------------------------------------

    def _load_offset(self) -> int | None:
        try:
            return int(json.loads(self.state_path.read_text(encoding="utf-8"))["offset"])
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _save_offset(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps({"offset": self.offset}), encoding="utf-8")
        except OSError:
            log.warning("could not persist telegram offset to %s", self.state_path)

    # --- the loop ---------------------------------------------------------

    async def run(self) -> None:
        """Poll until cancelled. Started by ``Agent.serve``, never by tests."""
        client = self._client if self._client is not None else httpx.AsyncClient()
        try:
            if self.offset is None:
                await self.skip_backlog(client)
            while True:
                updates = await self.poll(client, POLL_TIMEOUT_S)
                if updates is None:
                    await asyncio.sleep(RETRY_DELAY_S)
                    continue
                for update in updates:
                    await self.handle(update)
                if updates:
                    self._save_offset()
        finally:
            if self._client is None:  # only close what this poller opened
                await client.aclose()

    async def poll(self, client: Any, timeout: int) -> list[dict] | None:
        """One ``getUpdates`` call. Advances the offset; ``None`` on failure."""
        params: dict[str, Any] = {"timeout": timeout}
        if self.offset is not None:
            # Passing offset also confirms everything below it server-side,
            # which is exactly the "never replay after restart" guarantee.
            params["offset"] = self.offset + 1
        try:
            resp = await client.get(
                API_URL.format(token=self.token), params=params, timeout=timeout + 10
            )
            body = resp.json()
        except Exception as exc:  # noqa: BLE001 - the poller never raises
            log.warning("telegram getUpdates failed (%r) - retrying", exc)
            return None
        if not isinstance(body, dict) or not body.get("ok"):
            log.warning("telegram getUpdates answered not-ok: %r", body)
            return None
        updates = [u for u in (body.get("result") or []) if isinstance(u, dict)]
        for update in updates:
            if isinstance(update.get("update_id"), int):
                self.offset = (
                    update["update_id"] if self.offset is None else max(self.offset, update["update_id"])
                )
        return updates

    async def skip_backlog(self, client: Any) -> None:
        """First ever start: drain and discard everything already pending.

        CRITICAL (T-contact-ack): the chat holds old messages from bot setup;
        none of them may ever be routed into a live session. Short polls
        (timeout 0) until a batch comes back empty, then persist the mark so
        the next restart resumes instead of draining again.
        """
        skipped = 0
        while True:
            updates = await self.poll(client, 0)
            if updates is None:
                await asyncio.sleep(RETRY_DELAY_S)
                continue
            if not updates:
                break
            skipped += len(updates)
        if self.offset is None:
            self.offset = 0  # nothing was pending; still mark "initialized"
        self._save_offset()
        log.info("telegram: first start - skipped %d backlog update(s)", skipped)

    async def handle(self, update: dict) -> None:
        """Route one update - or say exactly why it was dropped."""
        message = update.get("message") or {}
        chat_id = str(((message.get("chat") or {}).get("id") or "")) or ""
        text = message.get("text") or ""
        if not chat_id or not text:
            return  # joins, stickers, edits: not a reply
        name = self.contacts.get(chat_id)
        if name is None:
            # Anyone can message a public bot; only configured contacts count.
            log.info("telegram: message from unconfigured chat %s ignored", chat_id)
            return
        try:
            await self.on_reply(name, text)
        except Exception:  # noqa: BLE001 - one bad reply must not stop the ears
            log.exception("contact reply handler failed for %s", name)
