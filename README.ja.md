<!-- Translated from README.md; keep in sync when README.md changes. -->
<div align="center">

<img src="docs/images/amika-avatar.png" alt="Amika" width="180">

# OpenAmika

**こんにちは、Amikaです！** — MekaHimeのAIコンパニオン、オープンソース版です

Amikaは、声とテキストでリアルタイムにおしゃべりしてくれるLive2Dのアニメ少女です。あなたのことを覚えていて、あなたの街で一緒に暮らしています。動くのはあなた自身のPCの上で、OpenRouterを使うことも、Ollamaで完全ローカルにすることもできます。ホスト版も[mekahime.com/amika](https://www.mekahime.com/amika)で動いています。

[简体中文](README.zh-CN.md) | **日本語** | [English](README.md) | [Tiếng Việt](README.vi.md) | [한국어](README.ko.md)

[![Made with Love](https://img.shields.io/badge/Made%20with-Love-ff69b4)](https://www.mekahime.com/openamika)
[![GitHub](https://img.shields.io/badge/GitHub-zeekk0%2FOpenAmika-181717?logo=github)](https://github.com/zeekk0/OpenAmika)
[![Release](https://img.shields.io/github/v/release/zeekk0/OpenAmika?logo=github&color=d8b4e2)](https://github.com/zeekk0/OpenAmika/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-43b581)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20(Linux%20untested)-0078D6?logo=windows&logoColor=white)](#必要なもの)
[![Python 3.11 | 3.12](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3119/)

[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-MekaHime%2FMekaHime__Amika-ffcc4d)](https://huggingface.co/MekaHime/MekaHime_Amika)
[![Discord](https://img.shields.io/badge/Discord-MekaHime-5865F2?logo=discord&logoColor=white)](https://discord.gg/mekahime)
[![Website](https://img.shields.io/badge/website-mekahime.com-d8b4e2)](https://www.mekahime.com/openamika)
[![Try Online](https://img.shields.io/badge/Try%20Online-mekahime.com%2Famika-e58fb8)](https://www.mekahime.com/amika)
[![Tests](https://github.com/zeekk0/OpenAmika/actions/workflows/tests.yml/badge.svg)](https://github.com/zeekk0/OpenAmika/actions/workflows/tests.yml)
[![GitHub stars](https://img.shields.io/github/stars/zeekk0/OpenAmika?style=social)](https://github.com/zeekk0/OpenAmika/stargazers)

</div>

## インストール：7つのステップ

**始める前に：** Windows 10 または 11、NVIDIAのグラフィックカード（RTX 20シリーズ以降、ビデオメモリ8 GB）、空きディスク約40 GBがありますか？

- **はい** → STEP 1 へ。
- **いいえ** → ブラウザーで彼女と話せます：[mekahime.com/amika](https://www.mekahime.com/amika)。

**動画で見たい？** 同じ7つのステップを3分の動画にしました。よくある質問と対処法もあります（英語のページ）：[mekahime.com/openamikatutorial](https://www.mekahime.com/openamikatutorial)。

### STEP 1 — Python 3.11 と Git をインストール

約5分。

1. [python-3.11.9-amd64.exe](https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe) をクリックして開きます。最初の画面の下にある **Add python.exe to PATH** にチェックを入れ、**Install Now** をクリック。
2. [Git-2.56.0.4-64-bit.exe](https://github.com/git-for-windows/git/releases/download/v2.56.0.windows.4/Git-2.56.0.4-64-bit.exe) をクリックして開きます。**Install** が出るまで **Next** をクリックし、**Install**、最後に **Finish**。

表示：「Setup was successful」（Python）と「Completing the Git Setup Wizard」（Git）。

### STEP 2 — 彼女を置くフォルダーで PowerShell を開く

1. **Windowsキー**を押し、`powershell` と入力して **Enter**。普通のウィンドウで開きます（「管理者として実行」ではありません）。
2. 下の行をコピーし、青いウィンドウをクリックして**右クリック**（これで貼り付けられます）、**Enter**。

```powershell
cd C:\
```

表示：`PS C:\>` と点滅するカーソル。

どのドライブでも大丈夫です：`cd D:\` なら D: に入ります。パスは短いほど安全です。OneDriveの中には置かないでください。

### STEP 3 — OpenAmika をダウンロード

1行ずつ貼り付けて **Enter**、`PS ...>` が戻るまで待ちます。約1分。

```powershell
git clone https://github.com/zeekk0/OpenAmika.git
```

```powershell
cd OpenAmika
```

表示：`PS C:\OpenAmika>`。

- `'git' is not recognized` と出たら → このウィンドウを閉じて STEP 2 からやり直し（新しいウィンドウならGitが見つかります）、このステップへ。
- `destination path 'OpenAmika' already exists` と出たら → もうダウンロード済みです。`cd OpenAmika` を貼り付けて先へ。

### STEP 4 — セットアップを実行

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

15〜60分、ダウンロードは約11 GB。ウィンドウは開いたままにしてください。

最初に Hugging Face のトークンを聞かれます：**Enter** で飛ばすか、[huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) で作った無料の *Read* トークンを貼り付けます（ダウンロードがずっと速くなります）。

最後の表示：`OpenAmika setup summary`、`OK` で始まる行、そして `Done. Next:`。

- `The argument 'scripts\setup_windows.ps1' to the -File parameter does not exist` → このウィンドウが彼女のフォルダーにいません。`cd C:\OpenAmika`（またはセットアップが表示した `cd` の行）を貼り付けて **Enter**、もう一度実行。
- `Python 3.11 was not found` → **Add python.exe to PATH** にチェックを入れて STEP 1 をやり直し、新しいウィンドウ（STEP 2）で `cd C:\OpenAmika`、そしてこの行をもう一度。
- ダウンロードがとても遅い（約50 KB/s）→ **Ctrl+C** を押してもう一度実行し、聞かれたら Hugging Face のトークンを貼り付けます。止まったところから続きます。
- `!!` で始まる行が出たら → その行の指示どおりにして、もう一度実行。終わった部分は飛ばされます。

### STEP 5 — 彼女の声とモデル

```powershell
envs\brain\Scripts\python.exe scripts\setup_tts.py
```

10〜30分、ダウンロードは約5.5 GB。ライセンスが表示されたあと聞かれるので、`yes` と入力して **Enter**。

表示：`OK voice MekaHime_Amika` と `OK Live2D model Amika`、そして `Done. Next:`。

- `not downloaded: her license was not accepted` → もう一度実行して `yes` と入力。
- `'envs\brain\Scripts\python.exe' is not recognized` → このウィンドウが彼女のフォルダーにいない（`cd C:\OpenAmika`）か、STEP 4 が終わっていません。

### STEP 6 — 彼女を起動

```powershell
.\Start_OpenAmika.bat
```

次からは `C:\OpenAmika` の `Start_OpenAmika.bat` をダブルクリックするだけです。

1〜3分（初回がいちばん遅いです）。

表示：**OpenAmika** という名前のウィンドウに緑の行が並びます。ブラウザーで彼女のページ（http://localhost:53000）が開き、最初のウィンドウがあなたの名前と街を聞きます。

- 彼女のウィンドウに `moved to … in settings.json (chat_port)` → Windowsがポート53000を予約していたので、次の空いているポートに移りました。ウィンドウ上部のアドレスを開いてください。
- エラーで止まったら → ウィンドウは開いたままで、ログ（`logs\launcher.log`）を示します。そのファイルを [Discord](https://discord.gg/mekahime) へ。

### STEP 7 — 最初のウィンドウに OpenRouter のキーを貼り付ける

1. [openrouter.ai](https://openrouter.ai) でサインインし、**Credits** を開いて数ドル入金します。OpenRouterは前払い制です：キーだけでは足りません。
2. **Keys** → **Create Key**。キー（`sk-or-v1-` で始まります）をコピー。
3. 彼女の最初のウィンドウの「脳」のところで **OpenRouter** をクリックし、キーを貼り付けて **Save key**。

表示：緑の `✓ Key saved … · $5.00 of credit left`。**Next** をクリックし、ページを一度クリック（ブラウザーが彼女の声を許可します）、電源ボタンを押して話しかけてください。

- `no credits` と出たら → openrouter.ai でクレジットを追加し、もう一度 **Save key**。
- 返事が失敗したら → チャットにOpenRouter自身の理由が表示されます。モデルが無くなっていたら：Setup → Brain → **Switch back to the OpenRouter preset**。

> **`git clone` ではなくZIPをダウンロードした？** 解凍し、内側のフォルダー（`Start_OpenAmika.bat` が入っている方）を開きます。何もないところを右クリック → **ターミナルで開く**。そのあと STEP 4 から STEP 7 へ。
> （Windows 10：フォルダーのアドレスバーをクリックし、`powershell` と入力して **Enter**。）

*STEP 1〜6 は、**metro01** さんがMekaHime Discordのヘルプデスクに書いてくれた手順をもとにしています。ありがとう、metro01さん！*

## アップデート（彼女の記憶はそのまま）

彼女の記憶は `memory_f` と `brain\memories` にあります。何かする前にバックアップしてください。

**git clone した場合**

1. **STEP 1 — 彼女を止める。** `Stop_OpenAmika.bat` をダブルクリック。
2. **STEP 2 — 彼女のフォルダーの `Update_OpenAmika.bat` をダブルクリック。** 彼女の記憶と設定を `backups\update-<日付>.zip` に保存し、アップデートをダウンロードして、変わった部分をインストールします。ライセンスを聞かれたら `yes`。

表示：`Updated. Start her: double-click Start_OpenAmika.bat`。

- `She is running` → 先に STEP 1。
- 「with your own changes」としてファイルが並んだら → あなたの版が残っています。彼女の記憶は無事です。

**彼女のフォルダーに `Update_OpenAmika.bat` がない？** v1.1.0（2026年11月9日）より前にインストールした場合です。今回だけ、STEP 2 を次のようにします。彼女のフォルダーを開き、何もないところを右クリック → **ターミナルで開く**（Windows 10：フォルダーのアドレスバーをクリックし、`powershell` と入力して **Enter**）。次の行を1行ずつ貼り付けて **Enter**：

```powershell
git fetch origin
```

```powershell
git show origin/main:scripts/update_openamika.ps1 > scripts\update_once.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\update_once.ps1
```

アップデートの内容もバックアップも同じです。これが終わると、彼女のフォルダーに `Update_OpenAmika.bat` が入ります。

**ZIPをダウンロードした場合**

1. **STEP 1 — 彼女を止める。** `Stop_OpenAmika.bat` をダブルクリック。
2. **STEP 2 — 新しいZIPをダウンロードして、古いフォルダーの隣に解凍。**
3. **STEP 3 — 古いフォルダーから新しいフォルダーへ次のものをコピー**（あるものだけ）：`memory_f`、`brain\memories`、`settings.json`、`brain\.env`、`config\seed.json`、`config\ollama.json`、`config\voice_map.json`、`config\tools.json`、`config\messengers.json`。
4. **STEP 4 — 新しいフォルダーでセットアップを実行**：インストールの STEP 4 と STEP 5 を新しいフォルダーで。2回目は速くなります。
5. **STEP 5 — 新しいフォルダーから彼女を起動。** 名前と街をもう一度聞かれることがありますが、記憶はすべて残っています。彼女があなたを覚えているのを確かめてから、古いフォルダーを消してください。

> 💖 Amikaのおかげで毎日が少しでも楽しくなったら、[GitHub](https://github.com/zeekk0/OpenAmika)で⭐をつけてもらえるとうれしいです。もっとたくさんの人が彼女に出会えます！ · プロジェクトへのご支援: https://www.mekahime.com/donate

## 必要なもの

- Windows 10または11と、NVIDIAのグラフィックカード（RTX 20シリーズ以降、ビデオメモリ8 GB以上。カメラで「見る」機能には16 GB）、そして新しいドライバー
- [Python 3.11](https://www.python.org/downloads/release/python-3119/)（インストール時に **Add python.exe to PATH** にチェック。3.12でも動きます。3.13以降は、彼女の声のサーバーが必要とする numpy 1.26.4 にホイールがないため動きません）と[Git](https://git-scm.com/download/win)
- 約40 GBの空きディスク（セットアップ後の使用量は約37 GB、カメラの目なしなら約28 GB。終わったあと `pip cache purge` で約6 GB戻ります）。セットアップでは約16 GBをダウンロードし、30〜60分ほどかかります
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

あとで彼女の記憶をリセットしたいときは、Setupページ →「Danger zone」→ **Wipe memory** を使います。すべての会話と事実を忘れ、バックアップは`memory_f\backups\`に残ります。彼女がまだ話していれば数秒待ち、それでも終わらないときは **Force wipe**（彼女はしていることをやめます）を表示します。スクリプトからは`envs\brain\Scripts\python.exe launch.py --wipe-memory`（先に止めるなら`--force`。彼女が起動していなくても使えます）。

## 話しかける

OpenAmikaフォルダーの`Start_OpenAmika.bat`をダブルクリックします（PowerShellでは`.\Start_OpenAmika.bat`）。コンソールが1つ開いて彼女のすべてが起動し、準備ができるとブラウザーで **http://localhost:53000** が開きます（約1分。初回はもう数分かかります）。最初に開いたとき、彼女が自己紹介をして、あなたの名前と住んでいる街、そして`brain\.env`にまだキーがなければOpenRouterのキーをたずねます。あとは電源ボタンを押して話しかけるか、文字で入力してください。ブラウザーが彼女の声を再生できるよう、ページを一度クリックしてください。あなたが黙っていると、彼女の声が止まった時点から数えて、彼女のほうから話しかけることがあります。頻度はSetup →「You & Amika」→「When you go quiet」で Normal / Rare / Off を選べます。

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
| 記憶の消去やリセットで`Amika is busy` | 彼女が話し終えるまで数秒待ちます。それでも終わらないときは **Force wipe (she stops what she is doing)** を押します。バックアップはどちらの場合も残ります。 |
| Setupページで`Model selection is busy` | メッセージの横の **Unlock** を押します。彼女はしていることをやめ、切り替えが通ります。 |
| コンソールのbrainの行（またはSetupページの`brain start`）が赤い | その行に理由が出ます：ポートが使われている、環境が壊れている、モデルが入りきらない、キーがない。 |
| Toolsページのヘルパーのカードが赤い、または彼女がHermesやnanoMuseにつながらないと言う | `envs\brain\Scripts\python.exe launch.py --check`を実行し、`agent`と`hermes key`の行を見てください。各メッセージの意味と直し方は[docs/TOOLS.md](docs/TOOLS.md#when-it-does-not-work)にあります。 |

各パーツのログは`logs\`にあります。それでも解決しないときは、`envs\brain\Scripts\python.exe launch.py --diagnose`を実行してください。`logs\`にzipが1つでき（起動時のチェック、各ログの末尾、キーを除いた設定、バージョン、空きディスクとGPUメモリ）、それを添えて、[Discord](https://discord.gg/mekahime)で質問するか、[issue](https://github.com/zeekk0/OpenAmika/issues)を作成してください。AIコーディングエージェントを使う場合は、[README_IF_YOU_ARE_AI_AGENT.md](README_IF_YOU_ARE_AI_AGENT.md)を読ませてください。

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
