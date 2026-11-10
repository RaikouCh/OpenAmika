<!-- Translated from README.md; keep in sync when README.md changes. -->
<div align="center">

<img src="docs/images/amika-avatar.png" alt="Amika" width="180">

# OpenAmika

**안녕하세요! Amika예요** — MekaHime의 오픈 소스 AI 동반자

[简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [English](README.md) | [Tiếng Việt](README.vi.md) | **한국어**

[![Made with Love](https://img.shields.io/badge/Made%20with-Love-ff69b4)](https://www.mekahime.com/openamika)
[![GitHub](https://img.shields.io/badge/GitHub-zeekk0%2FOpenAmika-181717?logo=github)](https://github.com/zeekk0/OpenAmika)
[![Release](https://img.shields.io/github/v/release/zeekk0/OpenAmika?logo=github&color=d8b4e2)](https://github.com/zeekk0/OpenAmika/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-43b581)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20(Linux%20untested)-0078D6?logo=windows&logoColor=white)](#준비-사항)
[![Python 3.11 | 3.12](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3119/)

[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-MekaHime%2FMekaHime__Amika-ffcc4d)](https://huggingface.co/MekaHime/MekaHime_Amika)
[![Discord](https://img.shields.io/badge/Discord-MekaHime-5865F2?logo=discord&logoColor=white)](https://discord.gg/mekahime)
[![Website](https://img.shields.io/badge/website-mekahime.com-d8b4e2)](https://www.mekahime.com/openamika)
[![Try Online](https://img.shields.io/badge/Try%20Online-mekahime.com%2Famika-e58fb8)](https://www.mekahime.com/amika)
[![Tests](https://github.com/zeekk0/OpenAmika/actions/workflows/tests.yml/badge.svg)](https://github.com/zeekk0/OpenAmika/actions/workflows/tests.yml)
[![GitHub stars](https://img.shields.io/github/stars/zeekk0/OpenAmika?style=social)](https://github.com/zeekk0/OpenAmika/stargazers)

</div>

> 이 문서는 영문 README의 한국어 번역입니다. 한국어 대화·음성·화면의 공식 지원을 뜻하지 않습니다.

## 7단계 설치 안내

**시작하기 전에 확인하세요.** Windows 10 또는 11, NVIDIA 그래픽 카드(RTX 20 시리즈 이상, VRAM 8 GB),
약 40 GB의 여유 디스크 공간이 있나요?

- **예** → 1단계로 진행하세요.
- **아니요** → 브라우저에서 대화할 수 있습니다: [mekahime.com/amika](https://www.mekahime.com/amika).

**영상으로 보고 싶다면:** 같은 7단계를 3분 영상으로 설명하며, 막히는 부분의 해결 방법과 답변도 제공합니다.
[mekahime.com/openamikatutorial](https://www.mekahime.com/openamikatutorial).

### 1단계 — Python 3.11과 Git 설치

약 5분 걸립니다.

1. [python-3.11.9-amd64.exe](https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe)를 내려받아 실행하세요.
   첫 화면 아래의 **Add python.exe to PATH**에 체크하고 **Install Now**를 누르세요.
2. [Git-2.56.0.4-64-bit.exe](https://github.com/git-for-windows/git/releases/download/v2.56.0.windows.4/Git-2.56.0.4-64-bit.exe)를
   내려받아 실행하세요. **Install**이 나올 때까지 **Next**를 누른 뒤 **Install**, **Finish**를 차례로 누르세요.

Python에서는 `Setup was successful`, Git에서는 `Completing the Git Setup Wizard`가 표시됩니다.

### 2단계 — 설치할 폴더에서 PowerShell 열기

1. **Windows 키**를 누르고 `powershell`을 입력한 뒤 **Enter**를 누르세요. 관리자 권한이 아닌 일반 창으로 실행하세요.
2. 아래 줄을 복사하고 파란 창 안에서 **마우스 오른쪽 버튼**을 눌러 붙여넣은 뒤 **Enter**를 누르세요.

```powershell
cd C:\
```

`PS C:\>`와 깜박이는 커서가 표시됩니다.

다른 드라이브도 가능합니다. `cd D:\`를 입력하면 D:에 설치합니다. 짧은 경로를 사용하고 OneDrive 폴더 안은 피하세요.

### 3단계 — OpenAmika 내려받기

한 줄씩 붙여넣고 **Enter**를 누른 뒤 `PS ...>`가 다시 나올 때까지 기다리세요. 약 1분 걸립니다.

```powershell
git clone https://github.com/zeekk0/OpenAmika.git
```

```powershell
cd OpenAmika
```

`PS C:\OpenAmika>`가 표시됩니다.

- `'git' is not recognized`가 나오면 창을 닫고 2단계부터 다시 진행하세요. 새 창에서 Git을 찾을 수 있습니다.
- `destination path 'OpenAmika' already exists`가 나오면 이미 내려받은 상태입니다. `cd OpenAmika`를 입력하고 계속하세요.

### 4단계 — 설치 프로그램 실행

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

약 11 GB를 내려받으며 15~60분 걸립니다. 창을 열어두세요.

처음에 Hugging Face 토큰을 요청합니다. **Enter**를 눌러 건너뛰거나,
[huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)에서 무료 *Read* 토큰을 만들어 붙여넣으세요.
토큰을 사용하면 다운로드가 훨씬 빨라집니다.

마지막에 `OpenAmika setup summary`, `OK`로 시작하는 줄들, `Done. Next:`가 표시됩니다.

- `The argument 'scripts\setup_windows.ps1' to the -File parameter does not exist`가 나오면 현재 창이 프로젝트 폴더에
  있지 않은 것입니다. `cd C:\OpenAmika` 또는 설치 프로그램이 안내한 `cd` 명령을 입력하고 다시 실행하세요.
- `Python 3.11 was not found`가 나오면 1단계에서 **Add python.exe to PATH**를 체크해 다시 설치하세요. 새 창을 열고
  2단계와 `cd C:\OpenAmika`를 거친 뒤 위 명령을 다시 실행하세요.
- 다운로드가 약 50 KB/s로 느리면 **Ctrl+C**를 누르고 다시 실행한 뒤 Hugging Face 토큰을 입력하세요.
  중단한 지점부터 이어받습니다.
- `!!`로 시작하는 줄이 있으면 해당 안내에 따라 해결한 뒤 다시 실행하세요. 완료한 부분은 건너뜁니다.

### 5단계 — 음성과 모델 설치

```powershell
envs\brain\Scripts\python.exe scripts\setup_tts.py
```

약 5.5 GB를 내려받으며 10~30분 걸립니다. 라이선스가 표시된 뒤 동의를 요청합니다. 읽고 동의한다면 `yes`를 입력하고 **Enter**를 누르세요.

`OK voice MekaHime_Amika`, `OK Live2D model Amika`, `Done. Next:`가 표시됩니다.

- `not downloaded: her license was not accepted`가 나오면 라이선스를 읽고 동의하는 경우 명령을 다시 실행해 `yes`를 입력하세요.
- `'envs\brain\Scripts\python.exe' is not recognized`가 나오면 현재 폴더가 맞는지(`cd C:\OpenAmika`),
  4단계가 끝났는지 확인하세요.

### 6단계 — 실행

```powershell
.\Start_OpenAmika.bat
```

다음부터는 `C:\OpenAmika`의 `Start_OpenAmika.bat`를 더블클릭하면 됩니다.

1~3분 걸리며, 첫 실행이 가장 오래 걸립니다.

**OpenAmika**라는 창에 초록색 상태 행이 표시됩니다. 브라우저에서 페이지(http://localhost:53000)가 열리고,
첫 설정 창에서 이름과 도시를 묻습니다.

- 창에 `moved to … in settings.json (chat_port)`가 나오면 Windows가 53000 포트를 예약해 두어 다음 빈 포트로 옮긴 것입니다.
  창 위쪽에 표시된 주소를 여세요.
- 오류로 멈추면 창이 열린 채 로그 경로(`logs\launcher.log`)를 안내합니다. 해당 파일을 첨부해
  [Discord](https://discord.gg/mekahime)에 문의하세요.

### 7단계 — 첫 설정 창에 OpenRouter 키 입력

1. [openrouter.ai](https://openrouter.ai)에 로그인하고 **Credits**에서 몇 달러를 충전하세요.
   OpenRouter는 선불제이므로 키만 있어서는 사용할 수 없습니다.
2. **Keys** → **Create Key**를 열고 `sk-or-v1-`로 시작하는 키를 복사하세요.
3. 첫 설정 창의 언어 모델 항목에서 **OpenRouter**를 누르고 키를 붙여넣은 뒤 **Save key**를 누르세요.

초록색 `✓ Key saved … · $5.00 of credit left`가 표시됩니다. **Next**를 누르고, 브라우저가 소리를 재생할 수 있도록
페이지를 한 번 클릭한 뒤 전원 버튼을 누르고 대화하세요.

- `no credits`가 나오면 openrouter.ai에서 충전한 뒤 **Save key**를 다시 누르세요.
- 답변에 실패하면 채팅에 OpenRouter의 오류 사유가 표시됩니다. 모델이 더 이상 제공되지 않는 경우에는
  Setup → Brain → **Switch back to the OpenRouter preset**을 선택하세요.

> **`git clone` 대신 ZIP을 내려받았나요?** 압축을 풀고 `Start_OpenAmika.bat`가 있는 안쪽 폴더를 여세요.
> 빈 곳에서 마우스 오른쪽 버튼 → **터미널에서 열기**를 선택한 뒤 4~7단계를 진행하세요.
> Windows 10에서는 폴더 주소 표시줄에 `powershell`을 입력하고 **Enter**를 누르세요.

*1~6단계는 **metro01**이 MekaHime Discord 도움말 채널에 작성한 설치 안내를 바탕으로 합니다. metro01에게 감사드립니다!*

## 업데이트와 기억 보존

기억은 `memory_f`와 `brain\memories`에 저장됩니다. 먼저 백업하세요.

**git clone으로 설치한 경우**

1. **1단계 — 종료.** `Stop_OpenAmika.bat`를 더블클릭하세요.
2. **2단계 — 프로젝트 폴더의 `Update_OpenAmika.bat`를 더블클릭하세요.** 기억과 설정을 `backups\update-<date>.zip`에
   백업하고, 업데이트를 내려받아 변경된 부분을 설치합니다. 라이선스 동의를 요청하면 읽고 동의하는 경우 `yes`를 입력하세요.

`Updated. Start her: double-click Start_OpenAmika.bat`가 표시됩니다.

- `She is running`이 나오면 먼저 1단계를 진행하세요.
- `with your own changes`라는 파일 목록이 나오면 사용자가 수정한 버전을 유지합니다. 기억도 보존됩니다.

**`Update_OpenAmika.bat`가 없나요?** v1.1.0(2026년 11월 9일) 이전에 설치한 경우입니다. 한 번만 다음 방법으로
2단계를 진행하세요. 프로젝트 폴더의 빈 곳에서 마우스 오른쪽 버튼 → **터미널에서 열기**를 선택하세요.
Windows 10에서는 폴더 주소 표시줄에 `powershell`을 입력하고 **Enter**를 누르세요. 아래 명령을 한 줄씩 실행하세요.

```powershell
git fetch origin
```

```powershell
git show origin/main:scripts/update_openamika.ps1 > scripts\update_once.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\update_once.ps1
```

백업을 포함해 같은 업데이트를 수행합니다. 완료하면 프로젝트 폴더에 `Update_OpenAmika.bat`가 생깁니다.

**ZIP으로 설치한 경우**

1. **1단계 — 종료.** `Stop_OpenAmika.bat`를 더블클릭하세요.
2. **2단계 — 새 ZIP을 내려받아** 기존 폴더 옆에 압축을 푸세요.
3. **3단계 — 기존 폴더에서 새 폴더로 다음 항목 중 있는 것을 복사하세요:** `memory_f`, `brain\memories`,
   `settings.json`, `brain\.env`, `config\seed.json`, `config\ollama.json`, `config\voice_map.json`,
   `config\tools.json`, `config\messengers.json`.
4. **4단계 — 새 폴더에서 설치 프로그램을 실행하세요.** 설치 안내의 4단계와 5단계를 새 폴더에서 진행하면 됩니다.
   두 번째 설치는 더 빠릅니다.
5. **5단계 — 새 폴더에서 실행하세요.** 이름과 도시를 다시 물을 수 있지만 기억은 그대로 있습니다.
   나를 기억하는지 확인한 뒤 기존 폴더를 삭제하세요.

## Amika 소개

Amika는 음성과 텍스트로 실시간 대화하고, 여러분을 기억하며, 여러분의 도시에서 함께 살아가는 Live2D 소녀 캐릭터입니다.
내 PC에서 실행하며 OpenRouter를 이용하거나 Ollama로 완전히 로컬에서 실행할 수 있습니다.
[mekahime.com/amika](https://www.mekahime.com/amika)에서는 호스팅 버전도 사용할 수 있습니다.

> 💖 Amika 덕분에 하루가 즐거워졌다면 [GitHub](https://github.com/zeekk0/OpenAmika)에 ⭐를 눌러 주세요.
> 더 많은 사람이 Amika를 만나는 데 도움이 됩니다! · 프로젝트 후원: https://www.mekahime.com/donate

## 준비 사항

- Windows 10 또는 11, 최신 드라이버를 설치한 NVIDIA 그래픽 카드(RTX 20 시리즈 이상)가 필요합니다.
  PC의 RAM이 아닌 그래픽 카드의 메모리(VRAM)를 기준으로 확인하세요.

  | 실행 방식 | Amika 자체 구성 요소 | 언어 모델 | 예시 |
  |---|---|---|---|
  | **Semi-Local**(권장) | 음성 인식·기억·음성 합성에 VRAM 약 **5.5 GB**. 8 GB 그래픽 카드 | OpenRouter에서 실행하므로 로컬 VRAM을 사용하지 않음 | RTX 3060 노트북에서도 실행됩니다. 텍스트가 나온 뒤 몇 초 후 음성이 나오며, 한 사용자는 비용이 “지금까지 2센트뿐”이라고 전했습니다. |
  | + 카메라 시각 기능 | 약 4.3 GB 추가. 16 GB 그래픽 카드 | | |
  | **Fully Local**(Ollama) | 5.5 GB, 시각 기능 포함 시 약 10 GB | 언어 모델에 추가로 사용. 27B 모델은 약 19 GB 추가 | 32 GB 그래픽 카드 한 장(RTX 5090) 또는 별도 PC에서 Ollama 실행 |

- Python 3.11(3.12도 사용 가능)과 Git이 필요합니다. 1단계를 참고하세요. 음성 서버에 필요한 numpy 1.26.4의
  휠이 없으므로 Python 3.13 이상은 사용할 수 없습니다.
- 여유 디스크 공간은 약 40 GB가 필요합니다. 전체 설치는 약 37 GB, 시각 기능을 제외하면 약 28 GB입니다.
  설치 후 `pip cache purge`로 약 6 GB를 비울 수 있습니다. 다운로드는 약 16 GB이며 30~60분 걸립니다.
- 언어 모델을 사용하려면 몇 달러를 충전한 [OpenRouter](https://openrouter.ai) 키 또는 27B 이상의 모델과 충분한
  VRAM을 갖춘 [Ollama](https://ollama.com)가 필요합니다. [언어 모델 선택](#언어-모델-선택)을 참고하세요.

## 언어 모델 선택

음성 인식·음성 합성·기억·시각 기능은 항상 내 PC에서 실행됩니다. 생각하고 답변을 작성하는 언어 모델은 다음 두 방식 중
하나로 실행합니다.

- **Semi-Local(권장):** 자신의 키로 [OpenRouter](https://openrouter.ai)를 이용합니다. 대부분의 경우 이 방식이
  적합합니다. 검증에 사용한 모델을 이용하고 응답이 빠르며, 비용은 월 몇 달러 정도입니다.
  하루 30번 대화하면 월 약 $1.50, 하루 100번이면 약 $5입니다.
- **Fully Local:** [Ollama](https://ollama.com)로 내 PC에서 실행합니다. **27B 파라미터 이상**의 모델을 사용하세요.
  안정적으로 모든 기능을 이용하려면 **70B 이상**을 권장합니다. 27B보다 작은 모델은 성격을 유지하지 못하거나,
  들은 내용을 잊거나, 답변 형식을 지키지 못할 수 있습니다. 첫 설정 창과 Setup → Brain에서도 안내합니다.
  로컬에서는 모든 추론 작업을 하나의 모델이 번갈아 처리하므로, 대화를 중단시킨 직후나 기억 저장·회고 중에는
  답변이 나오기까지 5~50초 걸릴 수 있습니다.

> **OpenRouter와 비용 안내.** OpenRouter 계정 하나로 여러 AI 모델을 이용할 수 있습니다. 자신의 키를 설정하면
> Amika가 검증에 사용한 모델로 추론 요청을 보내고, OpenRouter가 각 모델의 요금에 따라 청구합니다. **선불제**이므로
> 먼저 몇 달러를 충전하세요. 잔액이 없으면 모든 답변이 실패하고 채팅에 사유가 표시됩니다.
> 한 번 주고받는 데 약 **$0.002**가 듭니다. MekaHime의 기본 모델 사용 기록에서는 한 차례당 $0.00165였으며,
> 하루 30차례면 월 약 $1.50, 매일 한 시간씩 대화하면 약 $5입니다. **대화가 많은 날에는 하루 50센트에 이를 수 있습니다.**
> 한 시간의 음성 대화는 약 100차례이며, 매번 전체 캐릭터 설정과 필요한 기억을 다시 전송합니다(약 8,000토큰).
> 대화 사이에 회고와 기억 저장도 수행하며, 도우미(Hermes, nanoMuse)도 같은 키로 자체 모델을 사용합니다.
> 자신의 비용 표시는 Use 화면의 *Session cost*에서 확인할 수 있습니다.

로컬 언어 모델에는 음성 인식·기억·음성 합성에 쓰는 약 5.5 GB(시각 기능 포함 시 약 10 GB) 외에 별도 VRAM이 필요합니다.
`gemma3:27b` 같은 27B 모델은 약 19 GB, `qwen3:32b` 같은 32B 모델은 24 GB, `qwen2.5:72b` 같은 70B 모델은 50 GB가
필요합니다. 따라서 32 GB 그래픽 카드 한 장(RTX 5090)에는 Amika 전체 구성과 27B 모델이 함께 들어갑니다.
32B 모델은 시각 기능을 꺼야 함께 사용할 수 있고, 24 GB 카드에는 충분한 공간이 없습니다.
70B 모델을 함께 실행하려면 VRAM 72~96 GB의 워크스테이션용 카드가 필요합니다. 그렇지 않으면 별도 PC에서 Ollama를
실행하고 Setup에 주소를 입력하거나 Semi-Local을 사용하세요. 내부 프롬프트가 중국어이므로 중국어를 지원하는 모델을
선택해야 합니다. 예를 들어 `llama3.3:70b`는 중국어를 지원하지 않습니다. 전환 방법은 [선택 기능](#선택-기능)을 참고하세요.

**Amika와 함께 시험한 로컬 모델** — Ollama 용량은 ollama.com의 표기이며, 로드 시 메모리는 16k 컨텍스트 기준입니다.

| 모델 | Ollama | 다운로드 | 로드 시 VRAM | 시험 결과 |
|---|---|---|---|---|
| Gemma 4 26B MoE(26B, 토큰당 약 4B 활성) | `gemma4:26b` | 16~19 GB | 약 21 GB | 성격을 유지하며, 27B 미만 모델 중에서는 유일하게 그랬습니다. MoE 모델로, 한 사용자는 VRAM 6~10 GB와 CPU를 함께 사용해 실행했습니다. |
| Qwen 2.5 72B | `qwen2.5:72b` | 47 GB | 약 50 GB | 모든 기능을 이용하려면 VRAM 72~96 GB 카드 또는 별도 PC가 필요합니다. |
| GLM 5(744B, 40B 활성) | 로컬 모델 없음. Ollama는 2026-07-15에 `glm-5`를 중단했고 GLM 5.x 태그는 클라우드용입니다. | – | 4비트 기준 약 450 GB, 다중 GPU 서버 필요 | OpenRouter에서 사용하는 기본 심층 추론 모델입니다. OpenRouter에서는 월 몇 달러 정도로 이용합니다. |

## 접근 권한과 제어 범위

| 대상 | 사용하는 방식 | 제어 방법 |
|---|---|---|
| 마이크 | 전원이 켜져 있을 때 말을 듣습니다. 음성 인식은 내 PC에서 실행합니다. | Use 화면의 전원·마이크 버튼 |
| 웹캠(시각 기능) | 카메라를 켰을 때만 봅니다. 로컬의 작은 모델이 이미지를 설명하고, 언어 모델에는 그 설명만 전달됩니다. | Use 화면의 카메라 버튼. `settings.json`의 `"vision": {"enabled": false}`로 시각 기능을 제거할 수 있습니다. |
| 화면과 PC(브라우저, 파일, 이메일 초안) | 심부름을 요청했을 때 Hermes Agent나 nanoMuse 도우미를 통해서만 접근합니다. 위험한 작업은 승인을 기다립니다. | Tools 화면의 도우미 스위치. 설정 전까지 꺼져 있습니다. |
| 스마트 홈(Zigbee 플러그) | 연결한 플러그만 제어하며, IoT 안전 고지에 동의해야 사용할 수 있습니다. | Tools 화면의 IoT 스위치. `IoT\Setup_IoT_admin.bat`는 이 기능을 위한 선택적 설치입니다. |
| Discord와 Telegram | 자신의 서버와 봇을 통해 텍스트만 주고받습니다. 허용한 사용자 ID만 접근할 수 있습니다. | Setup → Text her |

Semi-Local에서는 입력한 말의 텍스트, 해당 대화에 필요한 기억, 카메라의 장면 설명이 OpenRouter로 전달됩니다.
음성과 카메라 이미지는 내 PC에 남습니다. Fully Local에서 도우미를 사용하지 않으면 PC 밖으로 전송하지 않습니다.

나중에 기억을 초기화하려면 Setup → Danger zone → **Wipe memory**를 선택하세요. 모든 대화와 사실을 잊으며,
`memory_f\backups\`에 백업이 남습니다. 대화 중이면 몇 초간 기다린 뒤 현재 작업을 중단하는 **Force wipe**를
선택할 수 있습니다. 명령줄에서는 `envs\brain\Scripts\python.exe launch.py --wipe-memory`를 사용하세요.
먼저 실행 중인 작업을 멈추려면 `--force`를 추가합니다. 실행 중이 아닐 때도 사용할 수 있습니다.

## 대화하기

OpenAmika 폴더에서 `Start_OpenAmika.bat`를 더블클릭하세요. PowerShell에서는 `.\Start_OpenAmika.bat`를 실행합니다.
콘솔 창 하나에서 전체 구성 요소를 시작하고, 준비되면 브라우저에서 **http://localhost:53000**을 엽니다.
Windows가 해당 포트를 예약한 경우 다음 빈 포트로 옮기며 콘솔에 주소가 표시됩니다. 보통 약 1분, 첫 실행은 조금 더 걸립니다.
첫 방문에서는 이름, 도시, 그리고 `brain\.env`에 아직 없다면 OpenRouter 키를 묻습니다. 전원 버튼을 누르고 말하거나
입력하세요. 브라우저가 소리를 재생할 수 있도록 페이지를 한 번 클릭하세요. 말을 멈추면 Amika가 먼저 말을 걸 수 있습니다.
대기 시간은 Amika의 음성이 끝난 시점부터 계산하며, Setup → You & Amika → **When you go quiet**에서
Normal, Rare, Off 중 선택할 수 있습니다.

각 페이지 오른쪽 위 표시등은 상태를 나타냅니다. 초록색이면 정상이며, 클릭하면 문제가 있는 부분을 볼 수 있습니다.
종료하려면 `Stop_OpenAmika.bat`를 더블클릭하거나 콘솔에서 Ctrl+C를 누르세요. 실행하지 않고 준비 상태를 확인하려면
`envs\brain\Scripts\python.exe launch.py --check`를 실행하세요. `result: ready` 또는 해결할 문제가 표시됩니다.

업데이트 방법은 [업데이트와 기억 보존](#업데이트와-기억-보존)을 참고하세요.

## 문제 해결

| 증상 | 해결 방법 |
|---|---|
| `The argument 'scripts\setup_windows.ps1' to the -File parameter does not exist` | 현재 창이 프로젝트 폴더에 있지 않습니다. `cd C:\OpenAmika`를 입력하고 다시 실행하세요. ZIP은 안쪽 `OpenAmika-main` 폴더입니다. |
| `Python 3.11 was not found` | Python 3.11을 설치하며 **Add python.exe to PATH**를 체크하고, 새 PowerShell 창에서 다시 설치하세요. 3.12도 사용할 수 있습니다. |
| 다운로드가 약 50 KB/s로 매우 느림 | 토큰이 없으면 Hugging Face가 다운로드 속도를 제한합니다. Ctrl+C로 중단하고 다시 실행한 뒤 [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)의 무료 Read 토큰을 입력하세요. 중단한 지점부터 이어받습니다. |
| `!! voice MekaHime_Amika  not downloaded: her license was not accepted` | 라이선스를 읽고 동의한다면 `envs\brain\Scripts\python.exe scripts\setup_tts.py`를 다시 실행해 `yes`를 입력하세요. |
| `!! voice MekaHime_Amika  Hugging Face refused the download (HTTP 401)` | 파일이 아직 공개되지 않았거나 `HF_TOKEN`이 잘못됐습니다. 같은 창에서 [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)의 읽기 토큰을 설정하고 다시 실행하세요(`$env:HF_TOKEN = "hf_..."`). |
| `download failed after 4 tries` 또는 `Check the internet connection` | 같은 명령을 다시 실행하면 이어받습니다. huggingface.co에 접속할 수 없는 네트워크라면 먼저 `$env:HF_ENDPOINT`를 Hugging Face 미러 주소로 설정하세요. 모든 파일은 동일하게 검증합니다. |
| `does not see the GPU (CUDA)` | NVIDIA 드라이버를 업데이트하고 다시 설치하세요. NVIDIA 카드가 없으면 `powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1 --cpu`를 사용하세요. |
| `The filename or extension is too long` | Windows 경로가 너무 깁니다. `C:\OpenAmika`처럼 짧은 경로로 옮긴 뒤 다시 설치하세요. |
| `settings.json not found` | 먼저 `powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1`을 실행하세요. |
| 화면에 `No Live2D model yet` 또는 `launch.py --check`에 `!! Live2D model` / `!! her voice`가 표시됨 | `envs\brain\Scripts\python.exe scripts\setup_tts.py`를 실행하세요. |
| `no OpenRouter key yet` | 첫 설정 창이나 Setup → Brain에 키를 입력하세요. |
| 콘솔에 `moved to … in settings.json` 또는 `[Errno 13] … 53000`이 표시됨 | Windows가 포트를 예약했습니다(Hyper-V, WSL2, Docker Desktop). 자동으로 다음 빈 포트로 옮기므로 콘솔 위쪽 주소를 여세요. |
| `!! TTS (voice)  port 8002 answers but has no voice MekaHime_Amika` | 다른 음성 서버가 같은 포트를 사용 중입니다. OpenSakura도 8002를 사용합니다. 해당 서버를 종료하거나 `settings.json`의 `tts_url`과 `services.tts`(`--port`, `health`)에서 `8002`를 다른 포트로 바꾸세요. |
| 모든 답변이 실패함 | 채팅에 제공자의 오류 사유가 표시됩니다. `no credits`이면 [OpenRouter](https://openrouter.ai/settings/credits)에서 충전하세요. 모델이 사라졌다면 Setup → Brain → **Switch back to the OpenRouter preset**을 선택하세요. 키가 잘못됐다면 Setup → Brain에 새 키를 입력하세요. 재시작 없이 바로 적용됩니다. |
| 텍스트는 나오지만 소리가 안 남 | 실행 후 약 20초간 음성 서버를 기다리고 페이지를 한 번 클릭하세요. TTS 상태 표시등이 초록색이어야 합니다. |
| 대문자로 쓴 단어를 한 글자씩 읽음 | 현재는 대문자로 강조한 문장을 소문자로 바꿔 읽도록 수정돼 있습니다. 한 글자씩 읽어야 하는 약어는 `config/word_replace.json`의 `"tts_keep_caps"`에 넣으세요. |
| 음성이 끊기거나 매우 느림 | 그래픽 카드를 사용하는 다른 프로그램을 닫거나 `settings.json`에서 `"vision": {"enabled": false}`로 시각 기능을 끄세요. |
| Ollama에서 성격을 유지하지 못하거나 기억을 잊거나 답변 형식이 깨짐 | 모델이 너무 작습니다. 27B 이상, 모든 기능을 안정적으로 이용하려면 70B 이상을 사용하세요. 또는 Setup → Brain → OpenRouter → **Switch back to the OpenRouter preset**을 선택하세요. |
| Ollama에서 답변이 매우 느림 | `ollama ps`가 `100% GPU` 대신 CPU/GPU 분할을 표시하면 Amika와 모델이 함께 VRAM에 들어가지 않는 것입니다. `100% GPU`여도 대화를 중단시킨 직후나 기억 저장·회고 중의 지연은 정상입니다. [언어 모델 선택](#언어-모델-선택)을 참고하세요. |
| 오류를 읽기 전에 콘솔이 닫힘 | 현재는 오류가 발생하면 창을 유지하고 `logs\launcher.log` 경로를 안내합니다. |
| 기억이나 전체 설정 초기화 시 `Amika is busy`가 표시됨 | 잠시 기다린 뒤에도 작업 중이면 **Force wipe (she stops what she is doing)**를 누르세요. 어느 쪽이든 백업은 유지됩니다. |
| Setup 화면에 `Model selection is busy`가 표시됨 | 옆의 **Unlock**을 누르면 현재 작업을 중단하고 모델을 전환합니다. |
| 콘솔의 brain 항목 또는 Setup의 `brain start`가 빨간색임 | 포트 사용 중, 환경 손상, 모델 용량 초과, 키 누락 등 원인이 해당 행에 표시됩니다. |
| Tools 화면에서 도우미 카드가 빨간색이거나 Hermes/nanoMuse에 연결할 수 없다고 함 | `envs\brain\Scripts\python.exe launch.py --check`를 실행하고 `agent`, `hermes key` 항목을 확인하세요. 메시지와 해결 방법은 [docs/TOOLS.md](docs/TOOLS.md#when-it-does-not-work)에 있습니다. |

각 구성 요소는 `logs\`에 로그를 기록합니다. 그 밖의 문제는 `envs\brain\Scripts\python.exe launch.py --diagnose`로
진단하세요. 시작 점검, 각 로그의 끝부분, 키를 제외한 설정, 버전, 디스크·VRAM 여유 공간을 담은 ZIP 하나를 `logs\`에
생성합니다. [Discord](https://discord.gg/mekahime)나 [GitHub 이슈](https://github.com/zeekk0/OpenAmika/issues)에
문의할 때 첨부하세요. AI 코딩 에이전트를 사용한다면 [README_IF_YOU_ARE_AI_AGENT.md](README_IF_YOU_ARE_AI_AGENT.md)를 알려주세요.

## 선택 기능

- **Fully Local:** [Ollama](https://ollama.com)를 설치하고 `ollama pull gemma3:27b`를 실행하세요.
  다운로드는 17 GB이며, 다른 27B 이상 모델도 가능합니다. [언어 모델 선택](#언어-모델-선택)을 참고하세요.
  Setup → Brain → Ollama → Detect models → Use this model을 선택하면 키 없이 사용할 수 있습니다.
  다른 PC의 Ollama는 먼저 해당 주소를 입력한 뒤 Detect models를 누르세요.
- **도우미:** Hermes Agent나 nanoMuse가 심부름을 하고, 책상 보기에 진행 상황이 표시됩니다.
  [아래 안내](#도우미-hermes와-nanomuse)를 참고하세요. 다른 MCP 서버도 Tools 화면에서 연결할 수 있습니다.
  자세한 내용은 [docs/TOOLS.md](docs/TOOLS.md)에 있습니다.
- **스마트 홈:** 선택 기능이며 다른 구성 요소에 필요하지 않습니다. Zigbee 플러그를 제어할 수 있습니다.
  [IoT/README.md](IoT/README.md)를 참고하세요. `IoT\Setup_IoT_admin.bat`는 필요한 항목을 관리자 권한으로 설치합니다.
  Zigbee 플러그가 없다면 건너뛰세요. Tools 화면에서 [IoT 안전 고지](docs/IOT_DISCLAIMER.md)를 읽고 동의하기 전까지
  꺼져 있습니다. 언어 모델은 실수할 수 있으므로 히터·잠금장치·밸브 등 위험한 장치를 연결하지 마세요.
- **메신저:** Discord나 Telegram에서 텍스트로 대화할 수 있습니다. [docs/MESSENGERS.md](docs/MESSENGERS.md)를 참고하세요.
  Discord 봇은 자신의 서버에서 실행하며, DM을 보내기 전에 사용자와 봇이 같은 서버에 있어야 합니다.
- **휴대전화:** `Tailscale_Serve_OpenAmika.bat`로 [Tailscale](https://tailscale.com)에 연결된 자신의 기기에서 접속할 수 있습니다.
- **데스크톱 펫:** 다른 창 위에 Amika만 표시할 수 있습니다. Use 화면의 **Desktop pet**을 누르세요.
  [아래 안내](#데스크톱-펫-모드)를 참고하세요.

## 데스크톱 펫 모드

Amika만 표시하는 투명 창을 다른 프로그램 위에 띄울 수 있습니다. Use 화면과 같은 음성·입 모양·표정을 지원하며 Windows 전용입니다.

**Use 화면에서 열기:** 무대 위쪽의 **Desktop pet**을 누르세요.

1. 처음에는 pywebview를 설치하라는 안내가 나옵니다. 몇 MB 정도이며 **Install and open**을 누르면 됩니다.
2. 데스크톱에 창이 열리고 현재 대화가 이어집니다. 전원과 마이크 상태도 유지됩니다.
3. 원래 페이지에는 *Amika is on your desktop*이 표시됩니다. **Bring her back here**를 누르면 페이지로 돌아옵니다.

이 버튼은 Amika를 실행 중인 PC의 브라우저에서만 보이며 휴대전화에는 나타나지 않습니다.

**처음부터 데스크톱에서 시작하기:** `Start_OpenAmika.bat` 대신 `Start_OpenAmika_Pet.bat`를 더블클릭하거나
`launch.py --pet`을 실행하세요. 준비되면 브라우저 대신 데스크톱 창이 열립니다. 이 방식은 자동으로 설치하지 않습니다.
설치하지 않았다면 평소처럼 브라우저 페이지가 열리며, 그곳의 **Desktop pet** 버튼으로 설치할 수 있습니다.
한 번만 다음 명령으로 직접 설치해도 됩니다.

```powershell
envs\brain\Scripts\python.exe -m pip install -r brain\requirements-pet.txt
```

Amika 위에 마우스를 올리면 전원·마이크·전체 페이지·닫기 버튼이 있는 작은 도구 모음이 나타납니다.
마이크를 눌러 평소처럼 대화하세요. 드래그로 이동하고 마우스 휠로 크기를 바꿀 수 있으며, 마지막 위치를 기억합니다.
창을 닫아도 전체 프로그램은 종료되지 않습니다. **Desktop pet** 버튼이나
`envs\brain\Scripts\python.exe pet.py`로 다시 열고, `Stop_OpenAmika.bat`로 전체를 종료하세요.

- 한 번에 한 곳에서 대화합니다. 데스크톱 모드에서는 페이지가 대기를 유지합니다. 페이지의 **Bring her back here**나
  데스크톱 창의 전체 페이지 버튼을 누르면 대화 위치가 바뀝니다.
- 데스크톱 창에는 입력란이 없습니다. 음성으로 대화하거나 페이지로 돌아와 입력하세요.
- 처음에는 전체 페이지에서 설정하세요. 첫 설정 창, 카메라, 배경 사진, 도우미 종이 인형은 전체 페이지에 있습니다.
- 투명한 모서리 부분도 클릭을 받으므로 창 크기를 Amika에 맞게 조절하세요.

## 도우미: Hermes와 nanoMuse

Amika는 PC의 [Hermes Agent](https://hermes-agent.nousresearch.com)나 [nanoMuse](https://github.com/nano-muse/nanoMuse)에
심부름을 맡길 수 있습니다. 도우미는 웹 검색, 브라우저 사용, 파일 작업을 합니다. Amika가 도울지 판단하고 먼저 답한 뒤
도우미에게 작업을 전달합니다. 도우미의 질문을 중계하고 결과를 알려줍니다. 도우미가 켜져 있으면 무대 오른쪽 아래에
**책상 보기(지금 하는 일)**가 나타납니다. MekaHime의 작은 종이 인형이 도우미의 상태를 연기해 진행 상황을 보여줍니다.
각 도우미는 자체 OpenRouter 모델을 사용하며 Amika에 설정한 키로 이용할 수 있습니다.

**Hermes Agent:** PowerShell에서 설치하세요. 아래 명령은 대화형 질문 없이 설치하며, 뒤의 명령으로 OpenAmika에 필요한
설정을 진행합니다.

```powershell
& ([scriptblock]::Create((irm https://hermes-agent.nousresearch.com/install.ps1))) -NonInteractive
```

새 PowerShell 창에서 다음을 실행하세요.

```powershell
hermes model                                    # OpenRouter 선택, 키 입력, "Enter custom model name"에 z-ai/glm-5 입력
$key = [guid]::NewGuid().ToString('N')          # API 서버용 무작위 키
hermes config set API_SERVER_ENABLED true
hermes config set API_SERVER_KEY $key
hermes gateway stop                             # 이미 실행 중인 Hermes는 재시작해야 새 키를 읽습니다.
```

**nanoMuse:** `Nanomuse` 폴더에 저장소를 복제하고 `config.toml`을 작성한 뒤 자체 vault에 키를 저장하세요.
명령과 파일 내용은 [docs/TOOLS.md](docs/TOOLS.md#set-up-nanomuse)에 있습니다.

**연결하기:** OpenAmika 폴더에 `config\tools.json`이 아직 없을 때만
`Copy-Item config\tools.example.json config\tools.json`을 실행하고, `notepad config\tools.json`으로 여세요.
최상위와 사용할 도우미 항목의 `"enabled": true`를 설정하세요. nanoMuse의 `"NANOMUSE_LANGUAGE"`는 응답 언어입니다.
`"en"`, `"ja"`, `"zh-CN"` 중 설정할 수 있습니다. Hermes는 다음 명령으로 키를 복사하고
`"HERMES_API_KEY"` 값에 Ctrl+V로 붙여넣으세요.

```powershell
(Select-String -Path "$env:LOCALAPPDATA\hermes\.env" -Pattern '^API_SERVER_KEY=(.+)').Matches[0].Groups[1].Value | Set-Clipboard
```

저장한 뒤 `.\Start_OpenAmika.bat`로 실행하면 도우미도 자동으로 시작합니다. Tools 화면에서 도우미 카드가
초록색(`agent online`)으로 바뀝니다.

**책상 보기:** Use 화면을 열면 작은 종이 인형이 무대에 나타납니다. 예를 들어 “Can you have Hermes check tomorrow's weather?”라고
물어보세요. Amika가 답하고 말풍선에 작업을 입력하면 책상 보기에 진행 상황이 표시됩니다. 도우미가 일하는 동안 인형이
생각하고, 도우미의 작업 단계를 말풍선으로 보여줍니다. 질문이나 승인이 필요하면 놀란 표정을 짓습니다.
말로 yes/no를 답하거나 Use 화면에서 Approve를 누르세요. 결과가 나오면 인형이 기뻐하고 Amika가 결과를 알려줍니다.
이 기능은 `setup_tts.py`에 포함되며 요약에 `OK paper doll Host`로 표시됩니다.

각 단계와 메시지의 의미는 [docs/TOOLS.md](docs/TOOLS.md#her-helpers-set-up-hermes-agent-and-nanomuse)를 참고하세요.

## 라이선스

- OpenAmika 코드는 **MIT**입니다([LICENSE](LICENSE)). 외부 구성 요소에는 각각의 라이선스가 적용됩니다
  ([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)). `ui/vendor/`의 Live2D Cubism Core는 MIT가 아닙니다.
- **Amika 자체는 MIT가 아닙니다.** 캐릭터·아트·음성·Live2D 모델과 가중치,
  책상 보기의 종이 인형([MekaHime/MekaHime_Amika](https://huggingface.co/MekaHime/MekaHime_Amika))은 MekaHime Inc.의 소유이며,
  개인 이용 라이선스로 무료 제공됩니다. 개인 용도, 만 18세 이상만 허용하며, 재배포·재호스팅 및 이를 이용한 다른 모델 학습은
  금지됩니다. 창작자에게는 두 가지 예외가 있습니다. 소셜 미디어의 영상·방송·광고·멤버십·후원 수익은
  MekaHime.AI를 눈에 띄게 표시하면 금액 제한 없이 허용됩니다. 개인이 직접 다시 그린 팬아트로 만든 팬 상품은
  총 US$1,000까지 허용됩니다. MekaHime가 웹사이트나 소셜 미디어에 게시한 원본 이미지는 사용할 수 없으며,
  상품의 보이는 면에 “MekaHime.AI”와 작은 “Fan Art” 표시를 넣어야 합니다. 그 밖의 상업적 이용은
  MekaHime(hi@mekahime.com)의 라이선스가 필요합니다.
  최종적으로는 Hugging Face의 [LICENSE](https://huggingface.co/MekaHime/MekaHime_Amika/blob/main/LICENSE)가 적용됩니다.
- Hermes Agent(MIT)와 nanoMuse(GPL-3.0-or-later)는 사용자가 별도로 설치하는 프로그램이며 OpenAmika는 이들과 통신만 합니다.
- [SenseVoice](https://github.com/FunAudioLLM/SenseVoice), [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS),
  [bge-m3](https://huggingface.co/BAAI/bge-m3), [Qwen3-VL](https://github.com/QwenLM/Qwen3-VL),
  [pixi-live2d-display](https://github.com/guansss/pixi-live2d-display),
  [Live2D Cubism SDK](https://www.live2d.com/en/sdk/about/), [OpenRouter](https://openrouter.ai),
  [Ollama](https://ollama.com), [Model Context Protocol](https://modelcontextprotocol.io)을 기반으로 합니다. 감사합니다.

## 문의와 지원

질문과 버그 제보: [GitHub 이슈](https://github.com/zeekk0/OpenAmika/issues), hi@mekahime.com,
[Discord](https://discord.gg/mekahime). 프로젝트 후원: https://www.mekahime.com/donate

<p align="center">
  <a href="https://www.mekahime.com">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/images/mekahime-logo-white.png">
      <img src="docs/images/mekahime-logo-card.png" alt="MekaHime" width="220">
    </picture>
  </a>
</p>
