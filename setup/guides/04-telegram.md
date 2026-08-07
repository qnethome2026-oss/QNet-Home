# Guide 4 — Telegram (the trusted-contact channel)

**What you're doing:** giving the house a way to reach real people. During
an incident, trusted contacts get messages like *"Reply OK if you can check
on Tony — otherwise I'll call emergency services in 30 seconds"* — and their
replies steer the escalation: `OK` claims the incident and holds the
(simulated) emergency call; `call 911` places it immediately.

**You need:** the Telegram app on each contact's phone, and the hub from
Guide 2 running. Total time: ~10 minutes.

**Skippable:** without this guide the house still works — notifications
print to the agent's console and append to `data/outbox/telegram.log` on the
hub, so you can demo everything and add Telegram later.

---

## Step 1 — Create the bot (once)

1. In Telegram, search for **@BotFather** (the verified one) and open a chat.
2. Send `/newbot`.
3. It asks for a **name** — anything, e.g. `My QNet Home`.
4. It asks for a **username** — must end in `bot`, e.g. `myqnethome_bot`.
5. BotFather replies with a **token** that looks like
   `1234567890:AAF4pXo3k...`. Copy it — this is `telegram_bot_token`.

⚠️ The token is a secret. It goes only in the hub's gitignored
`house.local.yaml` (Step 4) — never in a committed file, chat, or screenshot.

## Step 2 — Each trusted contact opens the bot (once per person)

On each contact's phone: search Telegram for the bot's username from Step 1
(e.g. `@myqnethome_bot`), open it, and press **Start**. Nothing visible
happens — that's fine; Telegram now allows the bot to message them.

## Step 3 — Get each contact's chat id

After every contact has pressed Start, run (laptop or hub, either works):

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates"
```

(Replace `<TOKEN>` with the Step 1 token — keep the word `bot` before it,
so the URL reads `.../botTOKEN/getUpdates`.)

In the JSON that comes back, find each person's block:

```json
"message": {"chat": {"id": 123456789, "first_name": "Sarah", ...}, "text": "/start"}
```

The number after `"id"` is that person's `telegram_chat_id`. One per
contact. (Empty `"result": []`? They haven't pressed Start, or the token is
wrong.)

## Step 4 — Put the values on the hub

Edit `~/qnet-home/config/house.local.yaml` on the hub (created in Guide 2
Step 5) so it reads:

```yaml
mqtt: { host: 127.0.0.1, port: 11883, ws_port: 19001 }
resident: { name: "Tony" }              # who the house watches over - used in messages
telegram_bot_token: "1234567890:AAF4pXo3k..."
contacts:
  - { name: "Sarah", telegram_chat_id: "123456789" }
  - { name: "Amit",  telegram_chat_id: "987654321" }   # add one line per contact
```

Then restart the agent and check it came up on the right broker:

```bash
ssh iq9 "sudo systemctl restart qnet-agent && sleep 3 && journalctl -u qnet-agent --no-pager | grep connected | tail -1"
```

Must print `connected 127.0.0.1:11883`.

## Step 5 — Test the full loop

1. Fire a test fall:
   ```bash
   ssh iq9 "cd qnet-home && PYTHONPATH=. ~/qnet-agent-venv/bin/python dev/inject.py --port 11883 fall --room kitchen"
   ```
2. Stay silent. Within ~35 seconds every contact's phone gets the
   escalation question naming the resident and the room.
3. Reply **`OK`** from one phone. Expected: that phone gets an
   acknowledgment, the room announces who is coming, and the journal shows
   the contact engaged:
   ```bash
   ssh iq9 "journalctl -u qnet-agent --no-pager | grep -i contact | tail -3"
   ```
4. End the test: say (or type in the dashboard composer) **"false alarm"**,
   or click **Mark resolved** on the dashboard banner.

## What you have now

Real people in the loop: milestone messages out, replies steering the
escalation in. Next: [Guide 5 — first run of the whole house](05-first-run.md).
