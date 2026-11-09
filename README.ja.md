<!-- Translated from README.md; keep in sync when README.md changes. -->
<div align="center">

<img src="docs/images/amika-avatar.png" alt="Amika" width="180">

# OpenAmika

**こんにちは、Amikaです！** — MekaHimeのAIコンパニオン、オープンソース版です

Amikaは、声とテキストでリアルタイムにおしゃべりしてくれるLive2Dのアニメ少女です。あなたのことを覚えていて、あなたの街で一緒に暮らしています。動くのはあなた自身のPCの上で、OpenRouterを使うことも、Ollamaで完全ローカルにすることもできます。ホスト版も[mekahime.com/amika](https://www.mekahime.com/amika)で動いています。

[简体中文](README.zh-CN.md) | **日本語** | [English](README.md) | [Tiếng Việt](README.vi.md)

[![Made with Love](https://img.shields.io/badge/Made%20with-Love-ff69b4)](https://www.mekahime.com/openamika)
[![GitHub](https://img.shields.io/badge/GitHub-zeekk0%2FOpenAmika-181717?logo=github)](https://github.com/zeekk0/OpenAmika)
[![Release](https://img.shields.io/github/v/release/zeekk0/OpenAmika?logo=github&color=d8b4e2)](https://github.com/zeekk0/OpenAmika/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-43b581)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20(Linux%20untested)-0078D6?logo=windows&logoColor=white)](#必要なもの)
[![Python 3.11](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3119/)

[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-MekaHime%2FMekaHime__Amika-ffcc4d)](https://huggingface.co/MekaHime/MekaHime_Amika)
[![Discord](https://img.shields.io/badge/Discord-MekaHime-5865F2?logo=discord&logoColor=white)](https://discord.gg/mekahime)
[![Website](https://img.shields.io/badge/website-mekahime.com-d8b4e2)](https://www.mekahime.com/openamika)
[![Try Online](https://img.shields.io/badge/Try%20Online-mekahime.com%2Famika-e58fb8)](https://www.mekahime.com/amika)
[![Tests](https://github.com/zeekk0/OpenAmika/actions/workflows/tests.yml/badge.svg)](https://github.com/zeekk0/OpenAmika/actions/workflows/tests.yml)
[![GitHub stars](https://img.shields.io/github/stars/zeekk0/OpenAmika?style=social)](https://github.com/zeekk0/OpenAmika/stargazers)

</div>

> 💖 Amikaのおかげで毎日が少しでも楽しくなったら、[GitHub](https://github.com/zeekk0/OpenAmika)で⭐をつけてもらえるとうれしいです。もっとたくさんの人が彼女に出会えます！ · プロジェクトへのご支援: https://www.mekahime.com/donate

## 必要なもの

- Windows 10または11と、NVIDIAのグラフィックカード（RTX 20シリーズ以降、ビデオメモリ8 GB以上。カメラで「見る」機能には16 GB）、そして新しいドライバー
- [Python 3.11](https://www.python.org/downloads/release/python-3119/)（インストール時に **Add python.exe to PATH** にチェック）と[Git](https://git-scm.com/download/win)
- 約45 GBの空きディスク。セットアップでは約15〜20 GBをダウンロードし、30〜60分ほどかかります
- 言語モデル用の[OpenRouter](https://openrouter.ai)のキー（おすすめ。費用は月に数ドルほどです）。または[Ollama](https://ollama.com)と、27B以上のモデルを動かせるグラフィックカード（[どの言語モデルを使う？](#どの言語モデルを使う)を参照）

## どの言語モデルを使う？

彼女の耳・声・記憶・目は、いつもあなたのPCで動きます。考えて返事を書く部分、つまり言語モデルの動かし方は2通りあります。

- **セミローカル（おすすめ）**：あなた自身のキーで[OpenRouter](https://openrouter.ai)を使います。ほとんどの場合はこちらのほうが良い選択です。彼女がテストされたモデルで動き、返事も速く、費用は月に数ドルだけです（1日30ターン話して約1.5ドル、100ターンで約5ドル）。
- **完全ローカル**：[Ollama](https://ollama.com)を使って、あなたのPCの上で動かします。**27B（パラメーター数270億）以上**のモデルを使ってください。フルで安定した体験には**70B以上**がおすすめです。27Bより小さいモデルは品質がかなり悪くなることがあり、彼女らしさが崩れたり、話したことを忘れたり、返事の形式が壊れたりします。また、ローカルのモデルでは返事が遅くなります。彼女の思考はすべてこのモデルが1つずつ順番に処理するため、話をさえぎった直後や、彼女が記憶を保存したり会話を振り返ったりしている間は、返事まで5〜50秒かかることがあります。

ローカルのモデルには、彼女の耳・記憶・声が使う約6 GB（目も使うと約10 GB）とは別に、モデル自身のビデオメモリが必要です。`gemma3:27b`のような27Bのモデルで約19 GB、`qwen3:32b`のような32Bのモデルで約24 GB、`qwen2.5:72b`のような70Bのモデルでは約50 GBです。つまり、32 GBのカード（RTX 5090）1枚なら27Bのモデルと彼女の全機能が収まりますが（32Bのモデルは目をオフにした場合だけ）、24 GBのカードには収まりません。70Bのモデルを彼女と同じカードで動かせるのは、72〜96 GBのワークステーション向けカードだけです。それ以外の場合は、2台目のPCでOllamaを動かすか（Setupページでそのアドレスを指定できます）、セミローカルのままにしてください。どのモデルを使う場合も、彼女のプロンプトは中国語で書かれているので、中国語と日本語に対応したモデルを選んでください（たとえば`llama3.3:70b`はどちらにも対応していません）。切り替え方は[オプション機能](#オプション機能)にあります。

## セットアップ

PowerShell（管理者ではない普通のウィンドウ）を開き、次の行を1行ずつ実行してください。彼女はOneDriveで同期されない短いフォルダー`C:\OpenAmika`に入ります。

```powershell
cd C:\
git clone https://github.com/zeekk0/OpenAmika.git
cd OpenAmika
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1   # 脳・耳・記憶・目
envs\brain\Scripts\python.exe scripts\setup_tts.py                   # 声、Live2Dモデル、紙人形：yes と入力
.\Start_OpenAmika.bat                                                # 起動
```

彼女の声とLive2Dモデル、そして紙人形は、MekaHimeの個人利用ライセンス（[ライセンス](#ライセンス)参照）のもとで無料です。`setup_tts.py`の行が最初にその内容を表示し、`yes`と入力したときだけ彼女のファイルをダウンロードします。

どちらのセットアップコマンドも、最後にまとめを表示します。1行に1項目で、完了なら`OK`、問題があれば`!!`と直し方、`--`はお知らせだけです（たとえばOpenRouterのキーがまだないとき。最初に開いたときに入力できます）。同じコマンドをもう一度実行すれば、終わった部分は飛ばして続きから再開します。`setup_tts.py`のまとめに`OK voice MekaHime_Amika`と`OK Live2D model Amika`が出ていれば、彼女の声と体はそろっています。`OK paper doll Host`は、彼女のヘルパーの代わりに舞台に立つ紙人形です（[彼女のヘルパー](#彼女のヘルパーhermesとnanomuse)）。

## 話しかける

OpenAmikaフォルダーの`Start_OpenAmika.bat`をダブルクリックします（PowerShellでは`.\Start_OpenAmika.bat`）。コンソールが1つ開いて彼女のすべてが起動し、準備ができるとブラウザーで **http://localhost:53000** が開きます（約1分。初回はもう数分かかります）。最初に開いたとき、彼女が自己紹介をして、あなたの名前と住んでいる街、そして`brain\.env`にまだキーがなければOpenRouterのキーをたずねます。あとは電源ボタンを押して話しかけるか、文字で入力してください。ブラウザーが彼女の声を再生できるよう、ページを一度クリックしてください。

各ページ右上のランプは彼女の状態です。緑ならすべて正常で、クリックすると問題のある項目が見られます。止めるときは`Stop_OpenAmika.bat`をダブルクリックします（またはコンソールでCtrl+C）。何も起動せずに全体をチェックするには`envs\brain\Scripts\python.exe launch.py --check`を実行します。最後に`result: ready`と出るか、直すべき項目が表示されます。

アップデートするには、彼女を止めてからOpenAmikaフォルダーで`git stash`、`git pull`、`git stash pop`を実行し（あなたの名前、街、あなたの編集はそのまま残ります）、2つのセットアップコマンドをもう一度実行します（変わった部分だけを取得します）。

## うまくいかないとき

| 表示されるメッセージ | 対処 |
|---|---|
| `Python 3.11 was not found` | Python 3.11をインストール（「Add python.exe to PATH」にチェック）し、新しいPowerShellウィンドウでセットアップをもう一度実行します。 |
| `!! voice MekaHime_Amika  not downloaded: her license was not accepted` | `envs\brain\Scripts\python.exe scripts\setup_tts.py`をもう一度実行し、`yes`と入力します。 |
| `!! voice MekaHime_Amika  Hugging Face refused the download (HTTP 401)` | 彼女のファイルがまだ公開されていないか、`HF_TOKEN`が正しくありません。[huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)の読み取りトークンを同じウィンドウで設定し（`$env:HF_TOKEN = "hf_..."`）、同じコマンドをもう一度実行します。 |
| `download failed after 4 tries` または `Check the internet connection` | 同じコマンドをもう一度実行します。止まったところから続きます。お使いのネットワークからhuggingface.coにつながらない場合は、先に`$env:HF_ENDPOINT`にHugging Faceのミラーを設定してください。どのファイルも同じようにチェックされます。 |
| `does not see the GPU (CUDA)` | NVIDIAのドライバーを更新して、セットアップをもう一度実行します。NVIDIAのカードがない場合は`powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1 --cpu`。 |
| `The filename or extension is too long` | フォルダーのパスがWindowsには長すぎます。OpenAmikaを`C:\OpenAmika`のような短いフォルダーに移し、そこでセットアップを実行します。 |
| `settings.json not found` | 先に`powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1`を実行します。 |
| ステージに`No Live2D model yet`、または`launch.py --check`で`!! Live2D model` / `!! her voice` | `envs\brain\Scripts\python.exe scripts\setup_tts.py`を実行します。 |
| `no OpenRouter key yet`（`launch.py --check`やセットアップのまとめ） | 初回のウィザードでキーを貼り付けるか、`brain\.env`の`OPENROUTER_API_KEY=`の後ろに書きます。 |
| `!! TTS (voice)  port 8002 answers but has no voice MekaHime_Amika` | ほかの音声サーバーが彼女のポートを使っています（OpenSakuraのものも8002を使います）。それを止めるか、`settings.json`の`tts_url`と`services.tts`（`--port`と`health`）の`8002`を別の番号に変えます。 |
| 文字では返事をするのに声が聞こえない | 起動後20秒ほど待ってから、ページを一度クリックします。ランプのTTSが緑になっている必要があります。 |
| 声が途切れる、またはとても遅い | グラフィックカードを使うほかのアプリを閉じるか、`settings.json`で`"vision": {"enabled": false}`にして目の機能をオフにします。 |
| Ollamaで彼女らしくない、話したことを忘れる、返事が崩れる | モデルが小さすぎます。27B以上（フルで安定した体験には70B以上）のモデルを使うか、OpenRouterに戻してください：Setup → Brain → OpenRouter → 「Switch back to the OpenRouter preset」。 |
| Ollamaだと返事がとても遅い | `ollama ps`の表示が`100% GPU`ではなくCPU/GPUの割合になっている場合は、モデルが彼女と一緒にビデオメモリに収まっていません。`100% GPU`なら、話をさえぎった直後や、記憶の保存中・会話の振り返り中に返事が遅れるのは、ローカルのモデルでは普通のことです。[どの言語モデルを使う？](#どの言語モデルを使う)を参照してください。 |
| Toolsページのヘルパーのカードが赤い、または彼女がHermesやnanoMuseにつながらないと言う | `envs\brain\Scripts\python.exe launch.py --check`を実行し、`agent`と`hermes key`の行を見てください。各メッセージの意味と直し方は[docs/TOOLS.md](docs/TOOLS.md#when-it-does-not-work)にあります。 |

各パーツのログは`logs\`にあります。それでも解決しないときは、[Discord](https://discord.gg/mekahime)で質問するか、[issue](https://github.com/zeekk0/OpenAmika/issues)を作成してください。AIコーディングエージェントを使う場合は、[README_IF_YOU_ARE_AI_AGENT.md](README_IF_YOU_ARE_AI_AGENT.md)を読ませてください。

## オプション機能

- **完全ローカル**：[Ollama](https://ollama.com)をインストールして`ollama pull gemma3:27b`を実行し（17 GB。27B以上のほかのモデルでも構いません。[どの言語モデルを使う？](#どの言語モデルを使う)を参照）、Setupページで Brain → Ollama → Detect models → Use this model を選びます。キーは不要です。別のPCで動くOllamaを使う場合は、Detect modelsの前にそのアドレスを入力してください。
- **彼女のヘルパー**：Hermes AgentやnanoMuseが彼女の用事をこなし、舞台では紙人形が彼女の横に立ちます（[下記](#彼女のヘルパーhermesとnanomuse)）。ほかのMCPサーバーもToolsページで使えます（[docs/TOOLS.md](docs/TOOLS.md)）。
- **スマートホーム**：彼女が切り替えられるZigbeeプラグ（[IoT/README.md](IoT/README.md)）。ToolsページでIoT安全に関する声明（[docs/IOT_DISCLAIMER.md](docs/IOT_DISCLAIMER.md)）を読んで同意するまでオフのままです。彼女は言語モデルで動いていて間違えることもあるので、暖房器具、錠、バルブなど、危険につながるものは絶対につながないでください。
- **テキストで話す**：DiscordやTelegramから（[docs/MESSENGERS.md](docs/MESSENGERS.md)）。
- **スマートフォンから**：`Tailscale_Serve_OpenAmika.bat`を使うと、[Tailscale](https://tailscale.com)経由で自分のデバイスから彼女にアクセスできます。

## 彼女のヘルパー：HermesとnanoMuse

彼女は、あなたのPCで動くヘルパープログラム、[Hermes Agent](https://hermes-agent.nousresearch.com)や[nanoMuse](https://github.com/nano-muse/nanoMuse)に用事を頼めます。ヘルパーはウェブを検索し、ブラウザーを操作し、ファイルを扱います。手伝うかどうかは彼女が決めます。あなたに返事をしてからヘルパーに用事を渡し、ヘルパーからの質問を伝え、結果を自分の言葉で教えてくれます。ヘルパーがオンの間は、MekaHimeの紙人形が彼女の舞台の右下に立ち、ヘルパーの役を演じます。ヘルパーはそれぞれOpenRouterで自分のモデルを使います。キーは彼女が使っているものをそのまま使えます。

**Hermes Agent**：PowerShellウィンドウでインストールします。この形のインストーラーは何も質問しません。OpenAmikaに必要な設定は、そのあとの行で行います。

```powershell
& ([scriptblock]::Create((irm https://hermes-agent.nousresearch.com/install.ps1))) -NonInteractive
```

終わったら、新しいPowerShellウィンドウで：

```powershell
hermes model                                    # OpenRouterを選んでキーを貼り付け、「Enter custom model name」で z-ai/glm-5 と入力
$key = [guid]::NewGuid().ToString('N')          # APIサーバー用のランダムなキー
hermes config set API_SERVER_ENABLED true
hermes config set API_SERVER_KEY $key
hermes gateway stop                             # すでに動いているHermesは、次に起動したときにキーを読み込む
```

**nanoMuse**：`Nanomuse`フォルダーにクローンし、`config.toml`を用意して、キーをnanoMuse自身の保管庫（vault）に入れます。コマンドとファイルの中身は[docs/TOOLS.md](docs/TOOLS.md#set-up-nanomuse)にあります。

**つなぐ。** OpenAmikaフォルダーで`Copy-Item config\tools.example.json config\tools.json`（`config\tools.json`がまだないときだけ）と`notepad config\tools.json`を実行します。先頭とヘルパーの項目の`"enabled"`を`true`にします。nanoMuseの場合は`"NANOMUSE_LANGUAGE"`も`"ja"`にします（ヘルパーが日本語で返事をします）。Hermesの場合は、次の行でキーをコピーして、`"HERMES_API_KEY"`に貼り付けます（Ctrl+V）：

```powershell
(Select-String -Path "$env:LOCALAPPDATA\hermes\.env" -Pattern '^API_SERVER_KEY=(.+)').Matches[0].Groups[1].Value | Set-Clipboard
```

保存して彼女を起動すると（`.\Start_OpenAmika.bat`）、ヘルパーは彼女が自分で起動します。Toolsページのヘルパーのカードが緑（`agent online`）になります。

**紙人形に会う。** Useページを開くと、紙人形が彼女の舞台にすっと入ってきます。たとえば「Hermesに明日の天気を調べてもらえる？」と頼んでみてください。彼女が返事をして、吹き出しに用事を打ち込むと、そこから紙人形の出番です。ヘルパーが作業している間は考え込み、ヘルパーの進み具合を自分の吹き出しで話し、ヘルパーから質問があるときやあなたの許可が必要なときは驚いた顔をします（声で「いいよ」「だめ」と答えるか、UseページのApproveをクリック）。結果が届くと喜び、その結果を彼女が教えてくれます。紙人形は`setup_tts.py`で一緒に入ります（まとめに`OK paper doll Host`）。

すべての手順の詳細と、各メッセージの意味：[docs/TOOLS.md](docs/TOOLS.md#her-helpers-set-up-hermes-agent-and-nanomuse)

## ライセンス

- OpenAmikaのコードは **MIT** です（[LICENSE](LICENSE)）。サードパーティーの部分はそれぞれのライセンスに従います（[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)）。`ui/vendor/`のLive2D Cubism CoreはMITではありません。
- **Amika自身はMITではありません。** 彼女のキャラクター、アート、声、Live2Dモデルとその重み、そして彼女のヘルパーの代わりに立つ紙人形（[MekaHime/MekaHime_Amika](https://huggingface.co/MekaHime/MekaHime_Amika)）はMekaHime Inc.に帰属し、個人利用ライセンスのもとで無料で使えます。個人利用に限り、18歳以上の方が対象です。再配布や再ホスティング、これらを使ったほかのモデルの学習はできません。クリエイター向けのルールが二つあります。SNS（動画、配信、広告、メンバーシップ、スポンサー）での収益化は上限なしで、MekaHime.AIのクレジットを見える形で表記してください。ファングッズは個人として合計1,000米ドルまでで、自分で描き起こしたファンアートを使い（MekaHimeがウェブサイトやSNSで公開したオリジナル画像は使えません）、見える面に「MekaHime.AI」と小さな「Fan Art」の表示を入れてください。それ以外の商用利用にはMekaHimeのライセンスが必要です（hi@mekahime.com）。Hugging Faceの[LICENSE](https://huggingface.co/MekaHime/MekaHime_Amika/blob/main/LICENSE)が正式な条件です。
- Hermes Agent（MIT）とnanoMuse（GPL-3.0-or-later）は、あなたが自分でインストールする別のプログラムです。OpenAmikaはそれらと通信するだけです。
- [SenseVoice](https://github.com/FunAudioLLM/SenseVoice)、[GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)、[bge-m3](https://huggingface.co/BAAI/bge-m3)、[Qwen3-VL](https://github.com/QwenLM/Qwen3-VL)、[pixi-live2d-display](https://github.com/guansss/pixi-live2d-display)と[Live2D Cubism SDK](https://www.live2d.com/en/sdk/about/)、[OpenRouter](https://openrouter.ai)、[Ollama](https://ollama.com)、[Model Context Protocol](https://modelcontextprotocol.io)の上に作られています。ありがとうございます。

## サポート

質問やバグ報告は、[GitHubのissue](https://github.com/zeekk0/OpenAmika/issues)、hi@mekahime.com、または[Discord](https://discord.gg/mekahime)へ。プロジェクトへのご支援: https://www.mekahime.com/donate

<p align="center">
  <a href="https://www.mekahime.com">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/images/mekahime-logo-white.png">
      <img src="docs/images/mekahime-logo-card.png" alt="MekaHime" width="220">
    </picture>
  </a>
</p>
