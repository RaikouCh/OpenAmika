<!-- Translated from README.md; keep in sync when README.md changes. -->
<div align="center">

<img src="docs/images/amika-avatar.png" alt="Amika" width="180">

# OpenAmika

**你好！我是 Amika**——MekaHime 的 AI 伴侣，现已开源

Amika 是一个 Live2D 二次元少女：她能用语音和文字与你实时聊天，会记住你，还和你一起住在你所在的城市。她运行在你自己的电脑上，可以接入 OpenRouter，也可以借助 Ollama 完全本地运行。你也可以在 [mekahime.com/amika](https://www.mekahime.com/amika) 体验在线托管版。

**简体中文** | [日本語](README.ja.md) | [English](README.md) | [Tiếng Việt](README.vi.md) | [한국어](README.ko.md)

[![Made with Love](https://img.shields.io/badge/Made%20with-Love-ff69b4)](https://www.mekahime.com/openamika)
[![GitHub](https://img.shields.io/badge/GitHub-zeekk0%2FOpenAmika-181717?logo=github)](https://github.com/zeekk0/OpenAmika)
[![Release](https://img.shields.io/github/v/release/zeekk0/OpenAmika?logo=github&color=d8b4e2)](https://github.com/zeekk0/OpenAmika/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-43b581)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20(Linux%20untested)-0078D6?logo=windows&logoColor=white)](#准备工作)
[![Python 3.11 | 3.12](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3119/)

[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-MekaHime%2FMekaHime__Amika-ffcc4d)](https://huggingface.co/MekaHime/MekaHime_Amika)
[![Discord](https://img.shields.io/badge/Discord-MekaHime-5865F2?logo=discord&logoColor=white)](https://discord.gg/mekahime)
[![Website](https://img.shields.io/badge/website-mekahime.com-d8b4e2)](https://www.mekahime.com/openamika)
[![Try Online](https://img.shields.io/badge/Try%20Online-mekahime.com%2Famika-e58fb8)](https://www.mekahime.com/amika)
[![Tests](https://github.com/zeekk0/OpenAmika/actions/workflows/tests.yml/badge.svg)](https://github.com/zeekk0/OpenAmika/actions/workflows/tests.yml)
[![GitHub stars](https://img.shields.io/github/stars/zeekk0/OpenAmika?style=social)](https://github.com/zeekk0/OpenAmika/stargazers)

</div>

## 安装：7 个步骤

**开始之前：** 你有 Windows 10 或 11、一张 NVIDIA 显卡（RTX 20 系列或更新，8 GB 显存）和约 40 GB 的空闲磁盘吗？

- **有** → 从 STEP 1 开始。
- **没有** → 直接在浏览器里和她聊：[mekahime.com/amika](https://www.mekahime.com/amika)。

**想看视频？** 同样的 7 个步骤做成了 3 分钟的视频，还有常见问题和解决办法（英文页面）：[mekahime.com/openamikatutorial](https://www.mekahime.com/openamikatutorial)。

### STEP 1 — 安装 Python 3.11 和 Git

约 5 分钟。

1. 点击 [python-3.11.9-amd64.exe](https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe)，打开它。勾选第一个窗口底部的 **Add python.exe to PATH**，点击 **Install Now**。
2. 点击 [Git-2.56.0.4-64-bit.exe](https://github.com/git-for-windows/git/releases/download/v2.56.0.windows.4/Git-2.56.0.4-64-bit.exe)，打开它。一直点 **Next** 直到出现 **Install**，点 **Install**，最后点 **Finish**。

你会看到：“Setup was successful”（Python）和“Completing the Git Setup Wizard”（Git）。

### STEP 2 — 在她要住的文件夹里打开 PowerShell

1. 按 **Windows 键**，输入 `powershell`，按 **回车**。用普通窗口，不要“以管理员身份运行”。
2. 复制下面这一行，点一下蓝色窗口，**右键**（这样就粘贴了），按 **回车**。

```powershell
cd C:\
```

你会看到：`PS C:\>` 和闪烁的光标。

任何磁盘都可以：`cd D:\` 就把她放在 D 盘。路径越短越好。不要放在 OneDrive 里。

### STEP 3 — 下载 OpenAmika

每次粘贴一行，按 **回车**，等 `PS ...>` 重新出现。约 1 分钟。

```powershell
git clone https://github.com/zeekk0/OpenAmika.git
```

```powershell
cd OpenAmika
```

你会看到：`PS C:\OpenAmika>`。

- 如果看到 `'git' is not recognized` → 关掉这个窗口，从 STEP 2 重新开始（新窗口才找得到 Git），再做这一步。
- 如果看到 `destination path 'OpenAmika' already exists` → 已经下载过了：粘贴 `cd OpenAmika` 继续。

### STEP 4 — 运行安装

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

需要 15 到 60 分钟，下载约 11 GB。窗口保持打开。

它会先问 Hugging Face 令牌：按 **回车** 跳过，或者粘贴在 [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) 免费创建的 *Read* 令牌（下载会快很多）。

最后你会看到：`OpenAmika setup summary`、以 `OK` 开头的行，然后是 `Done. Next:`。

- 如果看到 `The argument 'scripts\setup_windows.ps1' to the -File parameter does not exist` → 这个窗口不在她的文件夹里。粘贴 `cd C:\OpenAmika`（或安装程序打印出的那行 `cd`），按 **回车**，再运行一次。
- 如果看到 `Python 3.11 was not found` → 重新做 STEP 1，勾选 **Add python.exe to PATH**。然后开一个新窗口（STEP 2），`cd C:\OpenAmika`，再运行这一行。
- 如果下载很慢（约 50 KB/s）→ 按 **Ctrl+C**，再运行这一行，问令牌时粘贴 Hugging Face 令牌。它会从停下的地方继续。
- 如果有一行以 `!!` 开头 → 照那一行说的做，然后再运行一次。已完成的部分会跳过。

### STEP 5 — 她的声音和模型

```powershell
envs\brain\Scripts\python.exe scripts\setup_tts.py
```

需要 10 到 30 分钟，下载约 5.5 GB。它先显示她的许可证，然后询问：输入 `yes`，按 **回车**。

你会看到：`OK voice MekaHime_Amika` 和 `OK Live2D model Amika`，然后是 `Done. Next:`。

- 如果看到 `not downloaded: her license was not accepted` → 再运行一次，输入 `yes`。
- 如果看到 `'envs\brain\Scripts\python.exe' is not recognized` → 这个窗口不在她的文件夹里（`cd C:\OpenAmika`），或者 STEP 4 没有完成。

### STEP 6 — 启动她

```powershell
.\Start_OpenAmika.bat
```

以后只要双击 `C:\OpenAmika` 里的 `Start_OpenAmika.bat`。

需要 1 到 3 分钟（第一次最慢）。

你会看到：一个叫 **OpenAmika** 的窗口，里面是绿色的行。浏览器打开她的页面（http://localhost:53000），首次使用窗口会问你的名字和你所在的城市。

- 如果她的窗口显示 `moved to … in settings.json (chat_port)` → Windows 预留了 53000 端口，她换到了下一个空闲端口。打开她窗口顶部显示的地址。
- 如果她的窗口因错误停下 → 窗口会保持打开，并显示日志（`logs\launcher.log`）。把这个文件带到 [Discord](https://discord.gg/mekahime)。

### STEP 7 — 在首次使用窗口里粘贴你的 OpenRouter 密钥

1. 在 [openrouter.ai](https://openrouter.ai) 登录，打开 **Credits**，充几美元。OpenRouter 是预付费的：只有密钥是不够的。
2. 打开 **Keys** → **Create Key**，复制密钥（以 `sk-or-v1-` 开头）。
3. 在她的首次使用窗口里，到“大脑”那一步：点 **OpenRouter**，粘贴密钥，点 **Save key**。

你会看到：绿色的 `✓ Key saved … · $5.00 of credit left`。点 **Next**，再点一下她的页面（让浏览器允许她说话），按电源按钮，开始聊天。

- 如果看到 `no credits` → 在 openrouter.ai 充值，然后再点一次 **Save key**。
- 如果回复失败 → 聊天里会显示 OpenRouter 自己给出的原因。如果是模型下架了：Setup → Brain → **Switch back to the OpenRouter preset**。

> **下载的是 ZIP 而不是 `git clone`？** 解压后，打开里面那一层文件夹（有 `Start_OpenAmika.bat` 的那个）。在空白处右键 → **在终端中打开**。然后做 STEP 4 到 STEP 7。
> （Windows 10：点文件夹的地址栏，输入 `powershell`，按 **回车**。）

*STEP 1 到 STEP 6 参考了 **metro01** 在 MekaHime Discord 帮助频道写的分步指南。谢谢你，metro01！*

## 更新她（保留她的记忆）

她的记忆在 `memory_f` 和 `brain\memories` 里。做任何事之前先备份它们。

**用 git clone 安装的**

1. **STEP 1 — 停止她。** 双击 `Stop_OpenAmika.bat`。
2. **STEP 2 — 双击她文件夹里的 `Update_OpenAmika.bat`。** 它会把她的记忆和你的设置保存到 `backups\update-<日期>.zip`，下载更新，并安装有变化的部分。如果问到许可证，输入 `yes`。

你会看到：`Updated. Start her: double-click Start_OpenAmika.bat`。

- 如果看到 `She is running` → 先做 STEP 1。
- 如果它列出“with your own changes”的文件 → 保留的是你的版本。她的记忆是安全的。

**她的文件夹里没有 `Update_OpenAmika.bat`？** 说明她是在 v1.1.0（2026 年 11 月 9 日）之前安装的。这一次请这样做 STEP 2：打开她的文件夹，在空白处右键 → **在终端中打开**（Windows 10：点文件夹的地址栏，输入 `powershell`，按 **回车**）。把下面每一行粘贴进去，按 **回车**：

```powershell
git fetch origin
```

```powershell
git show origin/main:scripts/update_openamika.ps1 > scripts\update_once.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\update_once.ps1
```

更新的内容一样，备份也一样。做完之后，她的文件夹里就有 `Update_OpenAmika.bat` 了。

**下载 ZIP 安装的**

1. **STEP 1 — 停止她。** 双击 `Stop_OpenAmika.bat`。
2. **STEP 2 — 下载新的 ZIP，解压在旧文件夹旁边。**
3. **STEP 3 — 把下面这些从旧文件夹复制到新文件夹**（有的才复制）：`memory_f`、`brain\memories`、`settings.json`、`brain\.env`、`config\seed.json`、`config\ollama.json`、`config\voice_map.json`、`config\tools.json`、`config\messengers.json`。
4. **STEP 4 — 在新文件夹里运行安装**：在新文件夹里做安装的 STEP 4 和 STEP 5。第二次会快一些。
5. **STEP 5 — 从新文件夹启动她。** 她可能会再问一次你的名字和城市，但她的记忆都在。确认她还记得你之后，再删除旧文件夹。

> 💖 如果 Amika 让你的一天变得更美好，就在 [GitHub](https://github.com/zeekk0/OpenAmika) 上给我们点个 ⭐ 吧——这能帮更多人找到她！· 支持本项目：https://www.mekahime.com/donate

## 准备工作

- Windows 10 或 11，以及一块 NVIDIA 显卡（RTX 20 系列或更新，显存 8 GB 以上；她的摄像头“眼睛”需要 16 GB），驱动保持较新
- [Python 3.11](https://www.python.org/downloads/release/python-3119/)（安装时勾选 **Add python.exe to PATH**；3.12 也可以。3.13 及更新版本不行：她的语音服务器需要 numpy 1.26.4，而它没有这些版本的 wheel）和 [Git](https://git-scm.com/download/win)
- 约 40 GB 可用磁盘空间（装好后约占 37 GB，不装摄像头“眼睛”约 28 GB；装完后 `pip cache purge` 能腾出约 6 GB）。安装过程会下载约 16 GB，耗时 30–60 分钟
- 一个给语言模型用的 [OpenRouter](https://openrouter.ai) 密钥（推荐，每月只需几美元）；或者 [Ollama](https://ollama.com)，外加一块跑得动 27B 及以上模型的显卡（见[用哪种语言模型？](#用哪种语言模型)）

## 用哪种语言模型？

她的耳朵、声音、记忆和眼睛始终运行在你的电脑上。负责思考、写出回复的那部分——语言模型——有两种运行方式：

- **半本地（推荐）**：用你自己的密钥，通过 [OpenRouter](https://openrouter.ai) 运行。绝大多数情况下这都是更好的选择：用的是她经过测试的模型，回复也快，每月只要几美元（每天聊 30 轮约 1.5 美元，100 轮约 5 美元）。
- **完全本地**：用 [Ollama](https://ollama.com) 在你的电脑上运行。请使用 **27B（270 亿参数）及以上** 的模型；想要完整、稳定的体验，请用 **70B 及以上**。小于 27B 的模型质量可能非常差：她会丢掉自己的性格、忘记你说过的话、把回复格式弄乱。本地运行也更慢：她所有的思考都要在这一个模型上排队进行，所以在你打断她之后，或者在她保存记忆、回想对话的时候，一次回复可能要等 5–50 秒。

本地模型除了她的耳朵、记忆和声音占用的约 6 GB 显存（开启眼睛时约 10 GB），还需要自己的一份显存：像 `gemma3:27b` 这样的 27B 模型约 19 GB，像 `qwen3:32b` 这样的 32B 模型约 24 GB，像 `qwen2.5:72b` 这样的 70B 模型约 50 GB。也就是说，一块 32 GB 显卡（RTX 5090）能同时装下 27B 模型和她的全部功能（32B 模型只有关掉她的眼睛才行），24 GB 显卡则装不下。70B 模型只有 72–96 GB 的工作站显卡才能和她放在同一块卡上。其他情况下，请在第二台电脑上运行 Ollama（Setup 页面可以填写它的地址），或者继续使用半本地方式。不管用哪个模型，都请选择支持中文的：她的提示词是用中文写的（比如 `llama3.3:70b` 就不支持中文）。切换方法见[可选功能](#可选功能)。

## 安装

打开 PowerShell（普通窗口，不要以管理员身份运行），逐行运行下面的命令。它们会把她安装在 `C:\OpenAmika`——一个不被 OneDrive 同步的短路径文件夹：

```powershell
cd C:\
git clone https://github.com/zeekk0/OpenAmika.git
cd OpenAmika
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1   # 她的大脑、耳朵、记忆和眼睛
envs\brain\Scripts\python.exe scripts\setup_tts.py                   # 她的声音、Live2D 模型和纸娃娃：输入 yes
.\Start_OpenAmika.bat                                                # 启动她
```

她的声音、Live2D 模型和纸娃娃依照 MekaHime 的个人使用许可证免费提供（见[许可证](#许可证)）；`setup_tts.py` 这一行会先显示许可证内容，只有在你输入 `yes` 之后才会下载她的文件。

两条安装命令最后都会输出一份汇总：每个部分一行，完成显示 `OK`，有问题显示 `!!` 并附上解决方法，`--` 只是提示信息（例如还没有 OpenRouter 密钥：第一次打开页面时会请你填写）。再次运行同一条命令会从中断处继续，已完成的部分会跳过。`setup_tts.py` 的汇总里出现 `OK voice MekaHime_Amika` 和 `OK Live2D model Amika`，就说明她的声音和身体都已就位；`OK paper doll Host` 是替她的帮手站在舞台上的纸娃娃（见[她的帮手](#她的帮手hermes-和-nanomuse)）。

以后想让她的记忆重新开始：Setup 页面 → Danger zone → **Wipe memory**。她会忘掉所有对话和事实，备份保存在 `memory_f\backups\`。如果她还在说话，会先等几秒；还没结束的话，会出现 **Force wipe**（她会停下正在做的事）。在脚本里可以用 `envs\brain\Scripts\python.exe launch.py --wipe-memory`（加 `--force` 先让她停下；她没在运行时也能用）。

## 和她聊天

双击 OpenAmika 文件夹里的 `Start_OpenAmika.bat`（在 PowerShell 里运行 `.\Start_OpenAmika.bat`）。它会打开一个控制台窗口并启动她的全部组件；准备就绪后，浏览器会打开 **http://localhost:53000**（大约一分钟，第一次会多几分钟）。第一次打开时，她会先做自我介绍，问你的名字和所在城市；如果 `brain\.env` 里还没有密钥，也会请你填入 OpenRouter 密钥。之后按下电源按钮就可以和她说话，或者打字。请先在页面上点击一次，浏览器才会允许她发出声音。你一直不说话时，她可能会主动开口，从她的声音停下那一刻开始计时；在 Setup → You & Amika →「When you go quiet」里可以选 Normal、Rare 或 Off。

每个页面右上角的指示灯显示她的状态：绿色表示一切正常，点击它可以查看哪里有问题。双击 `Stop_OpenAmika.bat`（或在她的控制台里按 Ctrl+C）停止她。如果想在不启动任何东西的情况下检查一遍，运行 `envs\brain\Scripts\python.exe launch.py --check`：最后会显示 `result: ready`，或者列出需要修复的地方。

更新她：先停止她，在 OpenAmika 文件夹里运行 `git stash`、`git pull`、`git stash pop`（会保留你的名字、所在城市和你的修改），再把两条安装命令各运行一次（只会获取有变化的部分）。

## 遇到问题时

| 你看到的信息 | 解决方法 |
|---|---|
| `Python 3.11 was not found` | 安装 Python 3.11（勾选 “Add python.exe to PATH”），打开一个新的 PowerShell 窗口，重新运行安装。 |
| `!! voice MekaHime_Amika  not downloaded: her license was not accepted` | 重新运行 `envs\brain\Scripts\python.exe scripts\setup_tts.py`，并输入 `yes`。 |
| `!! voice MekaHime_Amika  Hugging Face refused the download (HTTP 401)` | 她的文件还没有公开，或者你的 `HF_TOKEN` 不对。在同一个窗口里设置 [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) 上的只读令牌（`$env:HF_TOKEN = "hf_..."`），再运行一次同一条命令。 |
| `download failed after 4 tries` 或 `Check the internet connection` | 再运行一次同一条命令，会从中断处继续。如果你的网络连不上 huggingface.co，先把 `$env:HF_ENDPOINT` 设为一个 Hugging Face 镜像；每个文件照样会被校验。 |
| `does not see the GPU (CUDA)` | 更新 NVIDIA 驱动后重新运行安装。没有 NVIDIA 显卡时：`powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1 --cpu`。 |
| `The filename or extension is too long` | 文件夹路径对 Windows 来说太长了：把 OpenAmika 移到 `C:\OpenAmika` 这样的短路径文件夹，再在那里运行安装。 |
| `settings.json not found` | 先运行 `powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1`。 |
| 舞台上显示 `No Live2D model yet`，或 `launch.py --check` 里出现 `!! Live2D model` / `!! her voice` | 运行 `envs\brain\Scripts\python.exe scripts\setup_tts.py`。 |
| `no OpenRouter key yet`（`launch.py --check` 或安装汇总中） | 在首次运行的向导里粘贴密钥，或写在 `brain\.env` 的 `OPENROUTER_API_KEY=` 后面。 |
| `!! TTS (voice)  port 8002 answers but has no voice MekaHime_Amika` | 另一个语音服务器占用了她的端口（OpenSakura 的语音服务器也用 8002）。关掉它，或者给她换个端口：把 `settings.json` 里 `tts_url` 和 `services.tts`（`--port` 与 `health`）中的 `8002` 改成别的端口。 |
| 她用文字回复，但听不到声音 | 启动后等大约 20 秒，再在页面上点击一次。指示灯里的 TTS 必须是绿色。 |
| 她的声音断断续续或非常慢 | 关闭其他占用显卡的程序，或者在 `settings.json` 里设置 `"vision": {"enabled": false}` 关掉她的眼睛。 |
| 用 Ollama 时她不像她自己、记不住事，或者回复格式乱了 | 模型太小了。请换用 27B 及以上的模型（想要完整、稳定的体验用 70B 及以上），或者切回 OpenRouter：Setup → Brain → OpenRouter → “Switch back to the OpenRouter preset”。 |
| 用 Ollama 时她回复得非常慢 | 如果 `ollama ps` 显示的是 CPU/GPU 比例而不是 `100% GPU`，说明模型和她一起放不进显存。如果显示 `100% GPU`，那么在你打断她之后，或者在她保存记忆、回想对话的时候，回复变慢是本地模型的正常现象。见[用哪种语言模型？](#用哪种语言模型)。 |
| 清除记忆或全部重置时提示 `Amika is busy` | 它会先等她说完几秒；还没结束的话，点 **Force wipe (she stops what she is doing)**。两种情况下备份都会保留。 |
| Setup 页面提示 `Model selection is busy` | 点消息旁边的 **Unlock**：她会停下正在做的事，切换就能完成。 |
| 控制台里 brain 那一行（或 Setup 页面的 `brain start`）是红色 | 那一行会写明原因：端口被占用、环境损坏、模型放不下，或者缺少密钥。 |
| Tools 页面上帮手的卡片是红色的，或者她说联系不上 Hermes 或 nanoMuse | 运行 `envs\brain\Scripts\python.exe launch.py --check`，看 `agent` 和 `hermes key` 那几行；每条信息的含义和解决方法见 [docs/TOOLS.md](docs/TOOLS.md#when-it-does-not-work)。 |

每个组件的日志都在 `logs\` 里。其他问题请先运行 `envs\brain\Scripts\python.exe launch.py --diagnose`：它会在 `logs\` 里生成一个 zip（启动检查、每个日志的末尾、去掉密钥的设置、版本、剩余磁盘和显存），提问时附上它，可以到 [Discord](https://discord.gg/mekahime) 提问，或提交 [issue](https://github.com/zeekk0/OpenAmika/issues)。如果你在用 AI 编程助手，请让它阅读 [README_IF_YOU_ARE_AI_AGENT.md](README_IF_YOU_ARE_AI_AGENT.md)。

## 可选功能

- **完全本地运行**：安装 [Ollama](https://ollama.com)，运行 `ollama pull gemma3:27b`（17 GB；也可以用其他 27B 及以上的模型，见[用哪种语言模型？](#用哪种语言模型)），然后在 Setup 页面选择 Brain → Ollama → Detect models → Use this model。不需要密钥。如果 Ollama 运行在另一台电脑上，请在按 Detect models 之前先填写它的地址。
- **她的帮手**：Hermes Agent 或 nanoMuse 替她跑腿，纸娃娃在舞台上站在她身边（[见下文](#她的帮手hermes-和-nanomuse)）。其他 MCP 服务器也可以在 Tools 页面使用（[docs/TOOLS.md](docs/TOOLS.md)）。
- **智能家居**：她可以开关的 Zigbee 插座（[IoT/README.md](IoT/README.md)）。在你于 Tools 页面阅读并接受 IoT 安全声明（[docs/IOT_DISCLAIMER.md](docs/IOT_DISCLAIMER.md)）之前，它始终关闭。她运行在大语言模型之上，可能出错：绝对不要连接取暖器、门锁、阀门或任何可能造成危险的设备。
- **用文字找她**：通过 Discord 或 Telegram（[docs/MESSENGERS.md](docs/MESSENGERS.md)）。
- **用手机访问**：`Tailscale_Serve_OpenAmika.bat` 可以让你通过 [Tailscale](https://tailscale.com) 在自己的设备上访问她。

## 她的帮手：Hermes 和 nanoMuse

她可以把跑腿的事交给你电脑上的帮手程序——[Hermes Agent](https://hermes-agent.nousresearch.com) 或 [nanoMuse](https://github.com/nano-muse/nanoMuse)：它们会上网搜索、操作浏览器、处理文件。帮不帮由她决定：她先回答你，再把事情交给帮手，替它转达问题，最后用自己的话把结果告诉你。帮手开着的时候，MekaHime 的纸娃娃会站在她舞台的右下角，演帮手那一方。每个帮手都在 OpenRouter 上用自己的模型；她现在用的密钥就可以。

**Hermes Agent**：在 PowerShell 窗口里安装。这种写法的安装程序不会问任何问题，OpenAmika 需要的设置由后面几行完成：

```powershell
& ([scriptblock]::Create((irm https://hermes-agent.nousresearch.com/install.ps1))) -NonInteractive
```

装好后，在一个新的 PowerShell 窗口里：

```powershell
hermes model                                    # 选 OpenRouter，粘贴你的密钥，再选 “Enter custom model name”，输入 z-ai/glm-5
$key = [guid]::NewGuid().ToString('N')          # 给它的 API 服务器生成一个随机密钥
hermes config set API_SERVER_ENABLED true
hermes config set API_SERVER_KEY $key
hermes gateway stop                             # 已经在运行的 Hermes 要重新启动后才会读到这个密钥
```

**nanoMuse**：把它克隆到 `Nanomuse` 文件夹，给它写一个 `config.toml`，再把密钥存进它自己的保险库（vault）；命令和文件内容见 [docs/TOOLS.md](docs/TOOLS.md#set-up-nanomuse)。

**连接。** 在 OpenAmika 文件夹里运行 `Copy-Item config\tools.example.json config\tools.json`（只在还没有 `config\tools.json` 时）和 `notepad config\tools.json`。把最上面和帮手那一项的 `"enabled"` 改成 `true`。如果是 nanoMuse，再把 `"NANOMUSE_LANGUAGE"` 改成 `"zh-CN"`（这样它会用中文回复）。如果是 Hermes，用下面这行复制它的密钥，再粘贴（Ctrl+V）到 `"HERMES_API_KEY"`：

```powershell
(Select-String -Path "$env:LOCALAPPDATA\hermes\.env" -Pattern '^API_SERVER_KEY=(.+)').Matches[0].Groups[1].Value | Set-Clipboard
```

保存后启动她（`.\Start_OpenAmika.bat`），她会自己启动帮手。Tools 页面上这个帮手的卡片会变成绿色（`agent online`）。

**见见纸娃娃。** 打开 Use 页面，纸娃娃会滑进她的舞台。试着问她，比如“能让 Hermes 查一下明天的天气吗？”。她先回答你，在气泡里打出要交代的事，接下来就轮到纸娃娃了：帮手干活时它在思考，帮手的每一步它都用自己的气泡说出来；帮手有问题要问或需要你同意时，它会露出吃惊的样子（直接说“好”或“不行”，或在 Use 页面点 Approve）；结果到了它会很开心，然后她把结果告诉你。纸娃娃由 `setup_tts.py` 一起安装（汇总里显示 `OK paper doll Host`）。

每一步的详细说明，以及每条信息的含义：[docs/TOOLS.md](docs/TOOLS.md#her-helpers-set-up-hermes-agent-and-nanomuse)

## 许可证

- OpenAmika 的代码采用 **MIT** 许可证（[LICENSE](LICENSE)）。第三方部分遵循各自的许可证（[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)）；`ui/vendor/` 中的 Live2D Cubism Core 不是 MIT。
- **Amika 本身不是 MIT。** 她的角色、美术、声音、Live2D 模型及其权重，以及替她的帮手站台的纸娃娃（[MekaHime/MekaHime_Amika](https://huggingface.co/MekaHime/MekaHime_Amika)）归 MekaHime Inc. 所有，依照个人使用许可证免费提供：仅限个人使用，须年满 18 岁，不得再分发或重新托管，不得用于训练其他模型。另有两条创作者规则：在社交媒体上（视频、直播、广告、会员、赞助）获得收入不设上限，须清晰可见地注明 MekaHime.AI；以个人身份制作同人周边，总额不超过 1,000 美元，须使用你自己重新创作的同人图（不得使用 MekaHime 在官网或社交媒体上发布的原图），可见的一面须印有“MekaHime.AI”和一个小小的“Fan Art”标识。其他任何商业用途都需要 MekaHime 的授权（hi@mekahime.com）。以 Hugging Face 上的 [LICENSE](https://huggingface.co/MekaHime/MekaHime_Amika/blob/main/LICENSE) 为准。
- Hermes Agent（MIT）和 nanoMuse（GPL-3.0-or-later）是你自己安装的独立程序；OpenAmika 只与它们通信。
- 本项目构建于 [SenseVoice](https://github.com/FunAudioLLM/SenseVoice)、[GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)、[bge-m3](https://huggingface.co/BAAI/bge-m3)、[Qwen3-VL](https://github.com/QwenLM/Qwen3-VL)、[pixi-live2d-display](https://github.com/guansss/pixi-live2d-display) 与 [Live2D Cubism SDK](https://www.live2d.com/en/sdk/about/)、[OpenRouter](https://openrouter.ai)、[Ollama](https://ollama.com) 和 [Model Context Protocol](https://modelcontextprotocol.io) 之上。谢谢你们。

## 支持

问题和 bug 反馈：[GitHub issues](https://github.com/zeekk0/OpenAmika/issues)、hi@mekahime.com，或 [Discord](https://discord.gg/mekahime)。支持本项目：https://www.mekahime.com/donate

<p align="center">
  <a href="https://www.mekahime.com">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/images/mekahime-logo-white.png">
      <img src="docs/images/mekahime-logo-card.png" alt="MekaHime" width="220">
    </picture>
  </a>
</p>
