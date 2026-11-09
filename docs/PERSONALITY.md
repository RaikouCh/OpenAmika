# Personality: the three context tiers, and what to edit

OpenAmika's "mind" is three LLM roles over the same conversation, each with its own prompt template
(all editable on the Setup page, hot-reloaded on save):

**Voice convention — one rule.** Anything *she* has to output is first person (我); everything the
system says *to* her is second person (你). So the templates, every `scenes.json` block, and the
runtime-injected lines in `webui.py` (the deep instruction variants, the pending-thought reminder, the
blurt note, the proactive-open cue, the tool-record notes) all address her as 你 — 你是桜井美香,
你住在…, 回复你想说的话…. First person is reserved for her transcript and output contract: `我说：` /
`我心想：`, the history verbs the parser keys on (`我准备说`, `我脱口而出`, `我仔细地想了想`), the example
output lines, and whatever stands in her own-thought slot of the reflection prompt (`[她现在来找你]`).
Those tokens are hard-coded in `po_contract.py` and `webui.py` — leave them alone. The reflection tier
addresses the *coach* as 你 and calls her 她, and writes its hints in 我 on purpose, because they become
her own thoughts.

## Surface — `brain/表层.txt` (instant)

A small fast model answers **first**, within ~0.5 s, with exactly four lines:

```
status: ok | unfinished | not-for-me    ← did she even need to respond?
tone:   register_emotion                ← first facial/voice reaction
mode:   say | say+think | think         ← is this a reflex, or does the deep tier take over?
reply:  one spoken line (may be empty)
```

The surface is her reflexes: greetings, one-word reactions, a filler ("我想想……") while the deep tier
thinks. Its reply is spoken immediately and handed to the deep tier as the *blurt* so she never repeats
herself. `status` decides whether a half-finished or not-addressed-to-her utterance gets silence.

## Deep — `brain/例子.txt` (her real voice)

The main model writes her actual turn:

```
[casual_happy]"说出口的话。【Sigh】可以夹声效。"[casual_shy]"下一句。"
我心想：她真实的想法，可以带动作和场景。……【想想】
```

- `[register_emotion]"…"` — every spoken sentence carries one of the **69 emotion keys**
  (5 registers: polite / casual / serious / intimate / whisper). The same key drives TTS, the Live2D
  expression and the motion.
- `我心想：` — inner thoughts. Never spoken; they appear in her history and make her consistent.
- `【想想】` — she "raises her hand" for the reflection tier.
- Sound effects — nine closed names (`【Sigh】`, `【Laugh】`…) remain part of the output contract,
  but OpenAmika ships no SFX audio: the tags are parsed and stripped from speech, and playback
  silently no-ops (drop wavs into `speech/static/sfx/` to enable; see the README there).

The deep prompt is **cache-first**: every static rule sits in one prefix the provider caches; after it
come daily context → scene → time → **recent history (ending with your current line) → memory block** →
pending thought → blurt → instruction variant → a one-line language rule (she answers in your language;
an explicit "say it in Japanese" lasts one turn).

## Reflection — `brain/思考.txt` (the background coach)

Between turns (and when the deep tier asks with 【想想】), a third model watches the conversation and
emits up to three channels:

```
<提示>  a hint injected into her next deep prompt
<计划>  a persistent plan (kept until replaced)
<开口>  make her SPEAK FIRST — the idle watcher turns this into a proactive turn
```

This is what makes her feel alive when you go quiet. `idle_reflection` / `auto_open_from_reflection`
in `config/build_f.json` switch it. The silence is counted from the moment her voice stops (the stage's
`speech_done`), never from the end of her text, and `silence_remarks` (`normal`: 30 s, `rare`: 90 s, `off`; Setup →
You & Amika → "When you go quiet") sets how soon she remarks on it.

A reply she speaks aloud is asked for about four sentences unless you ask for a story or for more: one line of the
deep tier's per-turn instruction (`VOICE_REPLY_NOTE` in `brain/webui.py`), not the persona files. Text (Discord,
Telegram, or the page with her voice off) keeps the long form.

## Memory

