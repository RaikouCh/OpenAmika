# Text her — Discord & Telegram

`messengers/service.py` lets you text Amika from a Discord bot or a Telegram bot. **Words only**: no
voice, no stage. Her quick line and her real reply arrive as two ordinary messages, the way a person
texts twice. launch.py starts the service next to the speech gateway; its row on the launcher says which
bots are online, or that none is set up yet.

## Set it up (Setup page → *Text her*)

**Discord**
1. [Developer Portal](https://discord.com/developers/applications) → *New Application* → *Bot* → *Reset Token*; copy it.
2. *OAuth2 → URL Generator*: scope `bot`. No permissions are needed for DMs; add *Send Messages* if you
   want to @mention her in a server. Open the link, invite the bot to any server you share with it
   (that is what lets you DM it). **The bot must share a server with you before a DM works**: without a
   server of your own, make a small one first (Discord: + → Create My Own). The MekaHime Discord is not
   that server: her bot lives on yours.
3. Paste the token on the Setup page, add **your user id** to the allow-list (Discord: *Settings →
   Advanced → Developer Mode*, then right-click your name → *Copy User ID*), tick *Enabled*, save.
4. DM the bot. In a server she answers only when @mentioned.

**Telegram**
1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
2. Paste it, tick *Enabled*, save. Send the bot `/id`: it answers with your user id. Add that id to the
   allow-list and save again.

Nothing privileged is requested from Discord: DMs and @mentions carry their text without the
"message content" intent.

## Who may text her

Only the user ids on a platform's allow-list. Anyone else is told their id (once an hour) so you can add
them, and nothing of theirs reaches her. The lists and tokens live in `config/messengers.json`
(git-ignored; `config/messengers.example.json` shows the shape). A file edited by hand is picked up within
a few seconds.

## How a message becomes a turn

```
Discord DM / Telegram message (allowed user)
  → outbox: one turn at a time, in order
  → brain  emit("message", {text, turn_id, context})      the same contract as the speech gateway
  ← surface_done.reply   → her quick line, sent as a message
  ← deep_done.speech     → her real reply (deduplicated against the quick line by the brain)
  ← end
```

- The turn is **protected** in the brain once her first message is delivered — what the first TTS audio
  does on stage — so it stays in her history. Once her whole reply is delivered the service tells the brain
  the turn has "played out" (what the stage sends when the audio ends), and the brain archives it into her
  memory like any spoken turn.
- Each turn carries a context line (in Chinese, like all her cues: this is a text message on Discord or
  Telegram, read on her phone, he is not next to her), so she knows she is texting, not talking. It also says
  where she is by name, her Discord channel on his own server (or his DMs), so she says "in my Discord channel
  on your server" instead of a bare "here", and that only words reach her there: pictures and voice
  messages do not (the bridge reads a message's text only).
- Replies longer than a platform's limit (Discord 2000, Telegram 4096 characters) are split at a
  paragraph, then a sentence, then a space.
- Turns **she** starts (a reflection making her speak first, a helper reporting back) go to the chat she
  last talked in. If nobody has texted her yet, they are logged and not delivered.
- The web stage and the bots share one brain and one history. Her replies go to the channel the message
  came from; the stage does not speak a Telegram reply.

## Endpoints (127.0.0.1:5215, local only; another port: `messengers_port` in settings.json)

| Route | Purpose |
|---|---|
| `GET /health` | `{app, ok, brain, bots, light}` — the launcher reads `light` for the row |
| `GET /api/status` | settings (tokens masked) + live bot status; the Setup page reads it through the gateway (`/api/build_f/messengers`) |
| `POST /api/config` | save settings; bots start / stop / restart to match |
| `POST /api/text {"text": "…"}` | a local text channel: her replies to one message, as JSON — handy for scripts and checks |

`AMIKA_MESSENGERS_PORT` changes the port (the gateway's `AMIKA_MESSENGERS_URL` must then match).
Requires `discord.py` in the speech python for Discord (`pip install discord.py`); Telegram uses the Bot
API over plain HTTPS, no library.
