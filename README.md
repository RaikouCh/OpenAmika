<div align="center">

<img src="docs/images/amika-avatar.png" alt="Amika" width="180">

# OpenAmika

**Hi! I'm Amika** — MekaHime's AI companion, open source

[简体中文](README.zh-CN.md) | [日本語](README.ja.md) | **English** | [Tiếng Việt](README.vi.md) | [한국어](README.ko.md)

[![Made with Love](https://img.shields.io/badge/Made%20with-Love-ff69b4)](https://www.mekahime.com/openamika)
[![GitHub](https://img.shields.io/badge/GitHub-zeekk0%2FOpenAmika-181717?logo=github)](https://github.com/zeekk0/OpenAmika)
[![Release](https://img.shields.io/github/v/release/zeekk0/OpenAmika?logo=github&color=d8b4e2)](https://github.com/zeekk0/OpenAmika/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-43b581)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20(Linux%20untested)-0078D6?logo=windows&logoColor=white)](#what-you-need)
[![Python 3.11 | 3.12](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3119/)

[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-MekaHime%2FMekaHime__Amika-ffcc4d)](https://huggingface.co/MekaHime/MekaHime_Amika)
[![Discord](https://img.shields.io/badge/Discord-MekaHime-5865F2?logo=discord&logoColor=white)](https://discord.gg/mekahime)
[![Website](https://img.shields.io/badge/website-mekahime.com-d8b4e2)](https://www.mekahime.com/openamika)
[![Try Online](https://img.shields.io/badge/Try%20Online-mekahime.com%2Famika-e58fb8)](https://www.mekahime.com/amika)
[![Tests](https://github.com/zeekk0/OpenAmika/actions/workflows/tests.yml/badge.svg)](https://github.com/zeekk0/OpenAmika/actions/workflows/tests.yml)
[![GitHub stars](https://img.shields.io/github/stars/zeekk0/OpenAmika?style=social)](https://github.com/zeekk0/OpenAmika/stargazers)

</div>

## Install her: 7 steps

**Before you start:** Windows 10 or 11, an NVIDIA graphics card (RTX 20-series or newer, 8 GB of video memory) and
about 40 GB of free disk?

- **Yes** → STEP 1.
- **No** → talk to her in your browser instead: [mekahime.com/amika](https://www.mekahime.com/amika).

**Rather watch it?** The same 7 steps as a 3-minute video, with fixes and answers for when you get stuck:
[mekahime.com/openamikatutorial](https://www.mekahime.com/openamikatutorial).

### STEP 1 — Install Python 3.11 and Git

Takes about 5 minutes.

1. Click [python-3.11.9-amd64.exe](https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe). Open it.
   Tick **Add python.exe to PATH** (bottom of the first window). Click **Install Now**.
2. Click [Git-2.56.0.4-64-bit.exe](https://github.com/git-for-windows/git/releases/download/v2.56.0.windows.4/Git-2.56.0.4-64-bit.exe).
   Open it. Click **Next** until it says **Install**, click **Install**, then **Finish**.

You see: "Setup was successful" (Python) and "Completing the Git Setup Wizard" (Git).

### STEP 2 — Open PowerShell in the folder where she will live

1. Press the **Windows key**, type `powershell`, press **Enter**. A normal window: not "Run as administrator".
2. Copy the line below. Click into the blue window. **Right-click** (that pastes). Press **Enter**.

```powershell
cd C:\
```

You see: `PS C:\>` and a blinking cursor.

Any drive works: `cd D:\` puts her on D:. Short paths work best. Not inside OneDrive.

### STEP 3 — Download OpenAmika

Paste each line, press **Enter**, wait for `PS ...>` to come back. Takes about a minute.

```powershell
git clone https://github.com/zeekk0/OpenAmika.git
```

```powershell
cd OpenAmika
```

You see: `PS C:\OpenAmika>`.

- If you see `'git' is not recognized` → close this window, do STEP 2 again (a new window finds Git), then this step.
- If you see `destination path 'OpenAmika' already exists` → she is downloaded already: paste `cd OpenAmika` and go on.

### STEP 4 — Run the setup

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

Takes 15 to 60 minutes: about 11 GB of downloads. Leave the window open.

First it asks for a Hugging Face token: press **Enter** to skip, or paste a free *Read* token from
[huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (it makes the downloads much faster).

You see at the end: `OpenAmika setup summary`, lines starting with `OK`, then `Done. Next:`.

- If you see `The argument 'scripts\setup_windows.ps1' to the -File parameter does not exist` → this window is not
  in her folder. Paste `cd C:\OpenAmika` (or the `cd` line her setup printed), press **Enter**, run the line again.
- If you see `Python 3.11 was not found` → STEP 1 again, with **Add python.exe to PATH** ticked. Then a new window
  (STEP 2), `cd C:\OpenAmika`, and this line again.
- If the download crawls (about 50 KB/s) → press **Ctrl+C**, run the line again and paste a Hugging Face token when
  it asks. It goes on where it stopped.
- If a line starts with `!!` → do what that line says, then run the line again. Finished parts are skipped.

### STEP 5 — Her voice and her model

```powershell
envs\brain\Scripts\python.exe scripts\setup_tts.py
```

Takes 10 to 30 minutes: about 5.5 GB of downloads. It shows her license, then asks: type `yes`, press **Enter**.

You see: `OK voice MekaHime_Amika` and `OK Live2D model Amika`, then `Done. Next:`.

- If you see `not downloaded: her license was not accepted` → run the line again and type `yes`.
- If you see `'envs\brain\Scripts\python.exe' is not recognized` → this window is not in her folder
  (`cd C:\OpenAmika`), or STEP 4 did not finish.

### STEP 6 — Start her

```powershell
.\Start_OpenAmika.bat
```

Next time, just double-click `Start_OpenAmika.bat` in `C:\OpenAmika`.

Takes 1 to 3 minutes (the first start is the slowest).

You see: a window called **OpenAmika** with green rows. Your browser opens her page (http://localhost:53000) and her
first-run window asks your name and your city.

- If her window says `moved to … in settings.json (chat_port)` → Windows had reserved port 53000, so she took the
  next free one. Open the address at the top of her window.
- If her window stops on an error → it stays open and names its log (`logs\launcher.log`). Bring that file to the
  [Discord](https://discord.gg/mekahime).

### STEP 7 — Paste your OpenRouter key in her first-run window

1. On [openrouter.ai](https://openrouter.ai): sign in, open **Credits**, add a few dollars. OpenRouter is prepaid:
   a key alone is not enough.
2. Open **Keys** → **Create Key**. Copy the key (it starts with `sk-or-v1-`).
3. In her first-run window, at her brain: click **OpenRouter**, paste the key, click **Save key**.

You see: a green `✓ Key saved … · $5.00 of credit left`. Click **Next**. Click her page once (so the browser lets
her speak), press the power button, and talk.

- If you see `no credits` → add credits on openrouter.ai, then click **Save key** again.
- If a reply fails → the chat shows OpenRouter's own reason. A model that is gone: Setup → Brain →
  **Switch back to the OpenRouter preset**.

> **Downloaded the ZIP instead of `git clone`?** Unzip it. Open the inner folder (the one with `Start_OpenAmika.bat`
> in it). Right-click an empty spot → **Open in Terminal**. Then do STEP 4 to STEP 7.
> (Windows 10: click the folder's address bar, type `powershell`, press **Enter**.)

*STEP 1 to STEP 6 follow the step-by-step guide that **metro01** wrote for the MekaHime Discord's help desk.
Thank you, metro01!*

## Updating her (keeps her memory)

Her memory is in `memory_f` and `brain\memories`. Back them up before anything.

**I used git clone**

1. **STEP 1 — Stop her.** Double-click `Stop_OpenAmika.bat`.
2. **STEP 2 — Double-click `Update_OpenAmika.bat`** in her folder. It saves her memory and your settings to
   `backups\update-<date>.zip`, downloads the update and installs what changed. Type `yes` if her license is asked.

You see: `Updated. Start her: double-click Start_OpenAmika.bat`.

- If you see `She is running` → STEP 1 first.
- If it lists files "with your own changes" → your version is kept. Her memory is safe.

**No `Update_OpenAmika.bat` in her folder?** You installed her before v1.1.0 (9 November 2026). Do STEP 2 this
way, one time. Open her folder, right-click an empty spot → **Open in Terminal** (Windows 10: click the folder's
address bar, type `powershell`, press **Enter**). Paste each line and press **Enter**:

```powershell
git fetch origin
```

```powershell
git show origin/main:scripts/update_openamika.ps1 > scripts\update_once.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\update_once.ps1
```

It is the same update, with the same backup. After it, `Update_OpenAmika.bat` is in her folder.

**I downloaded the ZIP**

1. **STEP 1 — Stop her.** Double-click `Stop_OpenAmika.bat`.
2. **STEP 2 — Download and unzip the new ZIP** next to the old folder.
3. **STEP 3 — Copy these from the old folder into the new one** (the ones you have): `memory_f`, `brain\memories`,
   `settings.json`, `brain\.env`, `config\seed.json`, `config\ollama.json`, `config\voice_map.json`,
   `config\tools.json`, `config\messengers.json`.
4. **STEP 4 — Run the setup in the new folder**: STEP 4 and STEP 5 of the install, from the new folder. It is
   faster the second time.
5. **STEP 5 — Start her** from the new folder. She may ask your name and city again; her memories are all there.
   Delete the old folder once she remembers you.

## About her

Amika is a Live2D anime girl who talks with you by voice and text in real time, remembers you, and lives with you
in your city. She runs on your own PC, with OpenRouter or fully local with Ollama. A hosted version runs at
[mekahime.com/amika](https://www.mekahime.com/amika).

> 💖 If Amika makes your day better, give us a ⭐ on [GitHub](https://github.com/zeekk0/OpenAmika) — it helps more
> people find her! · Support the project: https://www.mekahime.com/donate

## What you need

- Windows 10 or 11 and an NVIDIA graphics card, RTX 20-series or newer, with a recent driver. Video memory (VRAM)
  is what counts, not your PC's RAM:

  | how she runs | her own parts | her language model | for example |
  |---|---|---|---|
  | **Semi-Local** (recommended) | about **5.5 GB** of video memory: her ears, memory and voice. An 8 GB card | on OpenRouter: none on your card | an RTX 3060 laptop runs her: her voice comes a few seconds after the text, and a user's bill read "only 2 cents so far" |
  | + her camera eyes | about 4.3 GB more: a 16 GB card | | |
  | **Fully Local** (Ollama) | 5.5 GB (about 10 GB with her eyes) | the rest: about 19 GB more for a 27B model | one 32 GB card (RTX 5090), or Ollama on a second PC |

- Python 3.11 (3.12 works too; 3.13 and newer do not, because her voice server needs numpy 1.26.4, which has no
  wheels for them) and Git: STEP 1.
- About 40 GB of free disk: a full setup takes about 37 GB (about 28 GB without her camera eyes), and
  `pip cache purge` gives back about 6 GB of it afterwards. It downloads about 16 GB and takes 30 to 60 minutes.
- An [OpenRouter](https://openrouter.ai) key with a few dollars of credit for her language model, or
  [Ollama](https://ollama.com) with a model of 27B or more and a graphics card big enough for it (see
  [Which language model?](#which-language-model)).

## Which language model?

Her ears, voice, memory and eyes always run on your PC. Her language model, the part that thinks and writes her
replies, runs one of two ways:

- **Semi-Local (recommended)**: through [OpenRouter](https://openrouter.ai) on your own key. In almost all cases
  this is the better choice: she uses the models she was tested with, answers fast, and it only costs a few dollars
  a month (about $1.50 if you talk 30 turns a day, about $5 at 100 turns a day).
- **Fully Local**: on your PC with [Ollama](https://ollama.com). Use a model of **27B parameters or more**; **70B or
  more** gives the full, reliable experience. Models smaller than 27B may be really bad: she loses her character,
  forgets what you told her and breaks her reply format (her first-run window and Setup → Brain warn you). A local
  model is also slower: all her thinking takes turns on it, so after you interrupt her, or while she saves a memory
  or reflects, a reply can take 5–50 s.

> **What OpenRouter is, and what it costs.** OpenRouter is one account for many AI models: with your key, she sends
> her thinking to the models she was tested with, and OpenRouter charges their prices. It is **prepaid**: add a few
> dollars of credit first. A key on an account with no credits makes every reply fail (her chat then says so). One
> exchange costs about **$0.002** (MekaHime's own ledger: $0.00165 a turn on the default models): 30 a day is about
> $1.50 a month, an hour of talking every day about $5. **A long day can reach 50 cents**: an hour of voice chat is
> about 100 turns, every turn sends her whole character and the memories it needs again (about 8,000 tokens), she
> reflects and writes memories between turns, and a helper (Hermes, nanoMuse) runs its own model on the same key.
> Your own figure is on the Use page, in the *Session cost* tile.

A local model needs its own video memory on top of the ~5.5 GB her ears, memory and voice use (~10 GB with her
eyes): about 19 GB for a 27B model such as `gemma3:27b`, 24 GB for a 32B one such as `qwen3:32b`, and 50 GB for a
70B one such as `qwen2.5:72b`. So one 32 GB card (RTX 5090) holds a 27B model next to all of her (a 32B one only with
her eyes off); a 24 GB card does not. A 70B model fits next to her only on a 72–96 GB workstation card. Otherwise run
Ollama on a second PC (the Setup page takes its address), or stay Semi-Local. Whichever model you run, pick one that
supports Chinese, since her prompts are written in it (`llama3.3:70b`, for one, does not). How to switch:
[Optional add-ons](#optional-add-ons).

**Local models tried with her** (Ollama sizes as ollama.com lists them; "loaded" is with her 16k context):

| model | Ollama | download | video memory, loaded | how it went |
|---|---|---|---|---|
| Gemma 4 26B MoE (26B, about 4B active per token) | `gemma4:26b` | 16–19 GB | about 21 GB | holds her character; the one model under 27B that does. A mixture of experts: a user ran it with 6–10 GB of video memory and the rest on the CPU |
| Qwen 2.5 72B | `qwen2.5:72b` | 47 GB | about 50 GB | the full experience: a 72–96 GB card, or a second PC |
| GLM 5 (744B, 40B active) | none as a local model (Ollama retired `glm-5` on 2026-07-15; its GLM 5.x tags are cloud ones) | – | about 450 GB at 4-bit: a multi-GPU server | her default deep model on OpenRouter, where it costs a few dollars a month |

## What she can see and control

| what | what she does with it | the switch |
|---|---|---|
| Your microphone | hears you while her power is on; speech recognition runs on your PC | power and mic buttons on the Use page |
| Your webcam (her eyes) | sees you only while you turn the camera on; a small model on your PC describes the picture, and only that description reaches her language model | the camera button on the Use page; `"vision": {"enabled": false}` in `settings.json` removes her eyes |
| Your screen and your PC (browser, files, email drafts) | only through a helper, Hermes Agent or nanoMuse, when you ask her for an errand; risky steps wait for your OK | Tools page: the helper's switch (off until you set one up) |
| Your smart home (Zigbee plugs) | switches only plugs you paired, only after you accepted the IoT safety statement | Tools page: the IoT switch; `IoT\Setup_IoT_admin.bat` is optional, only for this |
| Discord and Telegram | text only, through your own bot on your own server; only user ids you allow reach her | Setup → Text her |

Semi-Local, the text of what you say, her memories that the turn needs and her camera's description go to OpenRouter;
your voice and the camera pictures stay on your PC. Fully Local (and without a helper), nothing leaves your PC.

To start her memory over later: Setup page → Danger zone → **Wipe memory**. She forgets every conversation and fact,
and a backup stays in `memory_f\backups\`. If she is still talking, it waits a few seconds, then offers **Force
wipe** (she stops what she is doing). From a script: `envs\brain\Scripts\python.exe launch.py --wipe-memory`
(`--force` to stop her first; it also works while she is not running).

## Talk to her

Double-click `Start_OpenAmika.bat` in the OpenAmika folder (in PowerShell: `.\Start_OpenAmika.bat`). One console
starts all of her, and your browser opens **http://localhost:53000** when she is ready (if Windows reserved that
port, she moves to the next free one and her console shows the address): about a minute, a few more the very first
time. On your first visit she introduces herself and asks your name, your city and, if `brain\.env` has none yet,
your OpenRouter key. Then press the power button and talk, or type. Click the page once so the browser lets her
speak. When you go quiet she may say something, counted from the moment her voice stops; Setup → You & Amika →
"When you go quiet" sets it to Normal, Rare or Off.

The light at the top right of every page is her health: green means everything works; click it to see what is not.
Double-click `Stop_OpenAmika.bat` (or press Ctrl+C in her console) to stop her. To check everything without starting
anything, run `envs\brain\Scripts\python.exe launch.py --check`: it ends with `result: ready`, or names what to fix.

To update her: [Updating her](#updating-her-keeps-her-memory).

## If something goes wrong

| what you see | what to do |
|---|---|
| `The argument 'scripts\setup_windows.ps1' to the -File parameter does not exist` | Your window is not in her folder: `cd C:\OpenAmika` (a ZIP: the inner `OpenAmika-main` folder), then the line again. |
| `Python 3.11 was not found` | Install Python 3.11 (tick "Add python.exe to PATH"; 3.12 works too), open a new PowerShell window and run the setup again. |
| The downloads crawl (about 50 KB/s) | Hugging Face throttles downloads without a token. Ctrl+C, run the setup again, paste a free Read token from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) when it asks: it continues where it stopped. |
| `!! voice MekaHime_Amika  not downloaded: her license was not accepted` | Run `envs\brain\Scripts\python.exe scripts\setup_tts.py` again and type `yes`. |
| `!! voice MekaHime_Amika  Hugging Face refused the download (HTTP 401)` | Her files are not public yet, or your `HF_TOKEN` is wrong. Set a read token from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) in the same window (`$env:HF_TOKEN = "hf_..."`) and run the command again. |
| `download failed after 4 tries` or `Check the internet connection` | Run the same command again: it continues where it stopped. If huggingface.co cannot be reached from your network, set `$env:HF_ENDPOINT` to a Hugging Face mirror first; every file is still checked. |
| `does not see the GPU (CUDA)` | Update your NVIDIA driver and run the setup again. Without an NVIDIA card: `powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1 --cpu`. |
| `The filename or extension is too long` | The folder's path is too long for Windows: move OpenAmika to a short folder such as `C:\OpenAmika` and run the setup there. |
| `settings.json not found` | Run `powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1` first. |
| `No Live2D model yet` on the stage, or `!! Live2D model` / `!! her voice` in `launch.py --check` | Run `envs\brain\Scripts\python.exe scripts\setup_tts.py`. |
| `no OpenRouter key yet` (`launch.py --check`, the setup summary) | Paste your key in the first-run window, or on Setup → Brain. |
| Her console says `moved to … in settings.json`, or `[Errno 13] … 53000` | Windows reserved that port (Hyper-V, WSL2, Docker Desktop). She moves to the next free port by herself: open the address at the top of her console. |
| `!! TTS (voice)  port 8002 answers but has no voice MekaHime_Amika` | Another voice server uses her port (OpenSakura's uses 8002 too). Stop it, or give her another port: change `8002` in `tts_url` and in `services.tts` (`--port`, `health`) in `settings.json`. |
| Every reply fails | The chat shows the provider's reason: `no credits` (OpenRouter is prepaid: add a few dollars at [openrouter.ai/settings/credits](https://openrouter.ai/settings/credits)), a model OpenRouter no longer offers (Setup → Brain → "Switch back to the OpenRouter preset"), a wrong key (paste a new one on Setup → Brain: it works at once, no restart). |
| She answers in text but you hear nothing | Give her voice about 20 seconds after a start, then click the page once. The health light must show TTS green. |
| Her voice spells a word in CAPITALS letter by letter | Fixed: she lower-cases shouting before she speaks. An acronym she should spell goes into `"tts_keep_caps"` in `config/word_replace.json`. |
| Her voice stutters or is very slow | Close other programs that use the graphics card, or turn her eyes off: `"vision": {"enabled": false}` in `settings.json`. |
| On Ollama she is out of character, forgets things, or her replies come out broken | The model is too small. Use one of 27B or more (70B or more for the full experience), or go back to OpenRouter: Setup → Brain → OpenRouter → "Switch back to the OpenRouter preset". |
| On Ollama she answers very slowly | If `ollama ps` shows a CPU/GPU split instead of `100% GPU`, the model does not fit in your video memory next to her. With `100% GPU`, slow replies after you interrupt her, or while she saves a memory or reflects, are normal for a local model. See [Which language model?](#which-language-model). |
| Her console closes before you can read it | It stays open now after an error and names `logs\launcher.log`. |
| `Amika is busy` when you wipe her memory or reset everything | It waits a few seconds for her to finish; if she is still busy, press **Force wipe (she stops what she is doing)**. The backup is kept either way. |
| `Model selection is busy` on the Setup page | Press **Unlock** next to the message: she stops what she is doing, and the switch goes through. |
| The console's brain row (or the Setup page's `brain start`) is red | The row says why: the port is taken, the environment is broken, the model does not fit, or the key is missing. |
| A helper's card on the Tools page is red, or she says she cannot reach Hermes or nanoMuse | Run `envs\brain\Scripts\python.exe launch.py --check` and look at its `agent` and `hermes key` lines; every message and its fix is in [docs/TOOLS.md](docs/TOOLS.md#when-it-does-not-work). |

Every part writes a log in `logs\`. For anything else, run `envs\brain\Scripts\python.exe launch.py --diagnose`: it
writes one zip in `logs\` (the startup checks, the end of each log, your settings without keys, versions, free disk and
GPU memory). Attach it when you ask on [Discord](https://discord.gg/mekahime) or open an
[issue](https://github.com/zeekk0/OpenAmika/issues). Using an AI coding agent? Point it at
[README_IF_YOU_ARE_AI_AGENT.md](README_IF_YOU_ARE_AI_AGENT.md).

## Optional add-ons

- **Fully Local**: install [Ollama](https://ollama.com), run `ollama pull gemma3:27b` (17 GB; or another model of
  27B or more, see [Which language model?](#which-language-model)), then on the Setup page choose Brain → Ollama →
  Detect models → Use this model. No key needed. For Ollama on another PC, type its address there before Detect models.
- **Her helpers**: Hermes Agent or nanoMuse run errands for her, and her desk view shows what they do
  ([below](#her-helpers-hermes-and-nanomuse)). Any other MCP server works too, on the Tools page
  ([docs/TOOLS.md](docs/TOOLS.md)).
- **Smart home** (optional: nothing else needs it): Zigbee plugs she can switch ([IoT/README.md](IoT/README.md)).
  `IoT\Setup_IoT_admin.bat` installs what it needs as administrator; skip it if you have no Zigbee plugs. It stays
  off until you read and accept the IoT safety statement ([docs/IOT_DISCLAIMER.md](docs/IOT_DISCLAIMER.md)) on the
  Tools page. She runs on language models and can make mistakes: never connect heaters, locks, valves or anything
  that could cause harm.
- **Text her** on Discord or Telegram ([docs/MESSENGERS.md](docs/MESSENGERS.md)). Her bot lives on your own Discord
  server: the bot must share a server with you before a DM works.
- **Your phone**: `Tailscale_Serve_OpenAmika.bat` makes her reachable on your own devices over
  [Tailscale](https://tailscale.com).
- **Desktop pet**: she stands on your desktop by herself, always on top of your other windows. Press **Desktop pet**
  on the Use page ([below](#desktop-pet-mode)).

## Desktop pet mode

She can also stand on your desktop by herself: a see-through window with only her in it, on top of your other
programs, with her voice, lip-sync and expressions as on the Use page. Windows only.

**From the Use page (the easy way):** press **Desktop pet** at the top of her stage.

1. The first time, the page asks for one small install (pywebview, a few megabytes). Press **Install and open**.
2. Her window opens on your desktop and the conversation goes with her: if she was on, she is on there; if your
   microphone was on, it is on there.
3. The page now says *Amika is on your desktop*. Press **Bring her back here** and she is on the page again.

The button shows only in a browser on the PC that runs her (her window opens on that PC's desktop), so not on your
phone.

**Straight to the desktop:** double-click `Start_OpenAmika_Pet.bat` instead of `Start_OpenAmika.bat` (or run
`launch.py --pet`): when she is ready, her window opens instead of the browser page. This way does not install
anything by itself. Without the install the page opens in your browser as usual, and its **Desktop pet** button
does the install; or do it by hand, once:

```powershell
envs\brain\Scripts\python.exe -m pip install -r brain\requirements-pet.txt
```

Hover over her for a small bar: power, microphone, the full page, close. Click the microphone and talk as usual.
Drag her to move the window; the mouse wheel over her makes her bigger or smaller; she comes back where you left
her. Closing her window does not stop her: the **Desktop pet** button (or `envs\brain\Scripts\python.exe pet.py`)
opens it again, `Stop_OpenAmika.bat` stops everything.

- One conversation at a time: while she is on your desktop, the page waits for her. **Bring her back here** on the
  page, or the full-page button on her window, moves her back.
- Her desktop window has no text box: talk to her, or bring her back to the page to type.
- Meet her on the full page first: the first-run wizard, the camera, the background photo and her helpers' paper
  doll are there.
- The see-through corners of her window still take your clicks: keep it snug around her.

## Her helpers: Hermes and nanoMuse

She can hand errands to a helper program on your PC, [Hermes Agent](https://hermes-agent.nousresearch.com) or
[nanoMuse](https://github.com/nano-muse/nanoMuse): it searches the web, uses a browser and works with files. She
decides whether to help, gives the helper the task after she has answered you, relays its questions, and tells you
the result in her own words. While a helper is switched on, **her desk view (what she does right now)** sits at the
bottom right of her stage: MekaHime's little folded-paper doll acts out the helper's side, so you can see what is
being done for you. Each helper runs its own model on OpenRouter, and the key she uses works for it.

**Hermes Agent**: install it from a PowerShell window. This form of its installer asks no questions; the lines
after it do the setup OpenAmika needs:

```powershell
& ([scriptblock]::Create((irm https://hermes-agent.nousresearch.com/install.ps1))) -NonInteractive
```

Then, in a new PowerShell window:

```powershell
hermes model                                    # choose OpenRouter, paste your key, then "Enter custom model name": z-ai/glm-5
$key = [guid]::NewGuid().ToString('N')          # a random key for its API server
hermes config set API_SERVER_ENABLED true
hermes config set API_SERVER_KEY $key
hermes gateway stop                             # a Hermes already running reads the key only when it starts again
```

**nanoMuse**: clone it into the `Nanomuse` folder, give it a `config.toml` and put your key in its own vault; the
commands and the file are in [docs/TOOLS.md](docs/TOOLS.md#set-up-nanomuse).

**Connect them.** In the OpenAmika folder, run `Copy-Item config\tools.example.json config\tools.json` (only if
there is no `config\tools.json` yet) and `notepad config\tools.json`. Set `"enabled": true` at the top and in the
helper's entry. For nanoMuse, `"NANOMUSE_LANGUAGE"` is the language it answers in (`"en"`; or `"ja"`, `"zh-CN"`).
For Hermes, copy its key with this line and paste it (Ctrl+V) as `"HERMES_API_KEY"`:

```powershell
(Select-String -Path "$env:LOCALAPPDATA\hermes\.env" -Pattern '^API_SERVER_KEY=(.+)').Matches[0].Groups[1].Value | Set-Clipboard
```

Save and start her (`.\Start_OpenAmika.bat`): she starts her helpers herself. On the Tools page the helper's card
turns green (`agent online`).

**Her desk view.** Open the Use page: the little paper doll slides onto her stage. Ask her, for example, "Can you
have Hermes check tomorrow's weather?". She answers, types the task in her speech bubble, and the desk view takes
over: the doll thinks while the helper works, speaks the helper's steps in its own bubble, looks surprised when the
helper has a question or needs your OK (say yes or no, or click Approve on the Use page), and is happy when the
result comes, which she then tells you. It comes with `setup_tts.py` (`OK paper doll Host` in its summary).

Every step in detail, and what each message means: [docs/TOOLS.md](docs/TOOLS.md#her-helpers-set-up-hermes-agent-and-nanomuse).

## Licenses

- OpenAmika's code is **MIT** ([LICENSE](LICENSE)). Third-party parts keep their own licenses
  ([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)); the Live2D Cubism Core in `ui/vendor/` is not MIT.
- **Amika herself is not MIT.** Her character, art, voice, Live2D model and their weights, and the paper doll of her
  desk view ([MekaHime/MekaHime_Amika](https://huggingface.co/MekaHime/MekaHime_Amika)), belong to
  MekaHime Inc. and are free under a personal-use license: personal use only, 18+, no redistribution or re-hosting,
  and no training other models on them. Two creator rules: earn on social media (videos, streams, ads, memberships,
  sponsorships) with no limit, crediting MekaHime.AI visibly; and fan merch up to US$1,000 in total, as an
  individual, made from fan art you recreated yourself (never an original image MekaHime published on its website
  or social media), with "MekaHime.AI" on the visible side and a small "Fan Art" label. Any other commercial use needs a
  license from MekaHime (hi@mekahime.com). The [LICENSE](https://huggingface.co/MekaHime/MekaHime_Amika/blob/main/LICENSE)
  on Hugging Face governs.
- Hermes Agent (MIT) and nanoMuse (GPL-3.0-or-later) are separate programs you install yourself; OpenAmika only
  talks to them.
- Built on [SenseVoice](https://github.com/FunAudioLLM/SenseVoice), [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS),
  [bge-m3](https://huggingface.co/BAAI/bge-m3), [Qwen3-VL](https://github.com/QwenLM/Qwen3-VL),
  [pixi-live2d-display](https://github.com/guansss/pixi-live2d-display) with the
  [Live2D Cubism SDK](https://www.live2d.com/en/sdk/about/), [OpenRouter](https://openrouter.ai),
  [Ollama](https://ollama.com) and the [Model Context Protocol](https://modelcontextprotocol.io). Thank you.

## Support

Questions and bugs: [GitHub issues](https://github.com/zeekk0/OpenAmika/issues), hi@mekahime.com, or
[Discord](https://discord.gg/mekahime). Support the project: https://www.mekahime.com/donate

<p align="center">
  <a href="https://www.mekahime.com">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/images/mekahime-logo-white.png">
      <img src="docs/images/mekahime-logo-card.png" alt="MekaHime" width="220">
    </picture>
  </a>
</p>