Every protected turn is archived as **evidence** (quotes, not summaries). A writer model extracts
facts with their verbatim quotes; corrections supersede old facts but never erase them. Retrieval is
hybrid BM25 + local bge-m3 embeddings, rendered into the prompt as natural language ("三个月前的上午，
{user_name}说：…") with perceived-time phrases — no machine syntax ever reaches her.

## Her situation (the shipped story)

She grew up in Kyoto as the Sakurai heir — the shrine, the ley lines, the purification duties — and at
eighteen, tired of a life where every step was arranged, she flew to **your city** to live with you as
roommates (rent-free; her side of the deal is being the best company she can). The three templates tell
that story in their own register (deep: first-person memory; surface: a one-page summary; reflection: a
third-person brief for the coach). Two things make it hers rather than generic:

- **Where she is right now.** `scenes.json → deep.daily_context` holds, for each time slot of a weekday
  and a weekend, **five possibilities** (the morning walk, which supermarket, which event, which workout,
  the private shrine routine at night, the doom-scrolling…). The brain picks one per *day and slot*, seeded
  by the date, so her afternoon does not change mid-conversation; the Setup page shows them as **[1]…[5]**.
  `current_scene` is where she is at home when you talk to her on the stage (voice or typed);
  `text_scene` is where she is when a message arrives from Discord or Telegram — out, phone in hand, you
  not next to her. The messengers service tags those turns with a `channel`, and the brain swaps the scene.
- **Identity tokens.** `{user_name}` and `{city}` may appear anywhere in the templates and scenes; they are
  filled from `config/build_f.json` (Setup → *You & Amika*, or the first-run wizard on the Use page).
  The relationship and speaking-style blocks also carry her one running gag (what she says when she sees
  you eating) — it is written in three places on purpose, so the surface, the deep and the coach all know it.

## Wipe, reset, first run

- **Wipe her memory** (Setup → Danger zone, type `WIPE`): the evidence store and the transcript go, with a
  backup under `memory_f/backups/`. She has to be idle (power the stage off first). A model call that began
  but never finished used to block this forever; the brain now retires such calls after 15 minutes.
- **Reset everything** (type `RESET`): the wipe, plus the four persona files restored from `brain/defaults/`
  and the identity fields cleared, so the first-run wizard plays again. Keys, bot tokens, voice and avatar
  settings are kept.
- **First run**: the Use page opens a wizard once (until `onboarded` is set in `build_f.json`): her face
  (a live crop of the Live2D stage) in a circle, and every line spoken in her voice (when a TTS server is configured) through
  `POST /api/tts_say` (one-shot synthesis on the gateway, lip-synced on the portrait). She asks your name —
  with a "hear her say it" preview and an optional **pronunciation guide** (Amika → Ameeka) that becomes the
  `role: user_name` rule in `config/word_replace.json`, so her voice says it that way from then on while
  her text keeps the real spelling — then your city and her clock, the OpenRouter key, and the same health
  check the top-right light shows (green *System Ready*, yellow *Warnings*, breathing red *System Failures*).
  The guide is also editable under Setup → You & Amika.

## What to customize (Setup → Personality)

| Knob | Where | Safe? |
|---|---|---|
| Her name / your name / your city / her clock | identity fields (config/build_f.json) | ✔ hot-applies; full effect after restart |
| Daily life (five possibilities per slot), mood, relationship stages, speaking style | `scenes.json` | ✔ free-form; use `{user_name}` for your name and `{city}` for your city |
| Backstory, persona prose, examples | the three templates | ✔ the prose, yes |
| FORMAT blocks (placeholders, vocab lines, SFX rule, 4-line format) | the three templates | ⚠ contract-checked on save — warnings tell you exactly what broke |
| Emotion vocabulary (69 keys) | `po_contract.py` (both copies) | ✖ wired through TTS, parser, banks and tests — change only with the whole chain |
| Memory budgets, history window, idle reflection | `config/build_f.json` | ✔ |

The template self-check runs at boot and on every save; problems are warnings, never a refusal to start
(`/api/build_f/status → template_check`).
