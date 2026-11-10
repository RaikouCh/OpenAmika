<!-- Translated from README.md; keep in sync when README.md changes. -->
<div align="center">

<img src="docs/images/amika-avatar.png" alt="Amika" width="180">

# OpenAmika

**Chào bạn! Mình là Amika** — người bạn đồng hành AI của MekaHime, mã nguồn mở

Amika là một cô gái anime Live2D, trò chuyện với bạn bằng giọng nói và văn bản theo thời gian thực, ghi nhớ bạn
và sống cùng bạn trong thành phố của bạn. Cô ấy chạy trên chính PC của bạn, dùng OpenRouter hoặc hoàn toàn cục bộ
với Ollama. Một bản lưu trữ sẵn đang chạy tại [mekahime.com/amika](https://www.mekahime.com/amika).

[简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [English](README.md) | **Tiếng Việt** | [한국어](README.ko.md)

[![Made with Love](https://img.shields.io/badge/Made%20with-Love-ff69b4)](https://www.mekahime.com/openamika)
[![GitHub](https://img.shields.io/badge/GitHub-zeekk0%2FOpenAmika-181717?logo=github)](https://github.com/zeekk0/OpenAmika)
[![Release](https://img.shields.io/github/v/release/zeekk0/OpenAmika?logo=github&color=d8b4e2)](https://github.com/zeekk0/OpenAmika/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-43b581)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20(Linux%20untested)-0078D6?logo=windows&logoColor=white)](#những-gì-bạn-cần)
[![Python 3.11](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3119/)

[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-MekaHime%2FMekaHime__Amika-ffcc4d)](https://huggingface.co/MekaHime/MekaHime_Amika)
[![Discord](https://img.shields.io/badge/Discord-MekaHime-5865F2?logo=discord&logoColor=white)](https://discord.gg/mekahime)
[![Website](https://img.shields.io/badge/website-mekahime.com-d8b4e2)](https://www.mekahime.com/openamika)
[![Try Online](https://img.shields.io/badge/Try%20Online-mekahime.com%2Famika-e58fb8)](https://www.mekahime.com/amika)
[![Tests](https://github.com/zeekk0/OpenAmika/actions/workflows/tests.yml/badge.svg)](https://github.com/zeekk0/OpenAmika/actions/workflows/tests.yml)
[![GitHub stars](https://img.shields.io/github/stars/zeekk0/OpenAmika?style=social)](https://github.com/zeekk0/OpenAmika/stargazers)

</div>

> 💖 Nếu Amika làm ngày của bạn vui hơn, hãy tặng chúng mình một ⭐ trên [GitHub](https://github.com/zeekk0/OpenAmika) — điều đó giúp nhiều người tìm thấy cô ấy hơn! · Ủng hộ dự án: https://www.mekahime.com/donate

## Những gì bạn cần

- Windows 10 hoặc 11 và một card đồ họa NVIDIA (dòng RTX 20 trở lên, bộ nhớ video từ 8 GB trở lên; đôi mắt camera
  của cô ấy cần 16 GB), kèm driver mới
- [Python 3.11](https://www.python.org/downloads/release/python-3119/) (tích chọn **Add python.exe to PATH** khi
  cài đặt) và [Git](https://git-scm.com/download/win)
- Khoảng 45 GB dung lượng đĩa trống. Quá trình cài đặt tải về khoảng 15–20 GB và mất 30–60 phút
- Một key [OpenRouter](https://openrouter.ai) cho mô hình ngôn ngữ của cô ấy (khuyên dùng: vài đô la mỗi tháng),
  hoặc [Ollama](https://ollama.com) với một mô hình từ 27B trở lên và một card đồ họa đủ mạnh để chạy nó (xem
  [Mô hình ngôn ngữ nào?](#mô-hình-ngôn-ngữ-nào))

## Mô hình ngôn ngữ nào?

Tai, giọng nói, trí nhớ và đôi mắt của cô ấy luôn chạy trên PC của bạn. Mô hình ngôn ngữ của cô ấy, phần suy nghĩ
và viết câu trả lời, chạy theo một trong hai cách:

- **Bán cục bộ (khuyên dùng)**: qua [OpenRouter](https://openrouter.ai) bằng key của chính bạn. Trong hầu hết các
  trường hợp, đây là lựa chọn tốt hơn: cô ấy dùng các mô hình đã được kiểm thử cùng cô ấy, trả lời nhanh, và chỉ tốn
  vài đô la mỗi tháng (khoảng $1.50 nếu bạn trò chuyện 30 lượt mỗi ngày, khoảng $5 nếu 100 lượt mỗi ngày).
- **Hoàn toàn cục bộ**: trên PC của bạn với [Ollama](https://ollama.com). Hãy dùng mô hình từ **27B tham số trở
  lên**; **70B trở lên** cho trải nghiệm đầy đủ và đáng tin cậy. Mô hình nhỏ hơn 27B có thể rất tệ: cô ấy mất đi
  tính cách của mình, quên những gì bạn đã nói và làm hỏng định dạng câu trả lời. Mô hình cục bộ cũng chậm hơn: mọi
  suy nghĩ của cô ấy đều lần lượt chạy trên nó, nên sau khi bạn ngắt lời cô ấy, hoặc trong lúc cô ấy lưu trí nhớ hay
  suy ngẫm, một câu trả lời có thể mất 5–50 giây.

Mô hình cục bộ cần bộ nhớ video riêng, ngoài khoảng 6 GB mà tai, trí nhớ và giọng nói của cô ấy dùng (khoảng 10 GB
khi bật đôi mắt): khoảng 19 GB cho mô hình 27B như `gemma3:27b`, 24 GB cho mô hình 32B như `qwen3:32b`, và 50 GB
cho mô hình 70B như `qwen2.5:72b`. Vì vậy, một card 32 GB (RTX 5090) chứa được một mô hình 27B cùng với toàn bộ
cô ấy (mô hình 32B thì chỉ khi tắt đôi mắt của cô ấy); card 24 GB thì không. Mô hình 70B chỉ vừa cùng với cô ấy
trên card workstation 72–96 GB. Nếu không, hãy chạy Ollama trên một PC thứ hai (trang Setup nhận địa chỉ của nó),
hoặc ở lại với Bán cục bộ. Dù chạy mô hình nào, hãy chọn mô hình hỗ trợ tiếng Trung, vì prompt của cô ấy được viết
bằng tiếng đó (`llama3.3:70b`, chẳng hạn, thì không hỗ trợ). Cách chuyển đổi:
[Tiện ích bổ sung](#tiện-ích-bổ-sung).

## Cài đặt cô ấy

**Muốn xem video?** Hướng dẫn 7 bước kèm video 3 phút, cùng các câu hỏi thường gặp và cách khắc phục (trang tiếng
Anh): [mekahime.com/openamikatutorial](https://www.mekahime.com/openamikatutorial).

Mở PowerShell (cửa sổ thường, không chạy với quyền administrator) và chạy từng dòng một. Các lệnh này sẽ cài đặt
cô ấy vào `C:\OpenAmika`, một thư mục đường dẫn ngắn mà OneDrive không đồng bộ:

```powershell
cd C:\
git clone https://github.com/zeekk0/OpenAmika.git
cd OpenAmika
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1   # bộ não, tai, trí nhớ và đôi mắt của cô ấy
envs\brain\Scripts\python.exe scripts\setup_tts.py                   # giọng nói, mô hình Live2D và hình nhân giấy của cô ấy: gõ yes
.\Start_OpenAmika.bat                                                # khởi động cô ấy
```

Giọng nói, mô hình Live2D và hình nhân giấy của cô ấy được cung cấp miễn phí theo giấy phép sử dụng cá nhân của
MekaHime (xem [Giấy phép](#giấy-phép)): dòng `setup_tts.py` hiển thị giấy phép trước, và chỉ tải các file của cô
ấy sau khi bạn gõ `yes`.

Cả hai lệnh cài đặt đều kết thúc bằng một bản tóm tắt, mỗi thành phần một dòng: `OK` khi đã xong, `!!` kèm cách
sửa khi chưa xong, và `--` chỉ là thông tin (ví dụ: chưa có key OpenRouter, lần truy cập đầu tiên của bạn sẽ hỏi
key). Chạy lại một lệnh sẽ tiếp tục từ chỗ đã xong và bỏ qua mọi thứ đã hoàn thành. Khi bản tóm tắt của
`setup_tts.py` hiển thị `OK voice MekaHime_Amika` và `OK Live2D model Amika`, cô ấy đã có giọng nói và cơ thể của
mình; `OK paper doll Host` là hình nhân giấy đóng vai thay cho các trợ lý của cô ấy
([Các trợ lý của cô ấy](#các-trợ-lý-của-cô-ấy-hermes-và-nanomuse)).

## Trò chuyện với cô ấy

Nhấn đúp `Start_OpenAmika.bat` trong thư mục OpenAmika (trong PowerShell: `.\Start_OpenAmika.bat`). Một cửa sổ
console sẽ khởi động toàn bộ cô ấy, và trình duyệt sẽ mở **http://localhost:53000** khi cô ấy đã sẵn sàng: khoảng
một phút, lần đầu tiên thì lâu hơn vài phút. Trong lần truy cập đầu tiên, cô ấy sẽ tự giới thiệu và hỏi tên, thành
phố của bạn và, nếu `brain\.env` chưa có, key OpenRouter của bạn. Sau đó nhấn nút nguồn rồi nói chuyện hoặc gõ chữ.
Nhấn vào trang một lần để trình duyệt cho phép cô ấy cất tiếng.

Đèn ở góc trên bên phải của mỗi trang cho biết tình trạng của cô ấy: màu xanh nghĩa là mọi thứ đều hoạt động; nhấn
vào đó để xem phần nào chưa ổn. Nhấn đúp `Stop_OpenAmika.bat` (hoặc nhấn Ctrl+C trong console của cô ấy) để dừng
cô ấy. Để kiểm tra mọi thứ mà không khởi động gì cả, hãy chạy
`envs\brain\Scripts\python.exe launch.py --check`: lệnh kết thúc với `result: ready`, hoặc nêu ra những gì cần sửa.

Để cập nhật cô ấy: dừng cô ấy, chạy `git stash`, `git pull` và `git stash pop` trong thư mục OpenAmika (các lệnh này
giữ nguyên tên, thành phố và các chỉnh sửa của bạn), rồi chạy lại hai lệnh cài đặt (chúng chỉ tải về những gì đã thay
đổi).

## Nếu có sự cố

| bạn thấy gì | phải làm gì |
|---|---|
| `Python 3.11 was not found` | Cài đặt Python 3.11 (tích chọn "Add python.exe to PATH"), mở một cửa sổ PowerShell mới và chạy lại quá trình cài đặt. |
| `!! voice MekaHime_Amika  not downloaded: her license was not accepted` | Chạy lại `envs\brain\Scripts\python.exe scripts\setup_tts.py` rồi gõ `yes`. |
| `!! voice MekaHime_Amika  Hugging Face refused the download (HTTP 401)` | Các file của cô ấy chưa được công khai, hoặc `HF_TOKEN` của bạn sai. Đặt một read token lấy từ [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) trong cùng cửa sổ (`$env:HF_TOKEN = "hf_..."`) rồi chạy lại lệnh. |
| `download failed after 4 tries` hoặc `Check the internet connection` | Chạy lại cùng lệnh đó: nó sẽ tiếp tục từ chỗ đã dừng. Nếu mạng của bạn không truy cập được huggingface.co, hãy đặt `$env:HF_ENDPOINT` thành một Hugging Face mirror trước; mọi file vẫn được kiểm tra. |
| `does not see the GPU (CUDA)` | Cập nhật driver NVIDIA rồi chạy lại quá trình cài đặt. Nếu không có card NVIDIA: `powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1 --cpu`. |
| `The filename or extension is too long` | Đường dẫn thư mục quá dài đối với Windows: chuyển OpenAmika sang một thư mục đường dẫn ngắn như `C:\OpenAmika` rồi chạy cài đặt ở đó. |
| `settings.json not found` | Chạy `powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1` trước. |
| `No Live2D model yet` trên sân khấu, hoặc `!! Live2D model` / `!! her voice` trong `launch.py --check` | Chạy `envs\brain\Scripts\python.exe scripts\setup_tts.py`. |
| `no OpenRouter key yet` (`launch.py --check`, bản tóm tắt cài đặt) | Dán key của bạn trong trình hướng dẫn chạy lần đầu, hoặc sau `OPENROUTER_API_KEY=` trong `brain\.env`. |
| `!! TTS (voice)  port 8002 answers but has no voice MekaHime_Amika` | Một voice server khác đang dùng cổng của cô ấy (của OpenSakura cũng dùng 8002). Hãy dừng nó, hoặc đổi cho cô ấy một cổng khác: thay `8002` trong `tts_url` và trong `services.tts` (`--port`, `health`) ở `settings.json`. |
| Cô ấy trả lời bằng chữ nhưng bạn không nghe thấy gì | Sau khi khởi động, hãy đợi giọng của cô ấy khoảng 20 giây rồi nhấn vào trang một lần. Đèn tình trạng phải hiển thị TTS màu xanh. |
| Giọng của cô ấy bị giật hoặc rất chậm | Đóng các chương trình khác đang dùng card đồ họa, hoặc tắt đôi mắt của cô ấy: `"vision": {"enabled": false}` trong `settings.json`. |
| Khi dùng Ollama, cô ấy không còn giống chính mình, quên mọi thứ, hoặc câu trả lời bị hỏng | Mô hình quá nhỏ. Hãy dùng mô hình từ 27B trở lên (70B trở lên để có trải nghiệm đầy đủ), hoặc quay lại OpenRouter: Setup → Brain → OpenRouter → "Switch back to the OpenRouter preset". |
| Khi dùng Ollama, cô ấy trả lời rất chậm | Nếu `ollama ps` hiển thị tỉ lệ CPU/GPU thay vì `100% GPU`, nghĩa là mô hình không vừa trong bộ nhớ video cùng với cô ấy. Với `100% GPU`, việc trả lời chậm sau khi bạn ngắt lời cô ấy, hoặc trong lúc cô ấy lưu trí nhớ hay suy ngẫm, là bình thường đối với mô hình cục bộ. Xem [Mô hình ngôn ngữ nào?](#mô-hình-ngôn-ngữ-nào). |
| Thẻ của một trợ lý trên trang Tools bị đỏ, hoặc cô ấy nói không kết nối được tới Hermes hay nanoMuse | Chạy `envs\brain\Scripts\python.exe launch.py --check` và xem các dòng `agent` và `hermes key`; ý nghĩa và cách sửa của từng thông báo đều có trong [docs/TOOLS.md](docs/TOOLS.md#when-it-does-not-work). |

Mỗi thành phần đều ghi log vào `logs\`. Với bất kỳ vấn đề nào khác, hãy hỏi trên
[Discord](https://discord.gg/mekahime) hoặc mở một
[issue](https://github.com/zeekk0/OpenAmika/issues). Bạn đang dùng AI coding agent? Hãy trỏ nó tới
[README_IF_YOU_ARE_AI_AGENT.md](README_IF_YOU_ARE_AI_AGENT.md).

## Tiện ích bổ sung

- **Hoàn toàn cục bộ**: cài đặt [Ollama](https://ollama.com), chạy `ollama pull gemma3:27b` (17 GB; hoặc một mô hình
  khác từ 27B trở lên, xem [Mô hình ngôn ngữ nào?](#mô-hình-ngôn-ngữ-nào)), rồi trên trang Setup chọn Brain →
  Ollama → Detect models → Use this model. Không cần key. Với Ollama trên một PC khác, hãy nhập địa chỉ của nó ở đó
  trước khi nhấn Detect models.
- **Các trợ lý của cô ấy**: Hermes Agent hoặc nanoMuse chạy việc vặt giúp cô ấy, với hình nhân giấy đứng bên cạnh
  cô ấy trên sân khấu ([bên dưới](#các-trợ-lý-của-cô-ấy-hermes-và-nanomuse)). Các MCP server khác cũng dùng được,
  trên trang Tools ([docs/TOOLS.md](docs/TOOLS.md)).
- **Nhà thông minh**: các ổ cắm Zigbee mà cô ấy có thể bật/tắt ([IoT/README.md](IoT/README.md)). Tính năng này vẫn
  tắt cho đến khi bạn đọc và chấp nhận tuyên bố an toàn IoT ([docs/IOT_DISCLAIMER.md](docs/IOT_DISCLAIMER.md)) trên
  trang Tools. Cô ấy chạy trên các mô hình ngôn ngữ và có thể mắc sai lầm: đừng bao giờ kết nối máy sưởi, khóa cửa,
  van nước hay bất cứ thứ gì có thể gây hại.
- **Nhắn tin cho cô ấy** qua Discord hoặc Telegram ([docs/MESSENGERS.md](docs/MESSENGERS.md)).
- **Điện thoại của bạn**: `Tailscale_Serve_OpenAmika.bat` giúp bạn truy cập cô ấy trên các thiết bị của mình qua
  [Tailscale](https://tailscale.com).

## Các trợ lý của cô ấy: Hermes và nanoMuse

Cô ấy có thể giao việc vặt cho một chương trình trợ lý trên PC của bạn,
[Hermes Agent](https://hermes-agent.nousresearch.com) hoặc
[nanoMuse](https://github.com/nano-muse/nanoMuse): nó tìm kiếm trên web, dùng trình duyệt và làm việc với các file.
Cô ấy quyết định có giúp hay không, giao việc cho trợ lý sau khi đã trả lời bạn, chuyển lại các câu hỏi của nó, và
nói cho bạn kết quả bằng lời của chính mình. Khi một trợ lý đang bật, hình nhân giấy của MekaHime đứng ở góc dưới
bên phải sân khấu của cô ấy và đóng vai phía trợ lý. Mỗi trợ lý chạy mô hình riêng của mình trên OpenRouter, và key
mà cô ấy đang dùng cũng dùng được cho nó.

**Hermes Agent**: cài đặt nó từ một cửa sổ PowerShell. Dạng cài đặt này không hỏi gì cả; các dòng sau đó sẽ thực
hiện phần thiết lập mà OpenAmika cần:

```powershell
& ([scriptblock]::Create((irm https://hermes-agent.nousresearch.com/install.ps1))) -NonInteractive
```

Sau đó, trong một cửa sổ PowerShell mới:

```powershell
hermes model                                    # chọn OpenRouter, dán key của bạn, rồi nhập "Enter custom model name": z-ai/glm-5
$key = [guid]::NewGuid().ToString('N')          # một key ngẫu nhiên cho API server của nó
hermes config set API_SERVER_ENABLED true
hermes config set API_SERVER_KEY $key
hermes gateway stop                             # một Hermes đang chạy sẽ chỉ đọc key khi nó khởi động lại
```

**nanoMuse**: clone nó vào thư mục `Nanomuse`, tạo cho nó một `config.toml` và đặt key của bạn vào vault riêng
của nó; các lệnh và nội dung file có trong [docs/TOOLS.md](docs/TOOLS.md#set-up-nanomuse).

**Kết nối các trợ lý.** Trong thư mục OpenAmika, chạy `Copy-Item config\tools.example.json config\tools.json` (chỉ
khi chưa có `config\tools.json`) và `notepad config\tools.json`. Đặt `"enabled": true` ở đầu file và trong mục của
trợ lý. Với nanoMuse, hãy đặt `"NANOMUSE_LANGUAGE"` thành `"en"` (nanoMuse chỉ hỗ trợ en, ja và zh-CN; trợ lý sẽ trả lời bằng tiếng Anh). Với Hermes,
hãy sao chép key của nó bằng dòng lệnh này rồi dán (Ctrl+V) vào `"HERMES_API_KEY"`:

```powershell
(Select-String -Path "$env:LOCALAPPDATA\hermes\.env" -Pattern '^API_SERVER_KEY=(.+)').Matches[0].Groups[1].Value | Set-Clipboard
```

Lưu lại rồi khởi động cô ấy (`.\Start_OpenAmika.bat`): cô ấy sẽ tự khởi động các trợ lý của mình. Trên trang Tools,
thẻ của trợ lý sẽ chuyển sang màu xanh (`agent online`).

**Gặp gỡ hình nhân giấy.** Mở trang Use: hình nhân sẽ trượt vào sân khấu của cô ấy. Hãy thử hỏi cô ấy, ví dụ:
"Nhờ Hermes xem giúp thời tiết ngày mai nhé?". Cô ấy trả lời, gõ việc cần làm vào bong bóng thoại của mình, rồi
hình nhân tiếp quản: nó suy nghĩ trong lúc trợ lý làm việc, nói các bước của trợ lý trong bong bóng của chính nó,
trông ngạc nhiên khi trợ lý có câu hỏi hoặc cần bạn đồng ý (hãy nói đồng ý hay không, hoặc nhấn Approve trên trang
Use), và vui vẻ khi kết quả tới, rồi cô ấy sẽ nói lại kết quả cho bạn. Hình nhân đi kèm với `setup_tts.py`
(`OK paper doll Host` trong bản tóm tắt của nó).

Từng bước chi tiết, và ý nghĩa của từng thông báo: [docs/TOOLS.md](docs/TOOLS.md#her-helpers-set-up-hermes-agent-and-nanomuse).

## Giấy phép

- Mã nguồn của OpenAmika theo giấy phép **MIT** ([LICENSE](LICENSE)). Các thành phần bên thứ ba giữ giấy phép riêng
  của chúng ([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)); Live2D Cubism Core trong `ui/vendor/` không phải MIT.
- **Bản thân Amika không phải MIT.** Nhân vật, hình ảnh, giọng nói, mô hình Live2D và các trọng số của cô ấy, cùng
  hình nhân giấy đóng vai thay cho các trợ lý của cô ấy
  ([MekaHime/MekaHime_Amika](https://huggingface.co/MekaHime/MekaHime_Amika)), thuộc về MekaHime Inc. và được cung
  cấp miễn phí theo giấy phép sử dụng cá nhân: chỉ dùng cho mục đích cá nhân, từ 18 tuổi trở lên, không được phân phối
  lại hay lưu trữ lại, và không được huấn luyện các mô hình khác trên chúng. Hai quy tắc dành cho creator: kiếm tiền
  trên mạng xã hội (video, livestream, quảng cáo, hội viên, tài trợ) không giới hạn, kèm ghi rõ credit MekaHime.AI ở
  vị trí dễ thấy; và làm hàng fan-made với tổng giá trị tối đa 1.000 USD, với tư cách cá nhân, từ fan art do chính
  bạn vẽ lại (không bao giờ dùng ảnh gốc mà MekaHime đã đăng trên website hay mạng xã hội), với dòng "MekaHime.AI" ở
  mặt dễ thấy và một nhãn "Fan Art" nhỏ. Mọi mục đích thương mại khác đều cần giấy phép từ MekaHime
  (hi@mekahime.com). Bản [LICENSE](https://huggingface.co/MekaHime/MekaHime_Amika/blob/main/LICENSE) trên Hugging
  Face là văn bản có hiệu lực.
- Hermes Agent (MIT) và nanoMuse (GPL-3.0-or-later) là các chương trình riêng mà bạn tự cài đặt; OpenAmika chỉ giao
  tiếp với chúng.
- Được xây dựng trên [SenseVoice](https://github.com/FunAudioLLM/SenseVoice), [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS),
  [bge-m3](https://huggingface.co/BAAI/bge-m3), [Qwen3-VL](https://github.com/QwenLM/Qwen3-VL),
  [pixi-live2d-display](https://github.com/guansss/pixi-live2d-display) với
  [Live2D Cubism SDK](https://www.live2d.com/en/sdk/about/), [OpenRouter](https://openrouter.ai),
  [Ollama](https://ollama.com) và [Model Context Protocol](https://modelcontextprotocol.io). Xin cảm ơn.

## Hỗ trợ

Câu hỏi và báo lỗi: [GitHub issues](https://github.com/zeekk0/OpenAmika/issues), hi@mekahime.com, hoặc
[Discord](https://discord.gg/mekahime). Ủng hộ dự án: https://www.mekahime.com/donate

<p align="center">
  <a href="https://www.mekahime.com">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/images/mekahime-logo-white.png">
      <img src="docs/images/mekahime-logo-card.png" alt="MekaHime" width="220">
    </picture>
  </a>
</p>
