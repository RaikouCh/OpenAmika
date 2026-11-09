"""
Hane WebUI - INNER MONOLOGUE 架构测试
OpenAmika：模板占位符布局（静态前缀在 {daily_context} 之前）、
逐轮语言行、共享输出契约 po_contract（深层/表层解析与发声端同一套规则）。
"""
from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
from flask_socketio import SocketIO
import requests as http_requests
import contextlib
import json
import random
import os
import uuid
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import threading
import time as _time
import re

import po_contract

# Her clock. build_f.json "timezone" (an IANA name such as America/Los_Angeles) is set from the Setup page
# and hot-applied through this module's globals (f_persona); absent or invalid → Asia/Tokyo, the stack's
# original zone. Every "now" in the brain reads LOCAL_TZ at call time.
DEFAULT_TZ_NAME = "Asia/Tokyo"


def _load_local_tz():
    try:
        cfg = json.loads(po_contract.read_text_bom(Path(__file__).resolve().parent.parent / "config" / "build_f.json"))
        name = str(cfg.get("timezone") or "").strip()
        if name:
            return ZoneInfo(name)
    except Exception as error:
        print(f"[clock] build_f.json timezone ignored ({error}); using {DEFAULT_TZ_NAME}")
    return ZoneInfo(DEFAULT_TZ_NAME)


LOCAL_TZ = _load_local_tz()
# 应用名（状态接口 / 健康检查）；f_bridge 按 build_f.json 的 "app" 覆盖。
APP_NAME = "OpenAmika"


load_dotenv(Path(__file__).with_name(".env"))

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

XAI_KEY = os.getenv("XAI_API_KEY")
XAI_BASE = "https://api.x.ai/v1/chat/completions"

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
_gemini_client = None

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
CONSOLIDATION_ANTHROPIC_KEY = os.getenv("CONSOLIDATION_ANTHROPIC_KEY", ANTHROPIC_KEY)
# 思考层走后台 key（与记忆整理同属"非实时"工作区），把深层实时通道的限流额度让出来。
# 默认回落到 CONSOLIDATION key；想单独配第三把 key 只需在 .env 设 THINKING_ANTHROPIC_KEY。
THINKING_ANTHROPIC_KEY = os.getenv("THINKING_ANTHROPIC_KEY", CONSOLIDATION_ANTHROPIC_KEY)
ANTHROPIC_BASE = "https://api.anthropic.com/v1/messages"

GROQ_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE = "https://api.groq.com/openai/v1/chat/completions"

CEREBRAS_KEY = os.getenv("CEREBRAS_API_KEY")
CEREBRAS_BASE = "https://api.cerebras.ai/v1/chat/completions"

TEMPLATE_FILE = os.getenv("TEMPLATE_FILE", "例子.txt")
SURFACE_TEMPLATE_FILE = "表层.txt"
THINKING_TEMPLATE_FILE = "思考.txt"

_template_cache = None
_surface_template_cache = None
_thinking_template_cache = None
# 开机模板自检结果（R2）：{文件名: [问题…]}；/api/build_f/status 里的 template_check。
TEMPLATE_CHECK = None

AVAILABLE_MODELS = {
    "claude-5-sonnet": {
        "name": "Claude Sonnet 5 (关思考)",
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "description": "深层主选（显式关思考：首字最快、人味足）",
        "thinking_disabled": True,
    },
    "claude-5-sonnet-thinking": {
        "name": "Claude Sonnet 5 (自适应思考)",
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "description": "思考层主选（默认自适应思考，规划最细）",
    },
    "claude-4.6-sonnet": {
        "name": "Claude 4.6 Sonnet",
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "description": "旧深层/思考层（备用回退）",
    },
    "grok-4.3": {
        "name": "Grok 4.3",
        "provider": "xai",
        "model": "grok-4.3",
        "description": "深层备选（人味密度高 + 便宜）",
    },
    "grok-4.3-fast": {
        "name": "Grok 4.3 (non-reasoning)",
        "provider": "xai",
        "model": "grok-4.3",
        "description": "表层主选 / listen-mode（reasoning_effort=none，near-instant）",
        "reasoning_effort": "none",
    },
    # 实测 reasoning_effort：none 0.64s/0推理 · low 1.3s · medium 偶尔偏慢 · high 2s+。
    "grok-4.3-low": {
        "name": "Grok 4.3 (reasoning: low)",
        "provider": "xai",
        "model": "grok-4.3",
        "description": "xAI · 轻推理 ~1.3s",
        "reasoning_effort": "low",
    },
    "grok-4.3-medium": {
        "name": "Grok 4.3 (reasoning: medium)",
        "provider": "xai",
        "model": "grok-4.3",
        "description": "xAI · 中推理（偶尔偏慢）",
        "reasoning_effort": "medium",
    },
    "grok-4.3-high": {
        "name": "Grok 4.3 (reasoning: high)",
        "provider": "xai",
        "model": "grok-4.3",
        "description": "xAI · 强推理 ~2s+",
        "reasoning_effort": "high",
    },
    "gemini-3-flash": {
        "name": "Gemini 3 Flash",
        "provider": "gemini",
        "model": "gemini-3-flash-preview",
        "description": "Gemini 快速",
    },
    "groq-qwen3-32b": {
        "name": "Qwen3 32B (Groq)",
        "provider": "groq",
        "model": "qwen/qwen3-32b",
        "description": "旧表层（Groq 即将于一个月内停服，已迁出）",
        "no_think": True,
    },
    "groq-gpt-oss-120b": {
        "name": "GPT-OSS 120B (Groq)",
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "description": "表层主选（裸脑子最稳：零幻觉、不被绕晕、~0.4s）",
        # gpt-oss 不理 /no_think，靠 reasoning_effort 控速；low 已够快够准
        "reasoning_effort": "low",
    },
    "groq-qwen3.6-27b": {
        "name": "Qwen 3.6 27B (Groq)",
        "provider": "groq",
        "model": "qwen/qwen3.6-27b",
        "description": "当前 Qwen · 27B dual-mode（对话走 none）· Groq ~0.4s",
        "reasoning_effort": "none",
    },
    "cerebras-glm-4.7": {
        "name": "GLM-4.7 (Cerebras)",
        "provider": "cerebras",
        "model": "zai-glm-4.7",
        "description": "Z.ai GLM-4.7 355B · 中文/角色扮演最强 · Cerebras ~1000 t/s",
        "reasoning_effort": "none",   # GLM-4.7 是思考模型；none = 关思考走快对话（否则 reply 空）
    },
    "cerebras-gemma-4-31b": {
        "name": "Gemma 4 31B (Cerebras)",
        "provider": "cerebras",
        "model": "gemma-4-31b",
        "description": "Gemma 4 31B · Cerebras ~1850 t/s",
    },
    "cerebras-gpt-oss-120b": {
        "name": "GPT-OSS 120B (Cerebras)",
        "provider": "cerebras",
        "model": "gpt-oss-120b",
        "description": "GPT-OSS 120B · Cerebras ~3000 t/s（对照）",
        "reasoning_effort": "low",
    },
    # ── LOCAL (ollama · RTX5090 · 无 API 费用；思考系 Qwen 一律 reasoning_effort=none 关思考）──
    "local-qwen2.5-14b-ablit": {"name": "Qwen2.5 14B abliterated (local)", "provider": "ollama",
        "model": "huihui_ai/qwen2.5-abliterate:14b", "description": "本地 · 9GB · 去审查"},
    "local-qwen2.5-32b-ablit": {"name": "Qwen2.5 32B abliterated (local)", "provider": "ollama",
        "model": "huihui_ai/qwen2.5-abliterate:32b", "description": "本地 · 20GB · 去审查角色扮演"},
    "local-qwen3-30b-a3b-ablit": {"name": "Qwen3 30B-A3B abliterated (local)", "provider": "ollama",
        "model": "huihui_ai/qwen3-abliterated:30b-a3b", "description": "本地 · MoE 3B活跃 · 快 · 去审查",
        "reasoning_effort": "none"},
    "local-qwen3-32b-ablit": {"name": "Qwen3 32B abliterated (local)", "provider": "ollama",
        "model": "huihui_ai/qwen3-abliterated:32b", "description": "本地 · 32B dense · 去审查",
        "reasoning_effort": "none"},
    "local-qwen3.5-35b-a3b": {"name": "Qwen3.5 35B-A3B (local)", "provider": "ollama", "model": "qwen3.5:35b-a3b",
        "description": "本地 · MoE 3B活跃 · 24GB · 快", "reasoning_effort": "none"},
    "local-qwen3.5-35b-ablit": {"name": "Qwen3.5 35B abliterated (local)", "provider": "ollama",
        "model": "huihui_ai/qwen3.5-abliterated:35b", "description": "本地 · MoE · 去审查角色扮演",
        "reasoning_effort": "none"},
    "local-qwen3.6-27b": {"name": "Qwen3.6 27B abliterated (local · 同 SLM)", "provider": "ollama",
        "model": "huihui_ai/qwen3.6-abliterated:27b",
        "description": "本地 · 17GB · 去审查 · 与 bot SLM/judge 同一模型（keep_alive:-1 常驻显存）——"
                       "选它不触发额外加载/卸载。OURS 7/17：从官方 qwen3.6:27b 改指到 abliterated 以对齐 SLM。",
        "reasoning_effort": "none"},
    "local-qwen3.6-35b-a3b": {"name": "Qwen3.6 35B-A3B (local)", "provider": "ollama", "model": "qwen3.6:35b-a3b",
        "description": "本地 · MoE 3B活跃 · 24GB · 最新（下载中）", "reasoning_effort": "none"},
    "local-glm-4.7-flash-ablit": {"name": "GLM-4.7-Flash abliterated (local)", "provider": "ollama",
        "model": "huihui_ai/glm-4.7-flash-abliterated:q4_K",
        "description": "本地 · 30B级 · 19GB · 中文/角色扮演强 · 去审查",
        "reasoning_effort": "none"},   # GLM-4.7 是思考模型；none 关思考走快对话（否则 reply 可能空）
}


def load_template() -> str:
    """从缓存返回模板，首次调用时从文件加载"""
    global _template_cache
    if _template_cache is None:
        reload_template()
    return _template_cache


def reload_template():
    """从 txt 文件重新加载模板到内存"""
    global _template_cache
    path = Path(TEMPLATE_FILE)
    if not path.exists():
        raise FileNotFoundError(f"模板文件不存在: {TEMPLATE_FILE}")

    _template_cache = po_contract.read_text_bom(path).strip()
    if not _template_cache:
        raise ValueError(f"{TEMPLATE_FILE} 内容为空")
    print(f"[Hane] deep template loaded: {TEMPLATE_FILE} ({len(_template_cache)} characters)")


def load_surface_template() -> str:
    global _surface_template_cache
    if _surface_template_cache is None:
        reload_surface_template()
    return _surface_template_cache


def reload_surface_template():
    global _surface_template_cache
    path = Path(SURFACE_TEMPLATE_FILE)
    if not path.exists():
        raise FileNotFoundError(f"表层模板不存在: {SURFACE_TEMPLATE_FILE}")
    _surface_template_cache = po_contract.read_text_bom(path).strip()
    print(f"[Hane] surface template loaded: {SURFACE_TEMPLATE_FILE} ({len(_surface_template_cache)} characters)")


def load_thinking_template() -> str:
    global _thinking_template_cache
    if _thinking_template_cache is None:
        reload_thinking_template()
    return _thinking_template_cache


def reload_thinking_template():
    global _thinking_template_cache
    path = Path(THINKING_TEMPLATE_FILE)
    if not path.exists():
        raise FileNotFoundError(f"思考层模板不存在: {THINKING_TEMPLATE_FILE}")
    _thinking_template_cache = po_contract.read_text_bom(path).strip()
    print(f"[Hane] reflection template loaded: {THINKING_TEMPLATE_FILE} ({len(_thinking_template_cache)} characters)")


def run_template_check() -> dict:
    """R2 模板自检：三份模板逐一过 po_contract.check_template（占位符齐全且各一次、顺序、
    情绪词表、声效名、无 BOM …）。只打日志、不拒绝启动；结果挂到 TEMPLATE_CHECK 给状态接口。
    查的是磁盘上的原文（含 BOM 检测），加载时 BOM 已经被剥掉，不影响运行。"""
    global TEMPLATE_CHECK
    result = {}
    for kind, name in (("deep", TEMPLATE_FILE), ("surface", SURFACE_TEMPLATE_FILE),
                       ("thinking", THINKING_TEMPLATE_FILE)):
        path = Path(name)
        try:
            problems = po_contract.check_template(kind, path.read_bytes().decode("utf-8", errors="replace"))
        except OSError as e:
            problems = [f"cannot read {name}: {e}"]
        result[name] = problems
        for p in problems:
            print(f"[PO] template check: {name}: {p}")
    if not any(result.values()):
        print("[PO] template check: OK (" + ", ".join(result) + ")")
    TEMPLATE_CHECK = result
    return result


# ─── 深层 prompt 的逐轮槽位（R4/P3）──
# 模板里所有静态句子都在 {daily_context} 之前（缓存前缀，po_contract.split_static 在此切开），
# 之后只有时段级和逐轮材料（CONTRACT §2.1）：
#   {daily_context} {current_scene} {current_time} {memories_block} {conversation_history}
#   {pending_mind} {blurt_block} {say_marker} {deep_instruction} {language_line}
# 代码只填占位符，不再对指令文字做字符串替换。
DEEP_TEMPLATE_SAY_MARKER = "我说：\n我心想："          # {say_marker}：正常
DEEP_TEMPLATE_SAY_MARKER_BLURT = "我接着说：\n我心想："  # {say_marker}：表层已脱口而出

# 打断格式的内部标记：写到 turn["user"] 开头，
# 用来可靠区分"打断合成" vs "用户真的说了'当我说到'开头的话"。
# 送给 LLM 前必须用 _user_for_llm() 剥掉。
# STT 文本不会以 '&' 开头，用它就够了。
INTERRUPT_MARKER = "&"


# 对话的默认模型搭配：表层 Grok 4.3（non-reasoning），深层/思考层 Sonnet 5。
# 前端协议不暴露模型选择，始终用这几个。
# 切模型只改下面几行：
#   "claude-5-sonnet"          ← 深层主选（Sonnet 5 显式关思考：首字最快、人味足）
#   "claude-5-sonnet-thinking" ← 思考层主选（Sonnet 5 自适应思考：慢通道，规划最细）
#   "claude-4.6-sonnet"        ← 旧深层/思考层（备用回退）
#   "grok-4.3-fast"            ← 表层主选（4.3 non-reasoning，near-instant）
#   "groq-gpt-oss-120b"        ← 旧表层（GPT-OSS 120B，备用回退）
DEFAULT_SURFACE_MODEL = "grok-4.3-fast"
# 控制台「Surface LLM」下拉可运行时切换的表层模型（改全局 DEFAULT_SURFACE_MODEL，正常对话轮即时生效）
SURFACE_MODEL_KEYS = [
    # cloud
    "groq-qwen3.6-27b", "groq-qwen3-32b", "groq-gpt-oss-120b", "grok-4.3-fast",
    "cerebras-glm-4.7", "cerebras-gemma-4-31b", "cerebras-gpt-oss-120b",
    # local (ollama, RTX5090; >=14B only)
    "local-qwen2.5-14b-ablit", "local-qwen2.5-32b-ablit",
    "local-qwen3-30b-a3b-ablit", "local-qwen3-32b-ablit",
    "local-qwen3.5-35b-a3b", "local-qwen3.5-35b-ablit",
    "local-qwen3.6-27b", "local-qwen3.6-35b-a3b", "local-glm-4.7-flash-ablit",
]
DEFAULT_DEEP_MODEL = "claude-5-sonnet"
# 思考层：慢但强推理，流式吐字，吃 Anthropic static-prefix 缓存
DEFAULT_THINKING_MODEL = "claude-5-sonnet-thinking"
# 控制台「Deep LLM」/「Thinking LLM」/「Consolidation LLM」下拉可运行时切换（改下面全局，下一轮即时生效）。
# 深层/思考层是「质量层」，主选云端强模型（Claude 5/4.6 + Grok 4.3 各推理档 + Gemini）。
# OURS 7/17：末尾补上本地 qwen3.6（ollama, RTX5090, 零 API 费）——记忆整理层实测追平 Sonnet；
# 深层/思考层（她的实时台词/推理）用本地是质量降级，仅作为选项开放，operator 自行取舍。
# claude-5-sonnet-thinking 只进思考层下拉——实时深层要显式关思考（否则首字 4s+）。
DEEP_MODEL_KEYS = [
    "claude-5-sonnet", "claude-4.6-sonnet",
    "grok-4.3-fast", "grok-4.3-low", "grok-4.3-medium", "grok-4.3-high",
    "gemini-3-flash",
    # OURS 7/17: 只列与 SLM 同一模型（abliterated 27b，常驻显存）——整理层实测追平 Sonnet、
    # 零 API 费、选它不触发加载/卸载。35b-a3b 是另一个 24GB 模型会挤显存、故不进质量层下拉。
    "local-qwen3.6-27b",
]
THINKING_MODEL_KEYS = [
    "claude-5-sonnet-thinking", "claude-5-sonnet", "claude-4.6-sonnet",
    "grok-4.3-fast", "grok-4.3-low", "grok-4.3-medium", "grok-4.3-high",
    "gemini-3-flash",
    "local-qwen3.6-27b",   # OURS 7/17: 同 SLM 的 abliterated 27b（不额外加载）
]


def _user_for_llm(user_field: str) -> str:
    """剥掉 interrupt 内部标记，得到给 LLM 看的干净 user 文本。"""
    if user_field.startswith(INTERRUPT_MARKER):
        return user_field[len(INTERRUPT_MARKER):]
    return user_field

# ─── 四种情况的 {deep_instruction}（深层 prompt 末尾、语言行之前的指令行）──────
# 这些常量可以独立调整，不影响其他情况。
#
# 判定：
#   interrupt = 当前 user 字段带 INTERRUPT_MARKER（打断合成格式）
#   blurt     = 表层已经说出口（say+think，或 think 模式带了一句垫话）
#
# B5：我心想里允许写动作，四条都以「以及你的想法和动作。」结尾。
# 口吻约定：指令是系统对她说的 → 第二人称「你」；只有她自己要输出的内容（我说/我心想、台词）才用「我」。

# 模板里原来贴着生成点的「每句说出口的话前面必须带上[register_emotion]语气标签」尾句已删（静态文字
# 不能留在 {daily_context} 之后），标签提醒改放进这四条指令里，仍然离生成点最近。
DEEP_INSTRUCTION_NORMAL = "回复你想说的话（如果你想说），说出口的话打上引号、前面带上[register_emotion]语气标签，以及你的想法和动作。"
DEEP_INSTRUCTION_NORMAL_BLURT = "接着你刚刚已经脱口而出的话，继续回复你想说的话（如果你想继续说），说出口的话打上引号、前面带上[register_emotion]语气标签，以及你的想法和动作。"
DEEP_INSTRUCTION_INTERRUPT = "回应对方突然的打断（如果你想说），可以顺着对方的打断说，也可以继续补完你本来想说但没说完的话；说出口的话打上引号、前面带上[register_emotion]语气标签，以及你的想法和动作。"
DEEP_INSTRUCTION_INTERRUPT_BLURT = "接着你刚刚已经脱口而出的话，继续回应对方突然的打断（如果你想继续说），可以顺着对方的打断说，也可以补完你本来想说但没说完的话；说出口的话打上引号、前面带上[register_emotion]语气标签，以及你的想法和动作。"

# ─── 四种情况的 user_content（作为 user role 消息送给 LLM）──
# 语种不在这里说：prompt 末尾的 {language_line} 是唯一的语言指令（B6）。
USER_CONTENT_NORMAL = "回复你想说的话（如果你想说）并给说话的内容打上引号，以及你的想法和动作。"
USER_CONTENT_NORMAL_BLURT = "接着你刚刚已经脱口而出的话（不一定对），继续回复你想说的话（如果你想继续说）并给说话的内容打上引号，以及你的想法和动作。你不会重复自己刚刚已经脱口而出的话。"
USER_CONTENT_INTERRUPT = "回应对方突然的打断（如果你想说），可以顺着对方的打断说，也可以补完你本来想说但没说完的话；给说话的内容打上引号，以及你的想法和动作。"
USER_CONTENT_INTERRUPT_BLURT = "接着你刚刚已经脱口而出的话（不一定对），继续回应对方突然的打断（如果你想继续说），可以顺着对方的打断说，也可以补完你本来想说但没说完的话；给说话的内容打上引号，以及你的想法和动作。你不会重复自己刚刚已经脱口而出的话。"


def _is_interrupt_user_msg(user_message: str) -> bool:
    """判断 user_message 是否为打断合成格式（通过内部标记识别）。"""
    return user_message.startswith(INTERRUPT_MARKER)


# 历史里怎么称呼对方（TELEMETRY_SPEC §3）：f_bridge 按 build_f.json 的 user_name 覆盖。
USER_NAME = "User"
# 她和对方住在哪座城市（build_f.json city，Setup → You & Amika）：模板和 scenes 里的 {city}；f_bridge 覆盖。
CITY = ""
# 最近一条对方消息的渠道：""=舞台（语音/打字，他在家），"discord"/"telegram"=文字消息（他不在身边，她在手机上看）。
# 决定 scenes 用 current_scene 还是 text_scene；ws_message 每条消息刷新。
_CURRENT_CHANNEL = ""
# 历史里相邻两轮隔了超过这么多分钟，就插一行「（——中间隔了…——）」；f_bridge 按 history_gap_minutes 覆盖。
# 0 或负数关掉所有时间行。
HISTORY_GAP_MINUTES = 20
# 打断合成句（_start_message_gen 写的英文包装）里对方的称呼，渲染时换成 user_name；存下来的 turn["user"] 不改。
_INTERRUPT_THEY_RE = re.compile(r'^(When I was saying ".*", )they( cut in: ".*")$', re.S)


def _history_user_name() -> str:
    """历史里对方的名字（与记忆渲染同一条规则：po_contract.speaker_name）。"""
    return po_contract.speaker_name("user", USER_NAME or "User")


def _render_user_line(user_field: str, user_name: str = None) -> str:
    """把 turn['user'] 渲染成历史里的一行。
    - 正常消息：'<user_name>：<text>'（build_f.json 的 user_name，默认 USER_NAME）
    - 打断合成消息：保留原来的自述句，只把句中的「they」换成对方的名字（不加归属前缀）
    """
    clean = _user_for_llm(user_field)
    name = user_name or _history_user_name()
    if _is_interrupt_user_msg(user_field):
        return _INTERRUPT_THEY_RE.sub(lambda m: m.group(1) + name + m.group(2), clean)
    return f"{name}：{clean}"

# ─── 对话记录系统 ───────────────────────────────────────────
MEMORY_DIR = Path("memories")
MEMORY_FILE = MEMORY_DIR / "conversations.json"
CONSOLIDATED_FILE = MEMORY_DIR / "consolidated.json"
# 三层 LLM 选择持久化：控制台切了 Surface/Deep/Thinking 后写盘，Hane 重启读回，
# 让「上次用的模型」跨重启保留（否则每次回落到硬编码默认）。每角色各自一份（各自 memories/）。
MODEL_PREFS_FILE = MEMORY_DIR / "model_prefs.json"


def _load_model_prefs():
    """开机读回上次用的三层模型。只在持久值仍在 AVAILABLE_MODELS 里时才覆盖默认，避免脏值。"""
    global DEFAULT_SURFACE_MODEL, DEFAULT_DEEP_MODEL, DEFAULT_THINKING_MODEL
    try:
        d = json.loads(MODEL_PREFS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    except Exception as e:
        print(f"[Hane] could not read the model preferences: {e}")
        return
    if d.get("surface") in AVAILABLE_MODELS:
        DEFAULT_SURFACE_MODEL = d["surface"]
    if d.get("deep") in AVAILABLE_MODELS:
        DEFAULT_DEEP_MODEL = d["deep"]
    if d.get("thinking") in AVAILABLE_MODELS:
        DEFAULT_THINKING_MODEL = d["thinking"]
    print(f"[Hane] model preferences loaded: surface={DEFAULT_SURFACE_MODEL} deep={DEFAULT_DEEP_MODEL} reflection={DEFAULT_THINKING_MODEL}")


def _save_model_prefs():
    """三层模型选择写盘（每次经 /api/*_model 切换后调用）。"""
    try:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        MODEL_PREFS_FILE.write_text(json.dumps(
            {"surface": DEFAULT_SURFACE_MODEL, "deep": DEFAULT_DEEP_MODEL,
             "thinking": DEFAULT_THINKING_MODEL}, ensure_ascii=False, indent=2),
            encoding="utf-8")
    except Exception as e:
        print(f"[Hane] could not save the model preferences: {e}")


_load_model_prefs()   # 开机即读回上次选择（AVAILABLE_MODELS/默认都已在上面定义好）

# Build F: external chat/vision integrations are excluded.
CONVERSATION_HISTORY: list = []
CONSOLIDATED_MEMORIES: list = []
_COMPLETED_CPS: set = set()  # 已完成（整理或跳过）的检查点 ID
_hist_lock = threading.RLock()  # 保护 CONVERSATION_HISTORY 的读/写/序列化

# ─── 思考层私有日志 ─────────────────────────────────────────
# 与对话记录"存储分开、呈现合并"：独立文件，每条挂 after_turn_num，
# 渲染 {thinking_history} 时按轮次交织进对话时间线。深层/表层永远读不到。
THINKING_LOG_FILE = MEMORY_DIR / "thinking_log.json"
THINKING_LOG: list = []
# 思考层总开关：慢通道（【想想】/空闲/开口/注入触发的外部思考层往返）。
# 深层在「我心想」里缀【想想】举手 → 本轮受保护后起思考层，产物(提示/计划/开口)挂回历史。
THINKING_ENABLED = True
# 【接着说】自续说：已停用（实测易自我循环刷屏，用处不大）。深层改回「我心想 + 【想想】」
# 走思考层；下面的 continue 相关代码与开关保留但不再被触发（f_bridge 也把入口换成空操作）。
CONTINUE_ENABLED = False
# B12：思考层的「开口」（主动发声轮）与空闲节奏恢复，同早期版本。f_bridge 按 build_f.json 的
# auto_open_from_reflection / idle_reflection 覆盖这两个开关，并提供 f_start_idle_reflection()。
F_AUTO_OPEN = False
F_IDLE_REFLECTION = False
# 思考层私有日志暂不单独浓缩（语境靠深层共用的浓缩记忆覆盖），只滚动保留最近若干条。
# 渲染时本就只对未浓缩轮次显示笔记，这个上限主要是给磁盘归档封顶、防无限增长。
THINKING_LOG_MAX = 20
_think_lock = threading.RLock()
# 思考层并发：允许同时跑多个请求（各自靠 target_turn_id 归位），但设上限防失控。
_THINKING_MAX = 3
_think_state_lock = threading.Lock()
_thinking_inflight = 0
# 「待思考态」：深层刚喊完【想想】、结果还没回来的窗口里，深层正在等的那条心想
# （最新一条，已剔除【想想】）。这段时间深层 prompt 的 {pending_mind} 会补一段"我已经在想这个了"，
# 避免它对同一件事重复举手。结果一回来就清空，{pending_mind} 恢复为空。
_pending_think = None
_pending_seq = 0


SESSION_BOUNDARY_HOUR = 5  # 凌晨5点为记忆日界线

def _consolidation_key(dt: datetime) -> str:
    """从墙钟算整理记忆用的检查点键，如 '15 3'（用于 consolidated.json）"""
    return f"{dt.hour} {dt.minute // 10 + 1}"

# ── 原始轮次检查点状态 ──
_cp_lock = threading.Lock()
_CURRENT_CP: str = ""      # 当前开放的检查点，如 "0318 15 3"
_CURRENT_TURN_NUM: int = 0  # 当前检查点内的轮次计数

def _make_raw_cp(sd: str, hour: int, cp_num: int) -> str:
    """构建原始轮次检查点 ID: '0318 15 3'"""
    mmdd = sd[5:7] + sd[8:10]
    return f"{mmdd} {hour} {cp_num}"

def _cp_to_ck(raw_cp: str) -> str:
    """原始检查点 → 整理键: '0318 15 3' → '15 3'"""
    parts = raw_cp.split()
    if len(parts) >= 3:
        return f"{parts[1]} {parts[2]}"
    return raw_cp

def _init_current_cp():
    """启动/重置时从墙钟初始化当前检查点"""
    global _CURRENT_CP, _CURRENT_TURN_NUM
    now = datetime.now(LOCAL_TZ)
    sd = _session_date(now)
    hour = now.hour
    cp_num = now.minute // 10 + 1
    ck = f"{hour} {cp_num}"
    if ck in _COMPLETED_CPS:
        if cp_num < 6:
            cp_num += 1
        else:
            hour = (hour + 1) % 24
            cp_num = 1
    with _cp_lock:
        _CURRENT_CP = _make_raw_cp(sd, hour, cp_num)
        with _hist_lock:
            existing = [t for t in CONVERSATION_HISTORY if t.get("checkpoint") == _CURRENT_CP]
        _CURRENT_TURN_NUM = len(existing)
    print(f"[Hane] current checkpoint: {_CURRENT_CP}, {_CURRENT_TURN_NUM} turn(s) so far")

def _session_minutes(h: int, m: int = 0) -> int:
    """将小时+分钟转为会话内分钟数（5点=0, 6点=60, ..., 4点=1380）用于顺序比较"""
    if h < SESSION_BOUNDARY_HOUR:
        h += 24
    return (h - SESSION_BOUNDARY_HOUR) * 60 + m


def _catchup_range(from_h: int, from_cp: int, to_h: int, to_cp: int):
    """从 (from_h, from_cp) 到 (to_h, to_cp)（不含）逐个处理检查点。
    每个检查点：原子捕获轮次+推进 _CURRENT_CP → 整理/跳过 → 标记完成 → 链式触发。
    启动补整理和运行时跳跃共用此函数。"""
    global _CURRENT_CP, _CURRENT_TURN_NUM
    h, cp = from_h, from_cp
    to_sm = _session_minutes(to_h, (to_cp - 1) * 10)

    while True:
        sm = _session_minutes(h, (cp - 1) * 10)
        if sm >= to_sm:
            break

        ck = f"{h} {cp}"
        nh, ncp = (h, cp + 1) if cp < 6 else ((h + 1) % 24, 1)

        if ck not in _COMPLETED_CPS:
            with _cp_lock:
                turns = _get_turns_for_checkpoint(ck)
                _CURRENT_CP = _make_raw_cp(_session_date(), nh, ncp)
                _CURRENT_TURN_NUM = 0

            print(f"[Hane] checkpoint advanced → {_CURRENT_CP}")

            if turns:
                history = _build_history_from_turns(turns)
                print(f"[Hane] consolidating 10min {ck} ({len(turns)} turn(s))")
                ok = _run_consolidation("10min", ck, history_override=history)
                if not ok:
                    print(f"[Hane] retrying 10min {ck}")
                    _time.sleep(3)
                    ok = _run_consolidation("10min", ck, history_override=history)
                if ok:
                    _mark_cp_done(ck)
                else:
                    print(f"[Hane] consolidating {ck} failed for good: skipped")
            else:
                _mark_cp_done(ck)
        else:
            with _cp_lock:
                _CURRENT_CP = _make_raw_cp(_session_date(), nh, ncp)
                _CURRENT_TURN_NUM = 0

        _try_hour_consolidation(h)
        h, cp = nh, ncp


def _startup_catchup():
    """启动时补充整理：处理服务器停机期间遗漏的检查点"""
    now = datetime.now(LOCAL_TZ)
    sd = _session_date(now)

    with _hist_lock:
        today_turns = [t for t in CONVERSATION_HISTORY
                       if _session_date_from_ts(t.get("ts", "1970-01-01 12:00:00")) == sd]
    if not today_turns:
        print("[Hane] start check: no conversation in this session yet: skipped")
        return

    latest = today_turns[-1]
    latest_ck = _cp_to_ck(latest.get("checkpoint", ""))
    parts = latest_ck.split()
    if len(parts) != 2:
        return
    latest_h, latest_cp = int(parts[0]), int(parts[1])

    trigger_min = latest_cp * 10 - 1
    if _session_minutes(now.hour, now.minute) < _session_minutes(latest_h, trigger_min):
        print(f"[Hane] start check: the latest checkpoint {latest_ck} is not due yet: skipped")
        return

    to_h = now.hour
    to_cp = now.minute // 10 + 1
    print(f"[Hane] catching up at start: from {latest_ck} to {to_h} {to_cp}")
    _catchup_range(latest_h, latest_cp, to_h, to_cp)
    print("[Hane] catching up at start: done")


def _session_date(now: datetime = None) -> str:
    """返回当前会话日期（凌晨5点前算前一天）"""
    if now is None:
        now = datetime.now(LOCAL_TZ)
    if now.hour < SESSION_BOUNDARY_HOUR:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    return now.strftime("%Y-%m-%d")

def _session_date_from_ts(ts_str: str) -> str:
    """从轮次时间戳字符串推算其所属的会话日期"""
    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    if dt.hour < SESSION_BOUNDARY_HOUR:
        return (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d")


def _load_history():
    if MEMORY_FILE.exists():
        try:
            data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            with _hist_lock:
                CONVERSATION_HISTORY.clear()
                CONVERSATION_HISTORY.extend(data.get("turns", []))
            print(f"[Hane] conversation history loaded: {len(CONVERSATION_HISTORY)} turn(s)")
        except Exception as e:
            print(f"[Hane] could not load the conversation history: {e}")


# R21：json.dumps 在 _hist_lock 里做（快照一致），写盘（.tmp + os.replace）在 _hist_lock 外做。
# 写盘按序号排队，旧快照永远不会覆盖新快照。清除控制（f_reset）绕过这里直接写文件，
# 所以写完再对一次历史指纹：期间被整体换掉（而没有新的保存）就按当前状态再写一遍。
_hist_write_lock = threading.Lock()   # 只保护写盘；持有它时绝不再去拿 _hist_lock
_hist_seq = 0
_hist_written_seq = 0


def _hist_shape() -> tuple:
    """调用者持有 _hist_lock。"""
    last = CONVERSATION_HISTORY[-1].get("turn_id") if CONVERSATION_HISTORY else None
    return len(CONVERSATION_HISTORY), last


def _save_history():
    global _hist_seq, _hist_written_seq
    MEMORY_DIR.mkdir(exist_ok=True)
    for _attempt in range(3):
        with _hist_lock:
            _hist_seq += 1
            seq = _hist_seq
            data = {
                "total_turns": len(CONVERSATION_HISTORY),
                "last_updated": datetime.now(LOCAL_TZ).isoformat(),
                "turns": CONVERSATION_HISTORY,
            }
            payload = json.dumps(data, ensure_ascii=False, indent=2)
            shape = _hist_shape()
        with _hist_write_lock:
            if seq < _hist_written_seq:
                return          # 更新的快照已经落盘
            tmp = MEMORY_FILE.with_name(MEMORY_FILE.name + ".tmp")
            try:
                tmp.write_text(payload, encoding="utf-8")
                os.replace(tmp, MEMORY_FILE)
            except OSError as e:
                # Windows 上目标文件被占用时 replace 会失败：退回直接覆盖（与旧行为一致）。
                print(f"[Hane] could not replace the conversation history in one step, writing it directly: {e}")
                MEMORY_FILE.write_text(payload, encoding="utf-8")
                with contextlib.suppress(OSError):
                    tmp.unlink()
            _hist_written_seq = seq
        with _hist_lock:
            if _hist_seq != seq or _hist_shape() == shape:
                return          # 要么有更新的保存接手，要么期间没有被整体替换


def _load_consolidated():
    global CONSOLIDATED_MEMORIES
    if CONSOLIDATED_FILE.exists():
        try:
            data = json.loads(CONSOLIDATED_FILE.read_text(encoding="utf-8"))
            CONSOLIDATED_MEMORIES = data.get("memories", [])
            # 重建已完成检查点集合
            sd = _session_date()
            for m in CONSOLIDATED_MEMORIES:
                if m.get("date") == sd and m.get("level") == "10min":
                    _COMPLETED_CPS.add(m["checkpoint"])
            # 已完成的小时和时段也标记其下属检查点为完成
            for m in CONSOLIDATED_MEMORIES:
                if m.get("date") == sd and m.get("level") == "hour":
                    parts = m.get("checkpoint", "").split()
                    if parts:
                        h = int(parts[0])
                        for i in range(1, 7):
                            _COMPLETED_CPS.add(f"{h} {i}")
            print(f"[Hane] consolidated memories loaded: {len(CONSOLIDATED_MEMORIES)}, "
                  f"checkpoints done: {len(_COMPLETED_CPS)}")
        except Exception as e:
            print(f"[Hane] could not load the consolidated memories: {e}")


def _save_consolidated():
    MEMORY_DIR.mkdir(exist_ok=True)
    data = {
        "total": len(CONSOLIDATED_MEMORIES),
        "last_updated": datetime.now(LOCAL_TZ).isoformat(),
        "memories": CONSOLIDATED_MEMORIES,
    }
    CONSOLIDATED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_thinking_log():
    if THINKING_LOG_FILE.exists():
        try:
            data = json.loads(THINKING_LOG_FILE.read_text(encoding="utf-8"))
            with _think_lock:
                THINKING_LOG.clear()
                THINKING_LOG.extend(data.get("entries", []))
            print(f"[Hane] reflection log loaded: {len(THINKING_LOG)} entries")
        except Exception as e:
            print(f"[Hane] could not load the reflection log: {e}")


def _save_thinking_log():
    MEMORY_DIR.mkdir(exist_ok=True)
    with _think_lock:
        data = {
            "total": len(THINKING_LOG),
            "last_updated": datetime.now(LOCAL_TZ).isoformat(),
            "entries": THINKING_LOG,
        }
        payload = json.dumps(data, ensure_ascii=False, indent=2)
    THINKING_LOG_FILE.write_text(payload, encoding="utf-8")


def add_thinking_entry(entry: dict) -> dict:
    """追加一条思考层记录并持久化；只滚动保留最近 THINKING_LOG_MAX 条。"""
    with _think_lock:
        THINKING_LOG.append(entry)
        if len(THINKING_LOG) > THINKING_LOG_MAX:
            del THINKING_LOG[:-THINKING_LOG_MAX]
        _save_thinking_log()
    return entry


def add_consolidated_memory(content: str, checkpoint: str = None, level: str = "10min"):
    """
    保存一条整理好的记忆。
    checkpoint: 如 '15 3'（10分钟级）、'15 0'（小时级）、'afternoon_early'（时段级）
    level: '10min' | 'hour' | 'period'
    """
    now = datetime.now(LOCAL_TZ)
    if checkpoint is None:
        checkpoint = _consolidation_key(now)
    sd = _session_date(now)
    memory = {
        "id": f"m_{sd.replace('-', '')}_{checkpoint.replace(' ', '_')}",
        "date": sd,
        "checkpoint": checkpoint,
        "level": level,
        "content": content,
    }
    CONSOLIDATED_MEMORIES.append(memory)
    _save_consolidated()
    return memory


def get_consolidated_checkpoints() -> set:
    """返回当前会话已整理的10分钟级检查点编号集合"""
    sd = _session_date()
    return {m["checkpoint"] for m in CONSOLIDATED_MEMORIES
            if m.get("level") == "10min" and m.get("date") == sd}


def create_turn(turn_id: str, user_message: str) -> dict:
    """建立新一轮对话，先只含用户消息。"""
    global _CURRENT_TURN_NUM
    now = datetime.now(LOCAL_TZ)
    with _cp_lock:
        _CURRENT_TURN_NUM += 1
        cp = _CURRENT_CP
        tn = _CURRENT_TURN_NUM
    turn = {
        "turn_id": turn_id,
        "ts": now.strftime("%Y-%m-%d %H:%M:%S"),
        "checkpoint": cp,
        "turn_num": tn,
        "user": user_message,
    }
    with _hist_lock:
        CONVERSATION_HISTORY.append(turn)
    _save_history()
    return turn


def _find_turn(turn_id: str) -> dict | None:
    """调用者需持有 _hist_lock（或只读场景下容忍竞态）。"""
    for t in CONVERSATION_HISTORY:
        if t.get("turn_id") == turn_id:
            return t
    return None


def update_turn_surface(turn_id: str, surface_reply: str, status: str = "", tone: str = ""):
    """表层结果入历史（C15：不再有 recall）。tone 是解析后的真实情绪键，历史里给这句话打标签用。"""
    with _hist_lock:
        t = _find_turn(turn_id)
        if t is None:
            return
        if surface_reply:
            t["surface_reply"] = surface_reply
        if status:
            t["status"] = status
        if tone:
            t["surface_tone"] = tone
    _save_history()


def update_turn_deep(turn_id: str, deep_raw: str):
    with _hist_lock:
        t = _find_turn(turn_id)
        if t is None:
            return
        if deep_raw:
            t["deep_raw"] = deep_raw
    _save_history()


def mark_turn_interrupted(turn_id: str, surface_partial: str = "",
                          deep_partial: str = ""):
    """标记 turn 为被真打断。保存已经流到的 partial 内容。"""
    with _hist_lock:
        t = _find_turn(turn_id)
        if t is None:
            return
        if surface_partial and not t.get("surface_reply"):
            t["surface_reply"] = surface_partial
        if deep_partial and not t.get("deep_raw"):
            t["deep_raw"] = deep_partial
        t["interrupted"] = True
    _save_history()
    print(f"[Hane] interrupted turn {turn_id}")


def discard_turn(turn_id: str) -> bool:
    """整条删除一轮（推测被取消）。"""
    with _hist_lock:
        for i, t in enumerate(CONVERSATION_HISTORY):
            if t.get("turn_id") == turn_id:
                CONVERSATION_HISTORY.pop(i)
                break
        else:
            return False
    _save_history()
    print(f"[Hane] dropped turn {turn_id}")
    return True


def _ck_session_minutes(ck: str) -> int:
    """检查点键 → 会话内分钟数，用于顺序比较。如 '9 4' → _session_minutes(9, 30)"""
    parts = ck.split()
    if len(parts) != 2:
        return -1
    h, cp = int(parts[0]), int(parts[1])
    return _session_minutes(h, (cp - 1) * 10)


def _unconsolidated_turns() -> list:
    """返回最晚一条10min整理之后的轮次（之前的全部视为已覆盖）"""
    sd = _session_date()
    done = get_consolidated_checkpoints()
    with _hist_lock:
        today_turns = [t for t in CONVERSATION_HISTORY
                       if _session_date_from_ts(t.get("ts", "1970-01-01 12:00:00")) == sd]
    if not done:
        return today_turns
    latest_done_sm = max(_ck_session_minutes(ck) for ck in done)
    return [t for t in today_turns
            if _ck_session_minutes(_cp_to_ck(t.get("checkpoint", ""))) > latest_done_sm]


def _parsed_deep(deep_raw: str, blurt: str = None) -> tuple:
    """解析 deep_raw，返回 (speech, thought)。partial 情况尽量容错。
    thought 已剥掉【想想】求助标记，任何层渲染都不会看到它。
    blurt：这一轮表层已经说出口的那句；深层开头重复它的部分会被去掉（C19）。"""
    if not deep_raw:
        return "", ""
    msgs = parse_response(deep_raw, blurt=blurt)
    if not msgs:
        return "", ""
    return msgs[0].get("speech", ""), msgs[0].get("thought", "")


def _turn_deep(t: dict) -> dict:
    """一轮的深层解析结果（speech / thought / segments …）。表层先说出口的那句
    （say+think，或 think 模式的垫话）作为 blurt 传入，深层重复的开头不算两遍。"""
    raw = t.get("deep_raw", "")
    if not raw:
        return {"speech": "", "thought": "", "segments": [], "needs_help": False, "wants_continue": False}
    return parse_response(raw, blurt=t.get("surface_reply") or None)[0]


def _deep_needs_help(deep_raw: str) -> bool:
    """这轮深层是否在「我心想」里缀了【想想】（思考层慢通道的触发标记）。"""
    return bool(deep_raw) and bool(po_contract.HELP_RE.search(deep_raw))


def _deep_wants_continue(deep_raw: str) -> bool:
    """这轮深层反思后是否决定自己接着说（【接着说】）。本版停用（CONTINUE_ENABLED=False）。"""
    return bool(deep_raw) and bool(po_contract.CONTINUE_RE.search(deep_raw))


def _history_speech(t: dict) -> str:
    """TELEMETRY_SPEC §3：一轮她说出口的话合成一句——表层先说出口的那句 + 深层去掉重复开头后的台词
    （与记忆归档同一条规则：po_contract.dedupe_blurt，见 _turn_deep），不带语气标签、不带声效，单行。"""
    sr = (t.get("surface_reply") or "").strip()
    speech = (_turn_deep(t)["speech"] or "").strip() if t.get("deep_raw") else ""
    parts = [sr] if sr else []
    if speech and speech != sr:
        parts.append(speech)
    return _spoken_text(" ".join(parts))


def _history_time_notes(turns: list) -> tuple:
    """TELEMETRY_SPEC §3：历史里的时间感。turns 是会渲染出来的轮次（按顺序）。
    返回 (开头一行, {i: 第 i 轮前面的分隔行}, 结尾一行)，不需要的为空。
    - 相邻两轮隔了超过 HISTORY_GAP_MINUTES：「（——中间隔了{perceived_span}——）」；
    - 第一轮已经超过阈值那么久：「（下面这段是{when_phrase}的对话）」；
    - 最后一轮已经超过阈值那么久：「（上一轮是{when_phrase}，现在是新的一段）」。
    时间用大脑的时钟 datetime.now(LOCAL_TZ)（测试/基准冻结的时钟同样生效）；没有可用 ts 的轮次不编时间。"""
    gap = int(HISTORY_GAP_MINUTES or 0)
    if gap <= 0 or not turns:
        return "", {}, ""
    now = po_contract.parse_when(datetime.now(LOCAL_TZ))
    whens = [po_contract.parse_when(t.get("ts")) for t in turns]
    separators = {}
    prev = None
    for i, when in enumerate(whens):
        if when is not None and prev is not None:
            minutes = (when - prev).total_seconds() / 60.0
            if minutes > gap:
                separators[i] = f"（——中间隔了{po_contract.perceived_span(minutes)}——）"
        prev = when
    opening = closing = ""
    first = next((w for w in whens if w is not None), None)
    last = next((w for w in reversed(whens) if w is not None), None)
    if first is not None and now is not None and (now - first).total_seconds() / 60.0 > gap:
        opening = f"（下面这段是{po_contract.when_phrase(first, now)}的对话）"
    if last is not None and now is not None and (now - last).total_seconds() / 60.0 > gap:
        closing = f"（上一轮是{po_contract.when_phrase(last, now)}，现在是新的一段）"
    return opening, separators, closing


def build_surface_history() -> str:
    """表层用：简洁的对话记录，第二人称，只有说出口的话（TELEMETRY_SPEC §3：对方用名字，
    一轮一句「你："…"」，不带标签/想法；隔得久的地方插时间行）。"""
    turns = _unconsolidated_turns()
    if not turns:
        return ""
    # 开口轮：不写对方的话，也不暴露括号提示（提示是深层专属）；没开口又没内容就整轮跳过。
    shown = [t for t in turns
             if t.get("inject_cue") or not t.get("open_cue") or t.get("deep_raw") or t.get("surface_reply")]
    opening, separators, closing = _history_time_notes(shown)
    lines = [opening] if opening else []
    for i, t in enumerate(shown):
        if i in separators:
            lines.append(separators[i])
        speak_verb = "你准备说" if t.get("interrupted", False) else "你"
        if t.get("inject_cue"):
            # 注入指导轮：无前缀裸括号，正常留在历史（表层也看得到，维持连贯）。
            lines.append(t["inject_cue"])
        elif not t.get("open_cue"):
            lines.append(_render_user_line(t['user']))
        # 表层只看「说出口的台词」：不贴深层原文，也不带「心想」「think_hint」等深层内部规划。
        # 喂内部规划会把又快又弱的表层锚死在旧话题上、跟不上对话已经转向的方向。
        speech = _history_speech(t)
        if speech:
            lines.append(f'{speak_verb}："{speech}"')
    if closing:
        lines.append(closing)
    return "[最近对话]\n" + "\n".join(lines)


# R19：只有窗口里最近这么多轮（有深层输出的轮）保留「我心想」，更早的只留说出口的话。
# f_bridge 按 build_f.json 的 history_thought_turns 覆盖。
HISTORY_THOUGHT_TURNS = 3


def _pinned_plan(visible_hints: list) -> str:
    """C20：思考层的「计划」一直有效，直到被新的计划替换。计划平时挂在它那一轮的
    think_hint 上随历史出现；那一轮不再显示想法（R19）或滑出窗口后，由这里在历史开头补一行。
    visible_hints：这次历史里会显示出来的 think_hint 文本。"""
    with _think_lock:
        entries = list(THINKING_LOG)
    for e in reversed(entries):
        plan = _clean_hint_piece(e.get("计划", ""))
        if plan:
            return "" if any(plan in h for h in visible_hints) else plan
    return ""


def build_deep_history() -> str:
    """深层用：第一人称叙事，包含内心想法。只包含最近窗口里的轮次。
    TELEMETRY_SPEC §3：对方用名字（<user_name>：…），一轮一句「我说："…"」（表层脱口而出 + 深层台词合一，
    不带语气标签——格式规则在静态前缀里），隔得久的地方插时间行。"""
    turns = _unconsolidated_turns()
    if not turns:
        return ""
    # 历史以当前这一轮的对方原话（或打断句 / 开口提示）结尾：这一轮表层已经说出口的那句
    # 由 {blurt_block}（我脱口而出…）交代，不在历史里再写一遍「我说」（C2：否则深层容易照着重复）。
    current_id = turns[-1].get("turn_id")
    # R19：「我心想」「我仔细地想了想」只留给当前这一轮之前的最近 HISTORY_THOUGHT_TURNS 轮，
    # 更早的轮次只留说出口的话。
    keep = max(0, int(HISTORY_THOUGHT_TURNS or 0))
    earlier = turns[:-1]
    thought_ids = {t.get("turn_id") for t in earlier[-keep:]} if keep else set()
    lines = []
    # C20：计划一直有效到被替换。挂着计划的那一轮已经不显示想法时，在历史开头补一行。
    plan = _pinned_plan([t.get("think_hint") or "" for t in earlier if t.get("turn_id") in thought_ids])
    if plan:
        lines.append(f"我之前仔细想好、现在还打算照着做的：{plan}")
    opening, separators, closing = _history_time_notes(turns)
    if opening:
        lines.append(opening)
    for i, t in enumerate(turns):
        if i in separators:
            lines.append(separators[i])
        shows_thoughts = t.get("turn_id") in thought_ids
        sr = t.get("surface_reply", "")
        deep_raw = t.get("deep_raw", "")
        speak_verb = "我准备说" if t.get("interrupted", False) else "我说"

        inject_cue = t.get("inject_cue")
        open_cue = t.get("open_cue")
        if inject_cue:
            # 注入指导轮：无前缀裸括号，永久留在历史，下面接她的反应（没有对方的话）。
            lines.append(inject_cue)
        elif open_cue:
            # 开口轮（思考层第三种指导诱导她主动说话）：永远不写对方的话。
            # 那句括号提示只在她还没开口时，作为本轮 prompt 末尾出现一次；
            # 一旦她开了口（或被打断留下 partial），提示即从历史消失——提示本身不进历史，
            # 只留下她自己说的话。被打断照常走 interrupted/「我准备说」那套。
            if not deep_raw and not sr:
                lines.append(open_cue)
                continue
        else:
            lines.append(_render_user_line(t['user']))

        if not deep_raw and t.get("turn_id") == current_id:
            continue
        speech = _history_speech(t)
        reply_line = f'{speak_verb}："{speech}"' if speech else ""
        if deep_raw and shows_thoughts:
            thought = _turn_deep(t)["thought"]
            if thought:
                reply_line = (reply_line + "\n" if reply_line else "") + f"我心想：{thought}"
        hint = t.get("think_hint")
        if hint and shows_thoughts and (deep_raw or sr):
            reply_line = (reply_line + "\n" if reply_line else "") + f"我仔细地想了想：{hint}"
        if reply_line:
            lines.append(reply_line)
    if closing:
        lines.append(closing)
    return "[之前的对话]\n" + "\n\n".join(lines)


def _display_hour(h: int) -> tuple:
    """返回 (period_name, display_hour)，如 (\"下午\", 3)"""
    h = h % 24
    period = _get_period(h)
    if h == 0:
        dh = 0
    elif h <= 12:
        dh = h
    else:
        dh = h - 12
    return period, dh


def build_memories_block() -> str:
    """将整理好的记忆按检查点距离排列，注入深层 prompt。"""
    if not CONSOLIDATED_MEMORIES:
        return ""

    now = datetime.now(LOCAL_TZ)
    sd = _session_date(now)
    current_hour = now.hour
    current_cp_num = 0
    for i in range(1, 7):
        if f"{current_hour} {i}" in _COMPLETED_CPS:
            current_cp_num = i

    today_mems = [m for m in CONSOLIDATED_MEMORIES if m.get("date") == sd]
    if not today_mems:
        return ""

    # 层级替代：有高级汇总时跳过低级条目
    hour_consolidated = set()
    period_consolidated_hours = set()
    for m in today_mems:
        if m.get("level") == "hour":
            parts = m.get("checkpoint", "").split()
            if parts:
                hour_consolidated.add(int(parts[0]))
        if m.get("level") == "period":
            pname = m.get("checkpoint", "").replace("period_", "")
            rng = _PERIOD_RANGES.get(pname)
            if rng:
                s, e = rng
                if e > 24:
                    for h in list(range(s, 24)) + list(range(0, e - 24)):
                        period_consolidated_hours.add(h)
                else:
                    for h in range(s, e):
                        period_consolidated_hours.add(h)

    lines = []
    prev_hour = None
    prev_bucket = None
    prev_period_name = None
    in_recent_zone = False

    for m in today_mems:
        if m.get("level") == "10min":
            parts = m.get("checkpoint", "").split()
            if len(parts) == 2 and int(parts[0]) in hour_consolidated:
                continue
        if m.get("level") == "hour":
            parts = m.get("checkpoint", "").split()
            if parts and int(parts[0]) in period_consolidated_hours:
                continue
        cp = m.get("checkpoint", "")
        level = m.get("level", "10min")
        content = m["content"].strip()

        if level == "period":
            lines.append(content)
            prev_hour = None
            prev_period_name = cp.replace("period_", "")
            in_recent_zone = False
            continue

        if level == "hour":
            parts = cp.split()
            h = int(parts[0]) if parts else 0
            cur_period_name = _get_period(h)
            if prev_period_name and cur_period_name != prev_period_name:
                lines.append(f"然后就到了{cur_period_name}。")
            period, dh = _display_hour(h)
            _, next_dh = _display_hour(h + 1)
            lines.append(f"今天{period}{dh}点到{next_dh}点，{content}")
            prev_hour = h
            prev_period_name = cur_period_name
            in_recent_zone = False
            continue

        # 10min level
        parts = cp.split()
        if len(parts) != 2:
            continue
        mem_hour, mem_cp = int(parts[0]), int(parts[1])
        cur_period_name = _get_period(mem_hour)

        if prev_period_name and cur_period_name != prev_period_name:
            lines.append(f"然后就到了{cur_period_name}。")
            prev_period_name = cur_period_name

        if mem_hour != current_hour:
            period, dh = _display_hour(mem_hour)
            base_min = (mem_cp - 1) * 10
            if mem_hour == prev_hour:
                prefix = "然后，"
            else:
                prefix = f"今天{period}{dh}点{base_min}分时，"
            prev_hour = mem_hour
            in_recent_zone = False
        else:
            if not in_recent_zone and lines:
                _, dh = _display_hour(current_hour)
                lines.append(f"然后后面这些是{dh}点之后的。")
                in_recent_zone = True

            dist = current_cp_num - mem_cp
            if dist <= 0:
                bucket = "几分钟前"
            elif dist == 1:
                bucket = "10分钟前"
            elif dist == 2:
                bucket = "20分钟前"
            elif dist == 3:
                bucket = "30分钟前"
            elif dist == 4:
                bucket = "40分钟前"
            else:
                bucket = "50分钟前"
            if prev_hour == mem_hour and prev_bucket == bucket:
                prefix = "然后，"
            else:
                prefix = f"{bucket}，"
            prev_bucket = bucket
            prev_hour = mem_hour

        if not prev_period_name:
            prev_period_name = cur_period_name

        lines.append(f"{prefix}{content}")

    return "\n".join(lines)


# ─── 场景系统 ──────────────────────────────────────────────
SCENES_FILE = "scenes.json"
_scenes_cache = None
_RELATIONSHIP_STAGE = 2  # 固定到关系阶段3「重要的人」（索引2），不切换

def _city_text() -> str:
    """{city}：她和对方住的城市（build_f.json city）；Setup 向导还没填时用一个中性的说法。"""
    return (CITY or "").strip() or "这座城市"


def _json_literal(text: str) -> str:
    """把要塞进 JSON 原文里的值转义（名字/城市里万一带引号或反斜杠，scenes.json 也照样能解析）。"""
    return json.dumps(text, ensure_ascii=False)[1:-1]


def _load_scenes() -> dict:
    global _scenes_cache
    if _scenes_cache is None:
        # persona 文本里的 {user_name} / {city} 在载入时换成配置的称呼和城市（build_f.json user_name / city）
        raw = (po_contract.read_text_bom(SCENES_FILE)
               .replace("{user_name}", _json_literal(USER_NAME or "User"))
               .replace("{city}", _json_literal(_city_text())))
        _scenes_cache = json.loads(raw)
    return _scenes_cache


def _pick_daily(options, logical_day, key: str) -> str:
    """daily_context 的几个可能（数组，通常 5 个 = 各 20%）里按「日期 + 时段」固定抽一个：
    同一个时段里不会变（她不会下午聊着聊着换了一个地方），换天才换。字符串原样返回（旧格式）。"""
    if isinstance(options, str):
        return options
    options = [o for o in (options or []) if isinstance(o, str) and o.strip()]
    if not options:
        return ""
    return random.Random(f"{logical_day.strftime('%Y-%m-%d')}|{key}").choice(options)

def _get_period(hour: int) -> str:
    hour = hour % 24
    if 5 <= hour < 8:
        return "清晨"
    if 8 <= hour < 12:
        return "上午"
    if 12 <= hour < 14:
        return "中午"
    if 14 <= hour < 17:
        return "下午"
    if 17 <= hour < 19:
        return "傍晚"
    if 19 <= hour < 22:
        return "晚上"
    if 22 <= hour or hour < 1:
        return "深夜"
    return "凌晨"


def build_picks_block() -> str:
    return ""





def _vlm_block() -> str:
    return ""


def _static_context(overrides: dict = None) -> dict:
    """scenes.json 里不随时间变化的上下文：recent_mood / current_action / relationship_context /
    communication_style（新版三份模板里都在 {daily_context} 之前，属于缓存前缀）。
    {danmaku_picks} / {video_view} 本版恒为空，模板里若有就清掉。"""
    values = {}
    for k, v in _load_scenes()["deep"]["static"].items():
        if k.startswith("_"):
            continue
        if k == "relationship_stages":
            stage_idx = min(_RELATIONSHIP_STAGE, len(v) - 1)
            values["relationship_context"] = v[stage_idx]["content"]
            continue
        values[k] = v
    values["danmaku_picks"] = ""
    values["video_view"] = _vlm_block()
    # 模板正文里的 {user_name} / {city}（同 scenes：他的称呼、你们住的城市），属于缓存前缀
    values["user_name"] = USER_NAME or "User"
    values["city"] = _city_text()
    if overrides:
        values.update(overrides)
    return values


def _fill_placeholders(template: str, values: dict) -> str:
    """单遍替换已知占位符：填进去的内容（记忆、历史、用户原话）里即使出现 {xxx}，
    也不会被当成占位符二次替换。没给值的占位符原样保留（交给 leftover 检查报警）。"""
    return po_contract._PLACEHOLDER_RE.sub(
        lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), template)


def _fill_static_context(template: str, overrides: dict = None) -> str:
    """只填缓存前缀里的固定占位符（每次调用结果逐字节相同）。"""
    return _fill_placeholders(template, _static_context(overrides))


def _warn_leftovers(kind: str, text: str) -> None:
    """填完后还剩已知占位符 = 模板和代码对不上：打警告，照常继续（R2）。"""
    left = po_contract.leftover_placeholders(text)
    if left:
        print(f"[PO] {kind} prompt still has placeholders after filling: {left}")


def _fill_deep_defaults(template: str, *,
                        memories_override: str = None,
                        history_override: str = None,
                        picks_block: str = "",
                        context_hour: int = None,
                        slots: dict = None) -> str:
    """深层 / 表层 / 思考层共用的占位符填充：固定上下文、今天的经历、时间、场景、记忆、历史。
    slots：本轮专有的值（深层的 {deep_instruction} 等、表层的 {detected_lang}、思考层的
    {thinking_history}），和其它占位符一起单遍替换。记忆和历史只在模板里有对应占位符时才构建。"""
    now = datetime.now(LOCAL_TZ)
    hour = now.hour
    logical_day = now - timedelta(days=1) if hour < SESSION_BOUNDARY_HOUR else now
    weekday_idx = logical_day.weekday()
    weekday = _WEEKDAYS_JP[weekday_idx]
    yesterday_idx = (weekday_idx - 1) % 7
    weekday_yesterday = _WEEKDAYS_JP[yesterday_idx]

    if context_hour is not None:
        period = _get_period(context_hour)
        p_name, dh = _display_hour(context_hour)
        time_str = f"大约是{p_name}{dh}点左右。"
    else:
        period = _scene_period()
        time_str = _local_time_str()
    day_type = "weekend" if weekday_idx >= 5 else "weekday"

    scenes = _load_scenes()
    key = f"{day_type}/{period}"
    fallback = "weekday/晚上"

    deep = scenes["deep"]
    daily_ctx = _pick_daily(deep["daily_context"].get(key, deep["daily_context"][fallback]), logical_day, key)
    # 他不在身边、消息从 Discord/Telegram 来的轮次：她在手机上看消息的场景（text_scene）；否则在家的场景
    scene_table = (deep.get("text_scene") or {}) if _CURRENT_CHANNEL else {}
    scene = scene_table.get(key) or deep["current_scene"].get(key, deep["current_scene"][fallback])

    if hour < SESSION_BOUNDARY_HOUR:
        actual_weekday = _WEEKDAYS_JP[now.weekday()]
        weekday_note = f"{weekday}（或者说应该算是{actual_weekday}了，不知不觉熬过了12点，日期变成第二天了）"
    else:
        weekday_note = weekday
    daily_ctx = daily_ctx.replace("{weekday}", weekday_note).replace("{weekday_yesterday}", weekday_yesterday)

    values = _static_context()
    values.update({
        "daily_context": daily_ctx,
        "current_time": time_str,
        "current_scene": scene,
        # 弹幕精选只在深层实时轮注入（build_messages 传 picks_block）；其余调用默认空
        "danmaku_picks": picks_block,
    })
    if "{memories_block}" in template:
        values["memories_block"] = (memories_override if memories_override is not None
                                    else build_memories_block())
    if "{conversation_history}" in template:
        values["conversation_history"] = (history_override if history_override is not None
                                          else build_deep_history())
    if slots:
        values.update(slots)
    return _fill_placeholders(template, values)


def _pending_mind_instruction(pending: str) -> str:
    """待思考态：告诉深层它已经在想什么了，别对同一件事重复举手。"""
    return (
        f'你刚刚已经决定要想、马上就会想好的是——{pending}。'
        f'这件事你正在想，结果很快就来，所以现在不用再为它纠结。'
        f'如果你觉得照这个方向想下去没问题，就不用写、也不用管它。'
        f'但要是冒出新的、和这个不一样的东西要想，或者发现刚才那个方向不太对、需要改，'
        f'就把新的那一点写出来，并在最后缀上【想想】。'
        f'只是随口能接的家常，照常自然过去就好。'
    )


def _pending_mind_block() -> str:
    """{pending_mind}：上一轮喊了【想想】、思考层结果还没回来时的那段提醒；否则为空。
    静态的「我心想」规则留在缓存前缀里、每轮不变，这里只补这一轮的情况。"""
    with _think_state_lock:
        pending = _pending_think
    return _pending_mind_instruction(pending) if pending else ""


def _make_parts(static_prefix: str, dynamic_filled: str, user_content: str) -> dict:
    """统一的 parts 结构：
    - system_static / system_dynamic：缓存友好（Anthropic content blocks / xAI 多 system）
    - system：拼好的整体（OpenRouter / 不缓存路径用）
    """
    return {
        "system_static": static_prefix,
        "system_dynamic": dynamic_filled,
        "system": static_prefix + dynamic_filled,
        "user_content": user_content,
    }


def _tidy_dynamic(text: str) -> str:
    """逐轮槽位为空时（没有待思考提醒 / 没有脱口而出）不留一串空行。"""
    return re.sub(r"\n{3,}", "\n\n", text)


def build_messages(user_message: str, blurted_reply: str = None, reply_lang: str = None,
                   reply_lang_reason: str = "detected") -> dict:
    """
    深层 prompt：history 结尾已含当前轮的对方发言（正常为 '<user_name>：<text>'，即 USER_NAME，
    打断场景则是打断合成的自描述）。模板在 {daily_context} 处切成
      静态前缀（人格、格式规则、词表、固定上下文；逐字节不变，可缓存）
      + 逐轮部分（记忆、历史、时间场景、{pending_mind}、{blurt_block}、{say_marker}、
        {deep_instruction}、{language_line}）。

    四种情况（normal/interrupt × no-blurt/blurt）分别使用不同的 {deep_instruction}
    与 user_content，定义为上方常量，方便独立调整。

    blurted_reply=None → 深层独立模式（{say_marker} = "我说：\\n我心想："）
    blurted_reply="..."  → 表层已先说出口（say+think，或 think 模式的垫话）：{blurt_block}
                           注入"我脱口而出"段，{say_marker} = "我接着说：\\n我心想："
    reply_lang / reply_lang_reason → {language_line}（po_contract.language_line），prompt 的最后一行。
    """
    static_template, dynamic_template = po_contract.split_static(load_template())

    is_interrupt = _is_interrupt_user_msg(user_message)
    has_blurt = bool(blurted_reply)

    if is_interrupt and has_blurt:
        instruction = DEEP_INSTRUCTION_INTERRUPT_BLURT
        user_content = USER_CONTENT_INTERRUPT_BLURT
    elif is_interrupt:
        instruction = DEEP_INSTRUCTION_INTERRUPT
        user_content = USER_CONTENT_INTERRUPT
    elif has_blurt:
        instruction = DEEP_INSTRUCTION_NORMAL_BLURT
        user_content = USER_CONTENT_NORMAL_BLURT
    else:
        instruction = DEEP_INSTRUCTION_NORMAL
        user_content = USER_CONTENT_NORMAL

    blurt_block = ""
    if has_blurt:
        blurt_block = (
            f'我脱口而出"{blurted_reply}"'
            '（只是刚刚的第一反应，不一定对，也许可以继续顺着说，'
            '但也有可能需要想一想然后重新调整对话方向。你脱口而出的内容是你已经说出口的，没必要重复了）'
        )
    language_line = po_contract.language_line(reply_lang, reply_lang_reason)
    slots = {
        # 待思考态：上一轮喊了【想想】、结果还没回来时，提醒深层它已经在想什么了。
        "pending_mind": _pending_mind_block(),
        "blurt_block": blurt_block,
        "say_marker": DEEP_TEMPLATE_SAY_MARKER_BLURT if has_blurt else DEEP_TEMPLATE_SAY_MARKER,
        "deep_instruction": instruction,
        "language_line": language_line,
    }
    history = build_deep_history()
    static_prefix = _fill_static_context(static_template)
    dynamic = _tidy_dynamic(_fill_deep_defaults(dynamic_template, picks_block=build_picks_block(),
                                                history_override=history, slots=slots))
    _warn_leftovers("deep", static_prefix + dynamic)
    parts = _make_parts(static_prefix, dynamic, user_content)
    # 本轮附加上下文（_with_round_context）插在历史之后、{pending_mind} 之前，语言行永远最后。
    parts["_history_text"] = history
    return parts


_WEEKDAYS_JP = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

def _local_time_str() -> str:
    now = datetime.now(LOCAL_TZ)
    period = _get_period(now.hour)
    if now.hour < SESSION_BOUNDARY_HOUR:
        logical_weekday = _WEEKDAYS_JP[(now - timedelta(days=1)).weekday()]
        actual_weekday = _WEEKDAYS_JP[now.weekday()]
        return (f"现在是{logical_weekday}{period}{now.hour}点"
                f"（或者说应该算是{actual_weekday}了，不知不觉熬过了12点，日期变成第二天了）。")
    weekday = _WEEKDAYS_JP[now.weekday()]
    return f"现在是{weekday}{period}{now.hour}点。"


_DETECTED_LANG_NAMES = {"zh": "CHINESE", "en": "ENGLISH", "ja": "JAPANESE",
                        "mixed": "MIXED (follow the user's style)"}


def detect_language(text: str) -> str:
    """表层 {detected_lang}：po_contract.detect_lang 的结果换成表层模板认的名字。
    没有任何字母/汉字时按 CHINESE（与旧版一致）。"""
    return _DETECTED_LANG_NAMES.get(po_contract.detect_lang(text or ""), "CHINESE")


def build_surface_messages(user_message: str, lang_text: str = None) -> dict:
    """表层模板：和深层同一套固定上下文/时间/场景/记忆（表层预算）填充，
    {relationship_context} 用 scenes.json 的 surface.context（第二人称，R17），
    历史只喂说出口的台词，再补表层专有的 {detected_lang}。
    lang_text：用来判断语种的干净原话（打断包装之前）；不给就用 user_message 去掉内部标记后的文本。"""
    static_template, dynamic_template = po_contract.split_static(load_surface_template())
    clean_user = _user_for_llm(user_message)
    lang = detect_language(lang_text if lang_text is not None else clean_user)
    surface = _load_scenes().get("surface") or {}
    ctx = {"relationship_context": surface["context"]} if surface.get("context") else {}
    static_prefix = _fill_static_context(static_template, ctx)
    # 表层只喂「说出口的台词」历史（build_surface_history），不要深层那套
    # 含「我心想 / 我仔细地想了想(think_hint)」的内部规划——那些是给深层用的，
    # 喂给又快又弱的表层会把它锚死在旧话题上（曾出现"深层聊直播、表层念漫画"的分裂）。
    history = build_surface_history()
    dynamic = _fill_deep_defaults(dynamic_template, history_override=history,
                                  slots=dict(ctx, detected_lang=lang))
    _warn_leftovers("surface", static_prefix + dynamic)
    parts = _make_parts(static_prefix, dynamic, clean_user)
    parts["_history_text"] = history
    return parts


def _spoken_text(text: str) -> str:
    """说出口的文字（入历史/记忆用）：声效标签发声端已经播过，这里剥掉。"""
    return " ".join(po_contract.strip_sfx(text or "").split())


def parse_response(raw: str, blurt: str = None) -> list:
    """
    深层输出 → [{speech, thought, segments, needs_help, wants_continue}]。
    规则在 po_contract.extract_deep（和发声端的流式解析是同一套，C16/C19）：
      · [tag]"…" 在哪都算台词（标签宽松解析，认不出就 casual_neutral）；缺右引号到下一个
        [tag] 或结尾为止；[tag] 后面没引号的同一行文字也算台词。
      · 「我心想/我反思/我思考」之前、单独成行的无标签引号也算台词（语气沿用前一个标签）；
        之后的无标签引号、以及其它文字都是 thought。
      · 台词过一遍清洗（语言标注、markdown 星号、字面 \\n、残留标签/引号）；
        blurt 给了的话，第一段开头和表层已说出口的那句重复的部分去掉。
    segments 里的 text 保留 【声效】 标签（发声端要播）；speech 是去掉声效后拼好的整句。
    【想想】/【接着说】 只是开关（needs_help / wants_continue），不会出现在 speech/thought 里。
    """
    d = po_contract.extract_deep(raw or "", blurt)
    return [{"speech": d["speech"], "thought": d["thought"], "segments": d["segments"],
             "needs_help": d["needs_help"], "wants_continue": d["wants_continue"]}]


def _extract_surface_fields(raw: str) -> dict:
    """表层 4 行格式 status / tone / mode / reply（C15：没有 recall），规则见
    po_contract.parse_surface：字段写法宽松；reply 只取 reply: 后的第一行，缺标签时取第一行
    自由文本；say 且 reply 为空、status 为 ok 时改成 think；status 只作参考，不拦生成（C18）。
    返回 status、tone（解析后的真实情绪键）、tone_raw、mode、reply（声效已剥掉）、speak_filler。"""
    s = po_contract.parse_surface(raw or "")
    return {"status": s["status"], "tone": s["tone"], "tone_raw": s["tone_raw"],
            "mode": s["mode"], "reply": _spoken_text(s["reply"]), "speak_filler": s["speak_filler"]}


def parse_surface_response(raw: str) -> list:
    """表层说出口的那一行（think 模式的垫话也算，它同样会被说出来，C14）。"""
    return [{"speech": _extract_surface_fields(raw)["reply"], "thought": ""}]


# ─── 思考层 ─────────────────────────────────────────────────

def _render_thinking_turn(t: dict, show_thought: bool = True) -> str:
    """把一轮对话渲染成第三人称叙述（给思考层看，不带 [心想]/[模版] 原始标记）。
    TELEMETRY_SPEC §3：对方用名字，一轮一句「她说："…"」（脱口而出 + 深层台词合一），
    「她心里」只给最近 HISTORY_THOUGHT_TURNS 轮（show_thought）。"""
    lines = []
    name = _history_user_name()
    if t.get("inject_cue"):
        # 注入指导轮：外部给她注入的情景/指导（无前缀裸括号），照原样让思考层也看到。
        lines.append(t["inject_cue"])
    elif t.get("open_cue"):
        # 开口轮：她是主动开口（思考层自己给的第三种指导促成的），没有对方发言。
        lines.append("（她主动开口）")
    elif _is_interrupt_user_msg(t.get("user", "")) and t.get("f_user_text"):
        # 打断轮：内部的打断包装是她的第一人称（"When I was saying…"），
        # 照搬会把「我」算到对方头上（C12）；这里直接写成对方打断了她。
        lines.append(f"{name}打断了她：{t['f_user_text']}")
    else:
        lines.append(_render_user_line(t.get("user", ""), name))
    speech = _history_speech(t)
    if speech:
        say_verb = "她准备说" if t.get("interrupted") else "她说"
        lines.append(f'{say_verb}："{speech}"')
    if show_thought and t.get("deep_raw"):
        thought = _turn_deep(t)["thought"]
        if thought:
            lines.append(f"她心里：{thought}")
    return "\n".join(lines)


def _render_thinking_note(e: dict) -> str:
    """渲染一条思考层私有记录（只有思考层自己看得到）。
    呈现完整闭环：她当时为什么来找你 → 你怎么分析 → 你给了什么指导。"""
    lines = ["〔你当时的思考（只有你自己看得到）〕"]
    req = (e.get("deep_request") or "").strip()
    if req:
        lines.append(f"她当时来找你：{req}")
    if e.get("analysis"):
        lines.append(f"分析：{e['analysis']}")
    if e.get("提示"):
        lines.append(f"你给的提示：{e['提示']}")
    if e.get("计划"):
        lines.append(f"你播的计划：{e['计划']}")
    if e.get("开口"):
        if e.get("open_delivered") is False:
            # 开口没执行（没有活跃客户端 / 她正在说话 / 开口被配置关闭）：别让思考层以为她说过了。
            lines.append(f"你想让她开口说：{e['开口']}（当时没能说出口）")
        else:
            lines.append(f"你让她开口说：{e['开口']}")
    if len(lines) == 1:
        lines.append("（当时你看过，但没有给出指导。）")
    return "\n".join(lines)


def build_thinking_history() -> str:
    """思考层视角的时间线：对话（第三人称）+ 按轮次交织的思考层私有记录。"""
    turns = _unconsolidated_turns()
    with _think_lock:
        entries = list(THINKING_LOG)
    # 思考层记录按轮次 id 挂到它那一轮下面；turn_num 每次会话从头计数，只按序号挂会把
    # 别的会话里同序号轮次的旧记录混进这次的时间线（2026-09-28 发现）。没有 id 的旧记录才按序号。
    by_turn: dict = {}
    for e in entries:
        key = ("id", e["after_turn_id"]) if e.get("after_turn_id") else ("num", e.get("after_turn_num"))
        by_turn.setdefault(key, []).append(e)
    if not turns and not entries:
        return "（还没有对话。）"
    blocks = []
    # R19 / TELEMETRY_SPEC §3：「她心里」只留给窗口里最近 HISTORY_THOUGHT_TURNS 轮。
    keep = max(0, int(HISTORY_THOUGHT_TURNS or 0))
    thought_ids = {t.get("turn_id") for t in turns[-keep:]} if keep else set()
    opening, separators, closing = _history_time_notes(turns)
    if opening:
        blocks.append(opening)
    for i, t in enumerate(turns):
        if i in separators:
            blocks.append(separators[i])
        blocks.append(_render_thinking_turn(t, show_thought=t.get("turn_id") in thought_ids))
        # 思考层私有记录紧跟在它那一轮后面（时间行不插在两者之间）。
        for e in by_turn.get(("id", t.get("turn_id")), []) + by_turn.get(("num", t.get("turn_num")), []):
            blocks.append(_render_thinking_note(e))
    if closing:
        blocks.append(closing)
    return "\n\n".join(blocks)


def build_thinking_messages(deep_request: str = "") -> dict:
    """思考层 prompt：和深层同一套固定上下文/时间/场景/记忆填充，再补 {thinking_history}
    与 {deep_request}。在 {daily_context} 处切静态/动态（所有规则都在静态前缀里，可缓存）。"""
    static_template, dynamic_template = po_contract.split_static(load_thinking_template())
    static_prefix = _fill_static_context(static_template)
    # history_override="" 让 _fill_deep_defaults 不去构建深层历史（思考层用自己的）
    dynamic = _fill_deep_defaults(dynamic_template, history_override="", slots={
        "thinking_history": build_thinking_history(),
        "deep_request": deep_request.strip() or "（这次没有特别的求助，你只是回来看看她、想想接下来。）",
    })
    _warn_leftovers("thinking", static_prefix + dynamic)
    # 顺序必须和 思考.txt 的约定一致（先指导、[分析]放最后），否则模型会回一段
    # 「注意：你要求先写[分析]，但我的规则是…」的前言来纠正，那段前言里的字面标记
    # 会把解析带偏。
    user_content = "请按上面约定的格式输出：先写指导（[指导方式] + [指导内容]），[分析] 放到最后。"
    return _make_parts(static_prefix, dynamic, user_content)


_THINK_CHANNELS_RE = re.compile(r"通道[:：]\s*(.+)")
_THINK_TAGS = ("提示", "计划", "开口")
# C20：模型偶尔把标签写成全角/变体括号（＜提示＞、〈计划〉、【分析】、［分析］），先归一。
# 只改标签本身，正文里的《书名》、全角斜杠等原样保留。
_THINK_SECTION_RE = re.compile(r"[\[［【]\s*(分析|指导方式|指导内容)\s*[\]］】]")
_THINK_TAG_VARIANT_RE = re.compile(r"[<＜〈《]\s*([/／]?)\s*(提示|计划|开口)\s*[>＞〉》]")
# 偶尔写成段落标签 [开口] / 【提示】 当开标签用（后面跟 </开口>）：也当开标签。
_THINK_TAG_SQUARE_RE = re.compile(r"[\[［【]\s*(提示|计划|开口)\s*[\]］】]")
_THINK_BOUNDARY_RE = re.compile(r"</?(?:提示|计划|开口)>|\[(?:分析|指导方式|指导内容)\]")
_THINK_TAG_ANY_RE = re.compile(r"</?(?:提示|计划|开口)>")


def _norm_think_text(raw: str) -> str:
    """变体括号、标签内多余空格 → 标准写法（<提示>…</提示>、[分析]）。"""
    text = _THINK_SECTION_RE.sub(r"[\1]", raw or "")
    text = _THINK_TAG_SQUARE_RE.sub(r"<\1>", text)
    return _THINK_TAG_VARIANT_RE.sub(lambda m: "<" + ("/" if m.group(1) else "") + m.group(2) + ">", text)


def _extract_think_tag(text: str, tag: str) -> str:
    """<tag>…</tag>。没闭合就取到下一个标签/段落标记或结尾；只有孤零零的 </tag>，
    就取它前面、上一个标签/段落标记之后的那段（去掉「通道:」那行）。"""
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.S)
    if m:
        return m.group(1).strip()
    m = re.search(rf"<{tag}>", text)
    if m:
        rest = text[m.end():]
        b = _THINK_BOUNDARY_RE.search(rest)
        return (rest[:b.start()] if b else rest).strip()
    m = re.search(rf"</{tag}>", text)
    if m:
        before = text[:m.start()]
        bounds = list(_THINK_BOUNDARY_RE.finditer(before))
        piece = before[bounds[-1].end():] if bounds else before
        return _THINK_CHANNELS_RE.sub("", piece).strip()
    return ""


def _guidance_body(text: str) -> str:
    """[指导内容] 和最后一个 [分析] 之间的正文（标签剥掉）。只在只声明了一个通道、
    却没有可解析的标签时兜底用（R13）。"""
    start = text.find("[指导内容]")
    if start == -1:
        return ""
    start += len("[指导内容]")
    end = text.rfind("[分析]")
    if end < start:
        end = len(text)
    return _THINK_TAG_ANY_RE.sub("", text[start:end]).strip()


def parse_thinking_response(raw: str) -> dict:
    """解析思考层输出：通道 / <提示>/<计划>/<开口> / [分析]（C20 宽松解析）。

      - 标签写成全角/变体括号也认（先归一）；
      - 提示/计划/开口：标签唯一，直接从全文抓；没闭合就取到下一个标签/段落或结尾；
        只剩孤立的闭合标签就取它前面那段；
      - [分析]：取最后一个（模板里分析放最末），避开前言里字面提到的 [分析]；
        分析写在指导前面时，只取到指导开始之前；
      - 通道：从全文找「通道:」声明；没有声明就按实际有内容的标签推断；
        只声明了一个通道、却没有可解析的标签时，取 [指导内容] 和 [分析] 之间的正文。
    """
    text = _norm_think_text(raw)
    found = {name: _extract_think_tag(text, name) for name in _THINK_TAGS}

    analysis = ""
    a_idx = text.rfind("[分析]")
    if a_idx != -1:
        rest = text[a_idx + len("[分析]"):]
        b = re.search(r"\[(?:指导方式|指导内容)\]|<(?:提示|计划|开口)>", rest)
        analysis = (rest[:b.start()] if b else rest).strip()

    channels = []
    chm = _THINK_CHANNELS_RE.search(text)
    if chm:
        channels = [name for name in _THINK_TAGS if name in chm.group(1)]
    if len(channels) == 1 and not _clean_hint_piece(found[channels[0]]):
        body = _guidance_body(text)
        if body:
            found[channels[0]] = body
    if not channels:
        # 没解析到「通道:」声明（或被前言干扰）：按有内容的标签兜底，免得通道丢失。
        channels = [name for name in _THINK_TAGS if _clean_hint_piece(found[name])]

    return {
        "analysis": analysis,
        "channels": channels,
        "提示": found["提示"],
        "计划": found["计划"],
        "开口": found["开口"],
    }


_HINT_PLACEHOLDERS = {"", "（无）", "(无)", "无", "none", "n/a", "-", "—", "……", "省略"}


def _clean_hint_piece(s: str) -> str:
    """把思考层 提示/计划 里的占位（（无）/无/-…）归一成空串。
    这些字面非空但没实际内容，直接拼进 think_hint 会覆盖同一轮已有的真提示。"""
    s = (s or "").strip()
    return "" if s.lower() in _HINT_PLACEHOLDERS else s


def run_thinking_once(deep_request: str = "", on_guidance=None,
                      target_turn_id: str = None) -> dict:
    """跑一次思考层（流式）：构建 prompt → 流式调用 → 解析 → 记入私有日志。

    反序模板下「指导」全部排在 [分析] 之前，所以一旦流里出现 [分析] 标记，
    指导部分就已完整——立刻解析并通过 on_guidance(dict) 回调发出去，不必等后面
    那段分析写完（分析只用于私有日志）。on_guidance 收到的 dict 含 channels/
    提示/计划/开口（analysis 为空）。整段跑完后返回完整记录（含 analysis）。

    target_turn_id：把「提示/计划」挂到指定轮次（即出【想想】那一轮）。后台异步跑时
    必须显式指定，否则会错挂到跑完时恰好最新的那轮。不给（空闲节奏）则挂到当前最后一轮。
    """
    # 思考层也要知道她手边的工具、哪个联系不上、眼下有没有事在办（第三人称版），不然"开口"会替她编结果。
    parts = _with_capabilities(build_thinking_messages(deep_request), voice="third")
    parts["conv_id"] = "hane-thinking"   # xAI 缓存：思考层 pin 到同一 server（非 xai provider 忽略）
    model_config = AVAILABLE_MODELS[DEFAULT_THINKING_MODEL]

    raw = ""
    guidance_fired = False
    # 思考层走 Anthropic 时用独立 THINKING_ANTHROPIC_KEY；其它 provider 走通用分发 _pick_stream。
    if model_config.get("provider") == "anthropic":
        _think_stream = _stream_anthropic(parts, model_config["model"],
                                          api_key=THINKING_ANTHROPIC_KEY,
                                          thinking_disabled=model_config.get("thinking_disabled", False))
    else:
        _think_stream = _pick_stream(parts, model_config)
    for chunk in _think_stream:
        raw += chunk
        if on_guidance and not guidance_fired:
            norm = _norm_think_text(raw)
            # 只有当某个 [分析] 之前已经出现过指导的闭合标签，才认定指导段真的写完了。
            # 否则模型在正式结构前的「前言」里字面提到 [分析] 会导致空触发。
            for am in re.finditer(r"\[分析\]", norm):
                if re.search(r"</(提示|计划|开口)>", norm[:am.start()]):
                    guidance_fired = True
                    try:
                        on_guidance(parse_thinking_response(norm[:am.start()]))
                    except Exception as e:
                        print(f"[Hane] reflection on_guidance callback failed: {e}")
                    break

    parsed = parse_thinking_response(raw)
    # 流里没能提前触发（没有 [分析]、标签没闭合…）时，兜底用完整解析补发一次指导
    if on_guidance and not guidance_fired:
        try:
            on_guidance(parsed)
        except Exception as e:
            print(f"[Hane] reflection on_guidance callback failed: {e}")

    with _hist_lock:
        if target_turn_id is not None:
            after_turn_id = target_turn_id
            after_turn_num = 0
            for t in CONVERSATION_HISTORY:
                if t.get("turn_id") == target_turn_id:
                    after_turn_num = t.get("turn_num", 0)
                    break
        else:
            last = CONVERSATION_HISTORY[-1] if CONVERSATION_HISTORY else None
            after_turn_num = last.get("turn_num", 0) if last else 0
            after_turn_id = last.get("turn_id") if last else None

    now = datetime.now(LOCAL_TZ)
    entry = {
        "id": f"think_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
        "ts": now.strftime("%Y-%m-%d %H:%M:%S"),
        "after_turn_num": after_turn_num,
        "after_turn_id": after_turn_id,
        "deep_request": deep_request.strip(),
        "analysis": parsed["analysis"],
        "channels": parsed["channels"],
        "提示": parsed["提示"],
        "计划": parsed["计划"],
        "开口": parsed["开口"],
        "raw": raw,
    }
    add_thinking_entry(entry)

    # 慢通道注入：提示 + 计划 都挂到「在哪轮之后想的」那一轮，随历史一起喂回深层。
    # 两者机制相同，只是尺度不同（一两轮的提点 vs 几轮的弧线），合成一条内心思考。
    # 计划滑出最近窗口后由 build_deep_history 的 _pinned_plan 继续带着，直到被新计划替换。
    # 过滤掉模型写的「（无）/无/-」这类占位——它们非空但没内容，曾把同一轮上一条
    # 真提示覆盖成「（无）\n（无）」。占位视为空，既不写、也不覆盖既有提示。
    hint_text = "\n".join(
        p for p in (_clean_hint_piece(parsed["提示"]), _clean_hint_piece(parsed["计划"])) if p
    )
    if hint_text and after_turn_id:
        with _hist_lock:
            t = _find_turn(after_turn_id)
            if t is not None:
                t["think_hint"] = hint_text
        # 立刻落盘：思考层是异步的，写完若不存盘，只能等下次别的操作顺带保存。
        if t is not None:
            _save_history()

    # 第三种指导（开口）：让她现在就主动说话——立刻起一个开口轮发声（快通道）。
    open_content = _clean_hint_piece(parsed["开口"])
    if open_content:
        delivered = _maybe_fire_open(open_content)
        with _think_lock:
            entry["open_delivered"] = bool(delivered)
            if delivered:
                entry["open_turn_id"] = delivered
            _save_thinking_log()

    return entry


def _maybe_fire_open(open_content: str):
    """思考层「开口」通道产出 → 立刻让她主动发声（B12）。
    返回起的开口轮 turn_id（没起就是 False），真假值和原来一样可以直接当 bool 用。

    包成第一人称括号提示喂给开口轮（只喂这一轮、不进历史）。
    仅在有活跃客户端且当前没有别的生成在跑时触发，避免和正在进行的对话打架。
    模型取当前选中的（表层/深层），不用函数定义时的默认值。
    """
    if not open_content or not open_content.strip():
        return False
    sid = _LAST_SID
    if not sid:
        print("[Hane] speaking first: no page connected: skipped")
        return False
    with _ws_active_lock:
        busy = bool(_ws_active)
    if busy:
        print("[Hane] speaking first: a reply is being written: skipped this time")
        return False
    cue = _wrap_open_cue(open_content)
    tid = _start_open_gen(sid, cue, DEFAULT_SURFACE_MODEL, DEFAULT_DEEP_MODEL)
    print(f"[Hane] speaking first: started turn {tid}" if tid else "[Hane] speaking first: no turn started (switched off, or nothing to say)")
    return tid or False


# 开口括号的「文字封装 + 前缀」：把思考层产出的开口内容框成一句对她说的
# 「轮到你主动开口、把这些自然讲出来」的指令（系统口吻 = 你；括号里的内容本身是她要说的话）。本系统里括号 = 不说出口的旁白/内心，
# 单纯裸包一层 () 深层会把它当内心、不一定真开口；加上这层框定（对照早期 work 的
# 「（趁现在，我先主动跟大家说点什么：…）」写法）深层才清楚这是该她现在说出口的话。
def _wrap_open_cue(open_content: str) -> str:
    inner = (open_content or "").strip()
    # 去掉思考层可能自带的最外层整对括号，避免双重括号。
    if (inner[:1] in "（(") and (inner[-1:] in "）)"):
        inner = inner[1:-1].strip()
    return (
        f"（轮到你主动开口了——下面这些是你想说的，"
        f"用你自己的话自然讲出来、别照着背：{inner}）"
    )


def trigger_thinking_async(deep_request: str = "", target_turn_id: str = None,
                           reason: str = "", set_pending: bool = True) -> bool:
    """后台异步跑一次思考层（慢通道）。被深层【想想】或后台节奏调用。

    并发：最多同时跑 _THINKING_MAX 个；满了才跳过（不再是单锁丢弃第二个请求）。
    每个结果靠 target_turn_id 各归各位。
    set_pending：是否登记「待思考态」（把这条记为深层正在等的那条心想，期间深层 prompt
      的「我心想」会提示它"我已经在想这个了"）。只有深层自己喊【想想】才该置 True；
      空闲节奏等后台触发不是她的心想，传 False，免得污染下一轮真实对话的「我心想」。
    返回是否真的起了线程。线程内自负盈亏（异常只打日志，绝不影响实时对话）。
    """
    global _thinking_inflight, _pending_think, _pending_seq
    if not THINKING_ENABLED:
        return False
    with _think_state_lock:
        if _thinking_inflight >= _THINKING_MAX:
            print(f"[Hane] reflection busy ({_THINKING_MAX} running): skipped this trigger ({reason})")
            return False
        _thinking_inflight += 1
        _pending_seq += 1
        my_seq = _pending_seq
        owns_pending = False
        if set_pending:
            req_clean = po_contract.strip_controls(deep_request or '').strip()
            if req_clean:
                _pending_think = req_clean
                owns_pending = True

    def _run():
        global _thinking_inflight, _pending_think
        try:
            entry = run_thinking_once(deep_request=deep_request,
                                      target_turn_id=target_turn_id)
            ch = entry.get("channels") or "-"
            print(f"[Hane] reflection done ({reason}), channels={ch}, "
                  f"after turn={entry.get('after_turn_id')}")
        except Exception as e:
            print(f"[Hane] reflection failed in the background ({reason}): {e}")
        finally:
            with _think_state_lock:
                _thinking_inflight -= 1
                # 只有"最新那条登记了 pending 的"求助才负责清空 pending；被更新的求助
                # 盖过就不清，让 pending 始终指向深层最近一次在等的东西。
                if owns_pending and _pending_seq == my_seq:
                    _pending_think = None

    threading.Thread(target=_run, daemon=True).start()
    return True


def _stash_pending_think(turn_id: str, deep_request: str, reason: str) -> None:
    """深层喊【想想】时不立刻起思考层，而是把请求暂存到这一轮，等这一轮「受保护」
    后再触发（见 _protect_latest / _fire_pending_think）。这样目标轮一定还在历史里，
    思考层产物不会因为目标轮在被保护前就被 prune 而丢失。
    若暂存时这一轮已经受保护（例如 TTS 首音频先到、深层后收尾），就地立刻触发。"""
    fire_now = False
    with _hist_lock:
        t = _find_turn(turn_id)
        if t is None:
            return
        t["pending_think"] = {"deep_request": deep_request or "", "reason": reason}
        fire_now = bool(t.get("protected"))
    if fire_now:
        _fire_pending_think(turn_id)


def _fire_pending_think(turn_id: str) -> None:
    """把某轮暂存的【想想】请求真正交给思考层（该轮受保护后调用）。
    pop 是原子的：「保护事件」和「暂存时已受保护」两条路径都走这里，谁先 pop 谁触发，
    另一条拿到 None 直接跳过，天然防重复。"""
    with _hist_lock:
        t = _find_turn(turn_id)
        req = t.pop("pending_think", None) if t is not None else None
    if not req:
        return
    trigger_thinking_async(
        deep_request=req["deep_request"],
        target_turn_id=turn_id,
        reason=req["reason"],
    )


def _stash_pending_continue(turn_id: str, sid: str) -> None:
    """深层这轮反思后打了【接着说】：不立刻起续说轮，先把它暂存到「这一轮」，
    等这一轮的 TTS 音频彻底播完（发声端发来 speech_done）再触发，见 ws_speech_done /
    _fire_pending_continue。等播完再起，等于真人"换口气"后接着说；且那时音频不忙，
    续说轮走现成主动轮认领路径正常出声，不会被发声端 busy 守卫丢掉。
    暂存只是存档，不在这里触发（触发统一在 speech_done）。"""
    with _hist_lock:
        t = _find_turn(turn_id)
        if t is None:
            return
        t["pending_continue"] = {"sid": sid or ""}


def _fire_pending_continue(turn_id: str) -> None:
    """把某轮暂存的【接着说】真正起成一个自续说主动轮。
    唯一触发入口是发声端的 speech_done（该轮 TTS 音频彻底播完）——等"换口气"后再续，
    此时音频不忙、续说轮走现成主动轮认领正常出声。pop 原子，谁先 pop 谁触发、防重复。"""
    with _hist_lock:
        t = _find_turn(turn_id)
        req = t.pop("pending_continue", None) if t is not None else None
    if not req:
        return
    sid = req.get("sid") or _LAST_SID
    if not sid:
        print("[Hane] keep-talking marker: no page connected: skipped")
        return
    print(f"[Hane] keep-talking marker: turn {turn_id} finished playing → starting her follow-up turn")
    _start_continue_gen(sid)


def _openai_headers(provider: str, conv_id: str = None) -> tuple:
    """返回 (url, headers)，目前支持 xai / groq。
    conv_id 仅 xAI 用：x-grok-conv-id 让请求落到同一台 server，命中前缀缓存。"""
    if provider == "xai":
        if not XAI_KEY:
            raise ValueError("XAI_API_KEY 未配置")
        h = {
            "Authorization": f"Bearer {XAI_KEY}",
            "Content-Type": "application/json",
        }
        if conv_id:
            h["x-grok-conv-id"] = conv_id
        return XAI_BASE, h
    if provider == "groq":
        if not GROQ_KEY:
            raise ValueError("GROQ_API_KEY 未配置")
        return GROQ_BASE, {
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json",
        }
    if provider == "cerebras":
        if not CEREBRAS_KEY:
            raise ValueError("CEREBRAS_API_KEY 未配置")
        return CEREBRAS_BASE, {
            "Authorization": f"Bearer {CEREBRAS_KEY}",
            "Content-Type": "application/json",
        }
    if provider == "ollama":
        # 本地 ollama：OpenAI 兼容、无需鉴权（dummy bearer 被忽略）。省 VRAM 给 STT，模型≤24GB。
        return os.getenv("AMIKA_LOCAL_MODEL_URL", "http://127.0.0.1:11436/v1/chat/completions"), {
            "Authorization": "Bearer ollama",
            "Content-Type": "application/json",
        }
    raise ValueError(f"不支持的 provider: {provider}")


def _openai_messages(parts: dict, no_think: bool = False, split_system: bool = False) -> list:
    """OpenAI 兼容格式的 messages。
    split_system=True：system 拆成 [static, dynamic] 两条消息（xAI 缓存友好）。
    split_system=False：system 拼成一条（Groq 等无缓存场景）。
    """
    user_content = parts["user_content"]
    if no_think:
        user_content = user_content + " /no_think"

    msgs = []
    if split_system and parts.get("system_static"):
        msgs.append({"role": "system", "content": parts["system_static"]})
        if parts.get("system_dynamic"):
            msgs.append({"role": "system", "content": parts["system_dynamic"]})
    else:
        msgs.append({"role": "system", "content": parts.get("system", "")})
    msgs.append({"role": "user", "content": user_content})
    return msgs


def call_llm(user_message: str, model: str, provider: str, no_think: bool = False) -> str:
    """统一调用入口（非流式），按 provider 路由到不同 API"""
    parts = build_messages(user_message)

    if provider == "gemini":
        return _call_gemini(parts, model)
    if provider == "anthropic":
        return _call_anthropic(parts, model)

    split = (provider == "xai")
    url, headers = _openai_headers(provider, conv_id=parts.get("conv_id"))
    resp = http_requests.post(
        url, headers=headers,
        json={"model": model, "messages": _openai_messages(parts, no_think=no_think, split_system=split)},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    if "choices" in data and data["choices"]:
        return data["choices"][0]["message"]["content"]
    raise ValueError(f"API 响应异常: {data}")


def _stream_openai(parts: dict, model: str, provider: str, no_think: bool = False,
                   reasoning_effort: str = None):
    """流式调用 xAI / Groq（OpenAI 兼容格式）。
    xAI：split_system=True + x-grok-conv-id + include_usage 打印缓存命中。
    reasoning_effort：gpt-oss 等推理模型控速用（如 'low'），其它模型留空。
    """
    split = (provider == "xai")
    url, headers = _openai_headers(provider, conv_id=parts.get("conv_id"))
    body = {
        "model": model,
        "messages": _openai_messages(parts, no_think=no_think, split_system=split),
        "stream": True,
    }
    if reasoning_effort:
        body["reasoning_effort"] = reasoning_effort
    if provider == "xai":
        body["stream_options"] = {"include_usage": True}
    resp = http_requests.post(
        url, headers=headers,
        json=body,
        timeout=60, stream=True,
    )
    resp.raise_for_status()
    resp.encoding = "utf-8"
    last_usage = None
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload.strip() == "[DONE]":
            break
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue
        usage = chunk.get("usage")
        if usage:
            last_usage = usage
        choices = chunk.get("choices", [])
        if not choices:
            continue
        delta = choices[0].get("delta", {})
        text = delta.get("content", "")
        if text:
            yield text
    if provider == "xai" and last_usage:
        details = last_usage.get("prompt_tokens_details") or {}
        cached = details.get("cached_tokens", 0)
        total = last_usage.get("prompt_tokens", 0) or 0
        out = last_usage.get("completion_tokens", 0) or 0
        pct = (100 * cached // total) if total else 0
        print(f"[xAI cache] prompt={total} cached={cached} ({pct}%) completion={out}")


def _anthropic_headers(api_key: str = None) -> dict:
    key = api_key or ANTHROPIC_KEY
    if not key:
        raise ValueError("ANTHROPIC_API_KEY 未配置")
    return {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }


def _anthropic_body(parts: dict, model: str, thinking_disabled: bool = False) -> dict:
    """system 字段走 content blocks，把静态前缀挂上 cache_control 触发缓存。
    若 parts 没拆分（如 surface 走 build_surface_messages），降级成单字符串。

    TTL=1h：默认 5min 太短——记忆整理每 ~10min 一次，5min 必过期、永远走
    write penalty (1.25x)。1h TTL 写 2x，但能跨整段会话命中读（0.1x），
    净效果远比 5min TTL 划算。深层若再切回 Sonnet 也吃这一档（连续对话场景
    缓存写一次后就一直读到会话结束）。
    """
    static = parts.get("system_static", "")
    dynamic = parts.get("system_dynamic", "")
    if static:
        system_blocks = [
            {"type": "text", "text": static,
             "cache_control": {"type": "ephemeral", "ttl": "1h"}},
        ]
        if dynamic:
            system_blocks.append({"type": "text", "text": dynamic})
        system = system_blocks
    else:
        system = parts.get("system", "")
    body = {
        "model": model,
        "system": system,
        "messages": [{"role": "user", "content": parts["user_content"]}],
        "max_tokens": 4096,
    }
    # Sonnet 5 起自适应思考默认开；实时深层要显式关（thinking_disabled 来自模型配置），
    # 否则首字延迟从 ~1s 涨到 4s+。思考层等慢通道不带此标记、吃默认自适应思考。
    if thinking_disabled:
        body["thinking"] = {"type": "disabled"}
    return body


def _log_anthropic_usage(usage: dict):
    if not usage:
        return
    inp = usage.get("input_tokens", 0) or 0
    create = usage.get("cache_creation_input_tokens", 0) or 0
    read = usage.get("cache_read_input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    total_in = inp + create + read
    pct = (100 * read // total_in) if total_in else 0
    print(f"[Anthropic cache] input={inp} cache_write={create} cache_read={read} ({pct}% read) output={out}")


def _call_anthropic(parts: dict, model: str, api_key: str = None,
                    thinking_disabled: bool = False) -> str:
    """直连 Anthropic API（非流式）"""
    resp = http_requests.post(
        ANTHROPIC_BASE, headers=_anthropic_headers(api_key),
        json=_anthropic_body(parts, model, thinking_disabled=thinking_disabled),
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    _log_anthropic_usage(data.get("usage"))
    return data["content"][0]["text"]


def _stream_anthropic(parts: dict, model: str, api_key: str = None,
                      thinking_disabled: bool = False):
    """直连 Anthropic API（流式）"""
    body = _anthropic_body(parts, model, thinking_disabled=thinking_disabled)
    body["stream"] = True
    resp = http_requests.post(
        ANTHROPIC_BASE, headers=_anthropic_headers(api_key),
        json=body,
        timeout=60, stream=True,
    )
    resp.raise_for_status()
    resp.encoding = "utf-8"
    usage = {}
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        try:
            event = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        etype = event.get("type")
        if etype == "content_block_delta":
            text = event.get("delta", {}).get("text", "")
            if text:
                yield text
        elif etype == "message_start":
            msg_usage = event.get("message", {}).get("usage", {}) or {}
            usage.update(msg_usage)
        elif etype == "message_delta":
            d = event.get("usage", {}) or {}
            for k, v in d.items():
                if v is not None:
                    usage[k] = v
    _log_anthropic_usage(usage)


def _get_gemini_client():
    """懒加载 Gemini client"""
    global _gemini_client
    if _gemini_client is None:
        if not GEMINI_KEY:
            raise ValueError("GEMINI_API_KEY 未配置")
        _gemini_client = genai.Client(api_key=GEMINI_KEY)
    return _gemini_client


def _gemini_config(parts: dict, model: str = "") -> types.GenerateContentConfig:
    is_pro = "pro" in model.lower()
    if is_pro:
        return types.GenerateContentConfig(
            system_instruction=parts["system"],
        )
    return types.GenerateContentConfig(
        system_instruction=parts["system"],
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )


def _call_gemini(parts: dict, model: str) -> str:
    """直连 Google Gemini API（非流式）"""
    client = _get_gemini_client()
    response = client.models.generate_content(
        model=model,
        config=_gemini_config(parts, model),
        contents=parts["user_content"],
    )
    return response.text


def _stream_gemini(parts: dict, model: str):
    """直连 Google Gemini API（流式）"""
    client = _get_gemini_client()
    for chunk in client.models.generate_content_stream(
        model=model,
        config=_gemini_config(parts, model),
        contents=parts["user_content"],
    ):
        if chunk.text:
            yield chunk.text


@app.route("/")
def index():
    from flask import redirect
    return redirect(os.getenv("AMIKA_CHAT_URL", "http://localhost:52000"))


def _pick_stream(p, cfg, api_key: str = None):
    prov = cfg.get("provider")
    mdl = cfg["model"]
    if prov == "gemini":
        return _stream_gemini(p, mdl)
    if prov == "anthropic":
        return _stream_anthropic(p, mdl, api_key=api_key,
                                 thinking_disabled=cfg.get("thinking_disabled", False))
    if prov in ("xai", "groq"):
        return _stream_openai(p, mdl, prov, no_think=cfg.get("no_think", False),
                              reasoning_effort=cfg.get("reasoning_effort"))
    # 本地 ollama / cerebras 也走 OpenAI 兼容流式（_openai_headers 已支持这两个 base）——
    # ported from an earlier MekaHime build (OURS 7/17) so 质量层下拉选本地/cerebras 不再抛 "不支持的 provider"。
    if prov in ("ollama", "cerebras"):
        return _stream_openai(p, mdl, prov, no_think=cfg.get("no_think", False),
                              reasoning_effort=cfg.get("reasoning_effort"))
    raise ValueError(f"不支持的 provider: {prov}")


@app.route("/api/consolidate", methods=["POST"])
def consolidate_memory():
    """旧版分时段整理记忆已停用：记忆由 F 证据库（f_memory）逐轮写入（记忆1.txt 已移除，R22）。"""
    return jsonify({"error": "Legacy consolidation is disabled; F evidence memory is written per turn."}), 409


# ─── 时段（旧整理系统留下的时段表，场景/时间显示仍在用）──────────────
_PERIOD_RANGES = {
    "凌晨": (1, 5), "清晨": (5, 8), "上午": (8, 12),
    "中午": (12, 14), "下午": (14, 17), "傍晚": (17, 19),
    "晚上": (19, 22), "深夜": (22, 25),
}
_PERIOD_ORDER = ["清晨", "上午", "中午", "下午", "傍晚", "晚上", "深夜", "凌晨"]


def _scene_period() -> str:
    """根据整理进度返回当前应显示的时段场景（最新已整理时段的下一个）。
    无时段记忆时回退到墙钟时段。"""
    sd = _session_date()
    consolidated_periods = set()
    for m in CONSOLIDATED_MEMORIES:
        if m.get("date") == sd and m.get("level") == "period":
            cp = m.get("checkpoint", "")
            if cp.startswith("period_"):
                consolidated_periods.add(cp[7:])

    if not consolidated_periods:
        return _get_period(datetime.now(LOCAL_TZ).hour)

    latest_idx = -1
    for p in consolidated_periods:
        if p in _PERIOD_ORDER:
            idx = _PERIOD_ORDER.index(p)
            if idx > latest_idx:
                latest_idx = idx

    if latest_idx < 0:
        return _get_period(datetime.now(LOCAL_TZ).hour)

    next_idx = latest_idx + 1
    if next_idx >= len(_PERIOD_ORDER):
        return _PERIOD_ORDER[-1]
    return _PERIOD_ORDER[next_idx]




def _run_consolidation(level: str, checkpoint: str,
                       hour: int = None, period_name: str = None,
                       history_override: str = None):
    """旧版分时段整理（记忆1.txt）已移除（R22）；F 证据库逐轮写入取代它。
    这里只保留入口，供仍被 f_bridge 停用的补整理/自动整理代码安全调用。"""
    print(f"[Hane] the old memory consolidation is off: skipped {level} {checkpoint}")
    return False


def _get_turns_for_checkpoint(ck: str) -> list:
    """按整理键（如 '15 3'）获取当前会话的原始轮次"""
    sd = _session_date()
    with _hist_lock:
        return [t for t in CONVERSATION_HISTORY
                if _cp_to_ck(t.get("checkpoint", "")) == ck
                and _session_date_from_ts(t.get("ts", "1970-01-01 12:00:00")) == sd]


def _build_history_from_turns(turns: list) -> str:
    if not turns:
        return ""
    lines = []
    for t in turns:
        sr = t.get("surface_reply", "")
        deep_raw = t.get("deep_raw", "")
        interrupted = t.get("interrupted", False)
        speak_verb = "我准备说" if interrupted else "我说"

        inject_cue = t.get("inject_cue")
        open_cue = t.get("open_cue")
        if inject_cue:
            # 注入指导轮：整理记忆时这条裸括号正常入档（是当时真实发生的情景），下接她的反应。
            lines.append(inject_cue)
        elif open_cue:
            # 开口轮：整理记忆时也只收她说的话，括号提示不入档。
            if not deep_raw and not sr:
                continue
        else:
            lines.append(_render_user_line(t['user']))

        if deep_raw:
            speech, thought = _parsed_deep(deep_raw)
            if sr and speech and sr != speech:
                reply_line = f'我脱口而出："{sr}"\n{speak_verb}："{speech}"'
            elif speech:
                reply_line = f'{speak_verb}："{speech}"'
            elif sr:
                reply_line = f'{speak_verb}："{sr}"'
            else:
                reply_line = ""
            if thought:
                reply_line = (reply_line + "\n" if reply_line else "") + f"我心想：{thought}"
            hint = t.get("think_hint")
            if hint:
                reply_line = (reply_line + "\n" if reply_line else "") + f"我仔细地想了想：{hint}"
            if reply_line:
                lines.append(reply_line)
        elif sr:
            line = f'{speak_verb}："{sr}"'
            hint = t.get("think_hint")
            if hint:
                line += f"\n我仔细地想了想：{hint}"
            lines.append(line)
    return "[之前的对话]\n" + "\n\n".join(lines)


def _build_history_from_memories(checkpoints: list, level: str = "10min") -> str:
    """从已整理的记忆中取出指定检查点和级别的内容，拼成历史（仅当前会话）"""
    sd = _session_date()
    pieces = []
    for m in CONSOLIDATED_MEMORIES:
        if (m.get("checkpoint") in checkpoints and m.get("level") == level
                and m.get("date") == sd):
            pieces.append(m["content"])
    return "\n\n".join(pieces) if pieces else ""


def _mark_cp_done(cp_id: str):
    _COMPLETED_CPS.add(cp_id)



def _hour_consolidated(hour: int) -> bool:
    sd = _session_date()
    return any(
        m.get("checkpoint") == f"{hour} 0" and m.get("level") == "hour"
        and m.get("date") == sd
        for m in CONSOLIDATED_MEMORIES
    )


def _period_consolidated(period_name: str) -> bool:
    sd = _session_date()
    return any(
        m.get("checkpoint") == f"period_{period_name}" and m.get("level") == "period"
        and m.get("date") == sd
        for m in CONSOLIDATED_MEMORIES
    )


def _try_hour_consolidation(hour: int):
    """H 6 完成后调用：补救失败的10min，然后整理小时级，然后检查时段"""
    if f"{hour} 6" not in _COMPLETED_CPS:
        return
    if not _hour_consolidated(hour):
        sd = _session_date()
        cps = [f"{hour} {i}" for i in range(1, 7)]
        for ck in cps:
            has_mem = any(
                m.get("checkpoint") == ck and m.get("level") == "10min"
                and m.get("date") == sd
                for m in CONSOLIDATED_MEMORIES
            )
            if not has_mem:
                turns = _get_turns_for_checkpoint(ck)
                if turns:
                    history = _build_history_from_turns(turns)
                    print(f"[Hane] catching up 10min {ck} before the hourly consolidation")
                    ok = _run_consolidation("10min", ck, history_override=history)
                    if ok:
                        _mark_cp_done(ck)
        has_any = any(
            m.get("checkpoint") in cps and m.get("level") == "10min"
            and m.get("date") == sd
            for m in CONSOLIDATED_MEMORIES
        )
        if has_any:
            history = _build_history_from_memories(cps, level="10min")
            hour_cp = f"{hour} 0"
            print(f"[Hane] chained trigger: hour {hour_cp}")
            _run_consolidation("hour", hour_cp, hour=hour, history_override=history)
    _try_period_consolidation(_get_period(hour))


def _try_period_consolidation(period_name: str):
    """小时整理完成后调用：检查该时段是否就绪，就绪则触发时段整理"""
    if _period_consolidated(period_name):
        return
    rng = _PERIOD_RANGES.get(period_name)
    if not rng:
        return
    start_h, end_h = rng
    last_h = (end_h - 1) % 24
    if f"{last_h} 6" not in _COMPLETED_CPS:
        return
    if end_h > 24:
        hours_in_period = list(range(start_h, 24)) + list(range(0, end_h - 24))
    else:
        hours_in_period = list(range(start_h, end_h))
    sd = _session_date()
    hour_cps = [f"{h} 0" for h in hours_in_period]
    has_any = any(
        m.get("checkpoint") in hour_cps and m.get("level") == "hour"
        and m.get("date") == sd
        for m in CONSOLIDATED_MEMORIES
    )
    if not has_any:
        return
    history = _build_history_from_memories(hour_cps, level="hour")
    period_cp = f"period_{period_name}"
    print(f"[Hane] chained trigger: period {period_name}")
    _run_consolidation("period", period_cp, period_name=period_name,
                       hour=start_h, history_override=history)


def _auto_consolidation_loop():
    """后台线程：只负责10分钟级检查点触发，小时/时段级由完成回调链式触发"""
    last_triggered_cp = None
    _current_session = _session_date()

    while True:
        try:
            now = datetime.now(LOCAL_TZ)
            sd = _session_date(now)

            if sd != _current_session:
                print(f"[Hane] the session date changed {_current_session} → {sd}: checkpoints reset")
                _COMPLETED_CPS.clear()
                last_triggered_cp = None
                _current_session = sd
                _init_current_cp()

            minute = now.minute
            hour = now.hour
            cp_num = minute // 10 + 1
            cp_id = f"{hour} {cp_num}"

            if cp_id != last_triggered_cp:
                if last_triggered_cp is not None:
                    prev_parts = last_triggered_cp.split()
                    from_h, from_cp = int(prev_parts[0]), int(prev_parts[1])
                    _catchup_range(from_h, from_cp, hour, cp_num)

                last_triggered_cp = cp_id

        except Exception as e:
            print(f"[Hane] the auto-consolidation loop failed: {e}")

        _time.sleep(5)


@app.route("/api/models", methods=["GET"])
def get_models():
    models = [
        {"key": k, "name": v["name"], "description": v["description"]}
        for k, v in AVAILABLE_MODELS.items()
    ]
    return jsonify({"models": models})


@app.route("/api/surface_model", methods=["GET", "POST"])
def api_surface_model():
    """表层（快通道）模型运行时切换。GET 读当前+可选项；POST {model} 切换（正常对话轮即时生效）。"""
    global DEFAULT_SURFACE_MODEL
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        m = (data.get("model") or "").strip()
        if m not in AVAILABLE_MODELS:
            return jsonify({"ok": False, "error": f"未知模型: {m}"}), 400
        DEFAULT_SURFACE_MODEL = m
        _save_model_prefs()
    options = [{"key": k, "name": AVAILABLE_MODELS[k].get("name", k),
                "description": AVAILABLE_MODELS[k].get("description", "")}
               for k in SURFACE_MODEL_KEYS if k in AVAILABLE_MODELS]
    return jsonify({"ok": True, "current": DEFAULT_SURFACE_MODEL, "options": options})


@app.route("/api/deep_model", methods=["GET", "POST"])
def api_deep_model():
    """深层（写台词的质量层）模型运行时切换。GET 读当前+可选项；POST {model} 切换（下一轮即时生效）。"""
    global DEFAULT_DEEP_MODEL
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        m = (data.get("model") or "").strip()
        if m not in AVAILABLE_MODELS:
            return jsonify({"ok": False, "error": f"未知模型: {m}"}), 400
        DEFAULT_DEEP_MODEL = m
        _save_model_prefs()
    options = [{"key": k, "name": AVAILABLE_MODELS[k].get("name", k),
                "description": AVAILABLE_MODELS[k].get("description", "")}
               for k in DEEP_MODEL_KEYS if k in AVAILABLE_MODELS]
    return jsonify({"ok": True, "current": DEFAULT_DEEP_MODEL, "options": options})


@app.route("/api/thinking_model", methods=["GET", "POST"])
def api_thinking_model():
    """思考层（反思/指导层）模型运行时切换。GET 读当前+可选项；POST {model} 切换（下次思考即时生效）。"""
    global DEFAULT_THINKING_MODEL
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        m = (data.get("model") or "").strip()
        if m not in AVAILABLE_MODELS:
            return jsonify({"ok": False, "error": f"未知模型: {m}"}), 400
        DEFAULT_THINKING_MODEL = m
        _save_model_prefs()
    options = [{"key": k, "name": AVAILABLE_MODELS[k].get("name", k),
                "description": AVAILABLE_MODELS[k].get("description", "")}
               for k in THINKING_MODEL_KEYS if k in AVAILABLE_MODELS]
    return jsonify({"ok": True, "current": DEFAULT_THINKING_MODEL, "options": options})


@app.route("/api/reload", methods=["POST"])
def reload():
    """重新加载模板（编辑 txt 后刷新用），并重跑模板自检（R2）。"""
    try:
        reload_template()
        reload_surface_template()
        reload_thinking_template()
        check = run_template_check()
        return jsonify({"ok": True, "deep_length": len(_template_cache),
                        "surface_length": len(_surface_template_cache),
                        "thinking_length": len(_thinking_template_cache),
                        "template_check": check})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/template", methods=["GET"])
def get_template():
    """预览当前系统提示词（调试用）"""
    try:
        parts = build_messages("（测试消息）")
        return jsonify({
            "file": TEMPLATE_FILE,
            "template_length": len(load_template()),
            "system_length": len(parts["system"]),
            "user_content_length": len(parts["user_content"]),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/relationship_stage", methods=["GET"])
def get_relationship_stage():
    scenes = _load_scenes()
    stages = scenes["deep"]["static"].get("relationship_stages", [])
    return jsonify({
        "current": _RELATIONSHIP_STAGE,
        "stages": [{"index": i, "name": s["name"]} for i, s in enumerate(stages)],
    })


@app.route("/api/relationship_stage", methods=["POST"])
def set_relationship_stage():
    global _RELATIONSHIP_STAGE
    data = request.get_json(force=True)
    idx = data.get("stage", 0)
    scenes = _load_scenes()
    stages = scenes["deep"]["static"].get("relationship_stages", [])
    if not (0 <= idx < len(stages)):
        return jsonify({"error": f"阶段索引 {idx} 超出范围 0-{len(stages)-1}"}), 400
    _RELATIONSHIP_STAGE = idx
    print(f"[Hane] relationship stage → {stages[idx]['name']}")
    return jsonify({"current": _RELATIONSHIP_STAGE, "name": stages[idx]["name"]})


@app.route("/api/clear_memory", methods=["POST"])
def clear_memory():
    with _hist_lock, _cp_lock:
        CONVERSATION_HISTORY.clear()
        CONSOLIDATED_MEMORIES.clear()
        _COMPLETED_CPS.clear()
        _save_history()
        _save_consolidated()
    with _think_lock:
        THINKING_LOG.clear()
        _save_thinking_log()
    _init_current_cp()
    print("[Hane] memory wiped")
    return jsonify({"status": "ok"})


@app.route("/api/think", methods=["POST"])
def api_think():
    """手动跑一次思考层（调试用）。可选 body: {deep_request: "..."}"""
    data = request.get_json(silent=True) or {}
    deep_request = (data.get("deep_request") or "").strip()
    try:
        entry = run_thinking_once(deep_request)
        return jsonify({"status": "ok", "entry": entry})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


# ─── WebSocket 推测执行系统 ──────────────────────────────────
#
# 前端协议（极简 + 对称）：
#   ← client "message"   {text, turn_id?, my_partial?}
#       处理：
#         1. 若 my_partial 非空，说明这是一次打断产生的消息：
#            - 找到最近的 protected turn（上一轮被打断的那轮）；
#              如果它还在跑生成就取消并保存 partial；
#              首次进入打断状态时给它打 interrupted=true。
#            - 把 user 字段合成为（INTERRUPT_MARKER 开头的内部格式）
#              'When I was saying "{my_partial}", they cut in: "{text}"'
#              （my_partial 只需是打断瞬间的最后几个字，用来定位打断点；
#               完整已播出内容已由上一轮 turn 的 surface_partial / deep_partial 保留）
#            否则 user 字段就是 text 本身。
#         2. 从历史末尾删掉所有未保护的 turn（顺便取消它们在跑的生成）。
#         3. 用干净原话 text 算本轮回话语种 reply_lang（B6/B7），新建一条 User turn（未保护），开流式生成。
#       模型搭配后端固定（DEFAULT_SURFACE_MODEL / DEFAULT_DEEP_MODEL），前端不选。
#   ← client "protect"   {}
#       处理：TTS 开播后前端调用，给最近的 turn 打 protected=True。
#
# → server 事件（按时序；每条都带 turn_id，客户端可据此绑 UI）：
#   begin          {turn_id, proactive, continuation, reply_lang, reply_lang_reason}  ── 一次新生成的开始
#   surface_chunk  {turn_id, text}
#   surface_done   {turn_id, mode, reply, tone, status, raw, reply_lang, reply_lang_reason}
#   deep_chunk     {turn_id, text}                        ── 可选
#   deep_done      {turn_id, speech, thought, segments, raw}  ── 可选；segments = [{text, tone}]
#   error          {turn_id, message}                     ── 出错；后端会紧跟一个 end
#   end            {turn_id}                              ── 正常结束 或 出错后
#                  被前端取消（无下一条消息/无 protect）时不会发 end —— 取消源自前端，自己知道
#
# turn_id：客户端提供就复用，未提供时后端自动 uuid4。既作内部取消流水线索引，
#         也作事件关联 ID 回传。

_ws_active_lock = threading.Lock()
_ws_active: dict = {}  # turn_id → {"cancel": threading.Event, "reason": str | None}
# 最近活跃客户端 sid：开口（主动发声）需要知道把这一轮推给谁。连接/发消息时更新。
_LAST_SID: str | None = None

# ── 空闲节奏：对方一段时间没接话，就借「深层→思考层」通道戳一下，让思考层决定
#    是直接开口续话、还是铺个新话题再开口；结果照常走思考层的「开口」快通道。
IDLE_TRIGGER_SECONDS = 30
# 预算保护：对方一直不接话时，最多连续主动开口这么多轮，之后等对方先说话再恢复空闲节奏
# （否则挂着的网页会每三十来秒自问自答一轮，一直计费）。
IDLE_MAX_UNANSWERED_OPENS = 2
_last_activity_ts = _time.monotonic()
_idle_fired = False            # 本段静默是否已触发过（避免反复触发）
_idle_state_lock = threading.Lock()
# 这句以她自己的口吻写，贴合思考层「她现在来找你」那一段的第一人称语气。
IDLE_DEEP_REQUEST = (
    "（已经三十秒左右没人接话了，有点冷场——我是该直接开口、接着刚才的话头说点什么，"
    "还是干脆铺一个新话题、主动开口带一下节奏？你帮我定一下，然后让我开口。）"
)


def _mark_activity():
    """有活动（对方说话 / 她说完一轮）就重置静默计时，解除本段触发锁。"""
    global _last_activity_ts, _idle_fired
    with _idle_state_lock:
        _last_activity_ts = _time.monotonic()
        _idle_fired = False


def _idle_check_and_arm() -> bool:
    """到了该触发空闲节奏吗？到了就置 _idle_fired（本段只触发一次）并返回 True。
    条件：有活跃客户端、当前没有生成在跑、静默已超阈值、本段还没触发过。"""
    global _idle_fired
    if not _LAST_SID:
        return False
    with _ws_active_lock:
        if _ws_active:                  # 她正在说 / 正在生成，不算静默
            return False
    with _hist_lock:
        unanswered = 0
        for t in reversed(CONVERSATION_HISTORY):
            if not t.get("open_cue"):
                break
            unanswered += 1
    if unanswered >= IDLE_MAX_UNANSWERED_OPENS:
        return False
    with _idle_state_lock:
        idle = _time.monotonic() - _last_activity_ts
        if idle < IDLE_TRIGGER_SECONDS or _idle_fired:
            return False
        _idle_fired = True
        return True


def _idle_watch_loop():
    """后台节奏：对方 IDLE_TRIGGER_SECONDS 没接话，就借深层通道戳一下思考层。"""
    while True:
        _time.sleep(3)
        try:
            if _idle_check_and_arm():
                if trigger_thinking_async(
                    deep_request=IDLE_DEEP_REQUEST,
                    reason=f"空闲{IDLE_TRIGGER_SECONDS}秒",
                    set_pending=False,  # 不是她的【想想】，别污染下一轮「我心想」
                ):
                    print(f"[Hane] quiet for {IDLE_TRIGGER_SECONDS} s: asked the reflection whether she speaks first")
        except Exception as e:
            print(f"[Hane] the quiet watch failed: {e}")


def _cancel_turn_gen(turn_id: str, reason: str) -> bool:
    with _ws_active_lock:
        entry = _ws_active.get(turn_id)
    if entry:
        entry["reason"] = reason
        entry["cancel"].set()
        return True
    return False


def _prune_unprotected():
    """从历史末尾开始 pop，直到遇到 protected=True 的 turn。
    对每条被删的 turn，若有在跑生成则标记 discard 取消。"""
    removed_ids = []
    with _hist_lock:
        while CONVERSATION_HISTORY:
            t = CONVERSATION_HISTORY[-1]
            if t.get("protected"):
                break
            removed_ids.append(t.get("turn_id"))
            CONVERSATION_HISTORY.pop()
    if removed_ids:
        _save_history()
    for tid in removed_ids:
        if tid:
            _cancel_turn_gen(tid, "discard")
    if removed_ids:
        print(f"[Hane] cleared {len(removed_ids)} unprotected turn(s)")
    return len(removed_ids)


def _protect_latest() -> bool:
    """把最近一条 turn 标为 protected。"""
    with _hist_lock:
        if not CONVERSATION_HISTORY:
            return False
        t = CONVERSATION_HISTORY[-1]
        if t.get("protected"):
            return True
        t["protected"] = True
        tid = t.get("turn_id")
        has_pending = bool(t.get("pending_think"))
    _save_history()
    print(f"[Hane] protected turn {tid}")
    # 这一轮深层喊过【想想】但当时没起思考层（等保护）：现在受保护了，触发慢通道。
    if has_pending:
        _fire_pending_think(tid)
    return True


def _with_round_context(parts: dict, context: str) -> dict:
    """本轮附加上下文（基准测试/外部注入的 context）。插在对话历史之后、{pending_mind} 之前，
    让 {language_line} 始终是 prompt 的最后一行；找不到历史锚点（如表层没有历史）时退回追加到末尾。"""
    if not context:
        return parts
    parts = dict(parts)
    block = "\n\n[Context supplied for this turn]\n" + context + "\n[/Context]"
    dynamic = parts.get("system_dynamic")
    anchor = parts.get("_history_text") or ""
    if dynamic is not None and anchor:
        idx = dynamic.rfind(anchor)
        if idx != -1:
            cut = idx + len(anchor)
            parts["system_dynamic"] = dynamic[:cut] + block + dynamic[cut:]
            parts["system"] = parts.get("system_static", "") + parts["system_dynamic"]
            return parts
    parts["system"] = parts.get("system", "") + block + "\n"
    if "system_dynamic" in parts:
        parts["system_dynamic"] += block + "\n"
    return parts


def _with_capabilities(parts: dict, voice: str = "self") -> dict:
    """[你手边的工具]（f_tools.capability_block）：启用的工具/代办 agent 清单，插在对话历史之前，
    让她每一轮都知道自己能做什么、规矩是什么。工具层关着或没启用任何服务器时原样返回。
    voice="third" 给思考层（它是旁观她的那一层）：[她手边的工具]，同样写明哪个帮手联系不上、
    眼下有没有事在办——否则它会替她编出"查到了"的开口内容。"""
    builder = globals().get("F_TOOLS_CAPABILITIES")
    if builder is None:
        return parts
    try:
        block = builder(voice) if voice != "self" else builder()
    except Exception as error:
        print(f"[tools] capability block skipped: {error}")
        return parts
    if not block:
        return parts
    parts = dict(parts)
    dynamic = parts.get("system_dynamic")
    anchor = parts.get("_history_text") or ""
    if dynamic is not None and anchor:
        idx = dynamic.rfind(anchor)
        if idx != -1:
            parts["system_dynamic"] = dynamic[:idx] + block + "\n\n" + dynamic[idx:]
            parts["system"] = parts.get("system_static", "") + parts["system_dynamic"]
            return parts
    text = "\n\n" + block + "\n"
    parts["system"] = parts.get("system", "") + text
    if "system_dynamic" in parts:
        parts["system_dynamic"] += text
    return parts


def _last_user_turn(exclude_turn_id: str = None, within_s: float = 600):
    """他最近一次说的话（有 user 文本的那一轮；开口轮/注入轮没有）。超过 within_s 秒就算过期（None）。"""
    now = datetime.now(LOCAL_TZ).replace(tzinfo=None)
    with _hist_lock:
        for t in reversed(CONVERSATION_HISTORY):
            if t.get("turn_id") == exclude_turn_id:
                continue
            text = (t.get("f_user_text") or t.get("user") or "").strip()
            if not text:
                continue
            try:
                age = (now - datetime.strptime(str(t.get("ts")), "%Y-%m-%d %H:%M:%S")).total_seconds()
            except (TypeError, ValueError):
                age = None
            if age is not None and age > within_s:
                return None
            return {"turn_id": t.get("turn_id"), "text": text, "reply_lang": t.get("reply_lang")}
    return None


def _tools_after_turn(turn_id: str, user_text: str, surface_reply: str, deep_parsed: dict | None,
                      proactive_cue, reply_lang=None, entry: dict | None = None) -> None:
    """说完之后才轮到工具（f_tools.after_turn）：书记员读对方的话和她说出口的话，只把她答应了的事交办出去。
    用户轮：对照他这轮说的话。开口轮（思考层让她主动开口）：她可能这时才答应他上一轮提的要求
    （"好啦，我让赫尔墨斯去查"），所以也过一遍书记员——但引用来源仍只能是他自己最近（10 分钟内）说的话，
    每条请求最多交办一次，且不从开口轮取任何批准/回答。注入轮（工具转述、提示）不跑——她不能自作主张。
    任何异常都不许影响本轮。"""
    hook = globals().get("F_TOOLS_AFTER_TURN")
    if hook is None:
        return
    source_turn_id = None
    if proactive_cue:
        if not (entry or {}).get("open_cue"):
            return
        last = _last_user_turn(exclude_turn_id=turn_id)
        if last is None:
            return
        user_text, source_turn_id = last["text"], last["turn_id"]
        reply_lang = reply_lang or last.get("reply_lang")
    if not (user_text or "").strip():
        return
    spoken = " ".join(s for s in (surface_reply or "", (deep_parsed or {}).get("speech") or "") if s).strip()
    thought = (deep_parsed or {}).get("thought") or ""
    try:
        hook(turn_id, user_text, spoken, thought, reply_lang, source_turn_id)
    except Exception as error:
        print(f"[tools] after-turn hook failed: {error}")


def _prev_reply_lang(exclude_turn_id: str = None):
    """B7：上一轮（已受保护）的回话语种，给太短/听不出语种的这一轮沿用。
    跳过「明确要求换语种」（switch）的那一轮——换语种只管一轮。
    旧记录没有 reply_lang 时，按那一轮的原话现判一次。"""
    with _hist_lock:
        for t in reversed(CONVERSATION_HISTORY):
            if t.get("turn_id") == exclude_turn_id or not t.get("protected"):
                continue
            if t.get("reply_lang_reason") == "switch":
                continue
            lang = t.get("reply_lang")
            if lang is None and "reply_lang_reason" not in t and t.get("f_user_text"):
                lang = po_contract.detect_lang(t["f_user_text"])
            if lang in ("zh", "en", "ja"):
                return lang
    return None


def _inherited_reply_lang() -> tuple:
    """开口/注入轮没有对方的话可判断：沿用上一轮的语种。"""
    prev = _prev_reply_lang()
    return (prev, "inherited") if prev else (None, "unknown")


def _describe_provider_error(error):
    """What the model provider said about a failed turn, first line only (f_openrouter.describe_error), or None."""
    try:
        from f_openrouter import describe_error
        return describe_error(error)
    except Exception:
        return None


def _ws_run_generation(sid: str, turn_id: str, text: str,
                       model_key: str, deep_model_key: str,
                       entry: dict):
    """后台线程：跑完整的 surface → deep 流水线，流式推送给前端。"""
    cancel = entry["cancel"]

    def _emit(event, data=None):
        payload = dict(data) if data else {}
        payload["turn_id"] = turn_id
        socketio.emit(event, payload, to=sid)

    surface_full = ""
    deep_full = ""
    surface_reply_saved = ""
    # 开口轮 / 注入指导轮：都跳过表层、深层直接顺着历史末尾那句括号反应。
    open_cue = entry.get("open_cue")
    proactive_cue = open_cue or entry.get("inject_cue")
    # B6/B7：本轮回话语种在建轮时算好（_start_*_gen），这里只读。
    with _hist_lock:
        _turn = _find_turn(turn_id) or {}
        reply_lang = _turn.get("reply_lang")
        reply_lang_reason = _turn.get("reply_lang_reason") or "unknown"
        lang_text = _turn.get("f_user_text")

    def _handle_cancel():
        reason = entry.get("reason") or "discard"
        if reason == "discard":
            discard_turn(turn_id)  # 找不到就是已被 _prune 删掉，无伤
        else:
            # interrupt：保留 partial + protected + interrupted
            partial_sr = surface_reply_saved
            if not surface_reply_saved and surface_full:
                partial_sr = parse_surface_response(surface_full)[0]["speech"]
            mark_turn_interrupted(
                turn_id,
                surface_partial=partial_sr,
                deep_partial=deep_full,
            )
            with _hist_lock:
                t = _find_turn(turn_id)
                if t is not None:
                    t["protected"] = True
            _save_history()

    def _run_deep(deep_parts: dict, blurt, help_reason: str) -> bool:
        """流式跑深层：deep_chunk → deep_done（带 segments）→ 入历史 → 【想想】暂存。
        被取消返回 False（调用方负责 _handle_cancel）。"""
        nonlocal deep_full
        # 工具层（f_tools）不再在深层之前跑任何东西：她先说话，说完之后书记员再交办（_tools_after_turn）。
        # 这里只把 [你手边的工具] 清单插进 prompt，让她知道自己能做什么。
        round_context = entry.get("context", "")
        # xAI 缓存按 server 分片，conv_id 让同一会话落到同一 server
        deep_parts = _with_round_context(deep_parts, round_context)
        deep_parts = _with_capabilities(deep_parts)
        deep_parts["conv_id"] = sid
        for chunk in _pick_stream(deep_parts, deep_model_config):
            if cancel.is_set():
                return False
            deep_full += chunk
            _emit("deep_chunk", {"text": chunk})
        if cancel.is_set():
            return False
        deep = parse_response(deep_full, blurt=blurt)[0]
        entry["deep_parsed"] = deep   # 给说完之后的书记员（_tools_after_turn）看她说出口的话
        _emit("deep_done", {
            "speech": deep["speech"],
            "thought": deep["thought"],
            "segments": deep["segments"],
            "raw": deep_full,
        })
        update_turn_deep(turn_id, deep_full)
        # 深层在「我心想」里缀【想想】举手 → 慢通道：不立刻起思考层，先把请求暂存到
        # 「这一轮」，等这一轮受保护（TTS 首音频 / 网页 end）后再触发，确保目标轮还在
        # 历史里，思考层产物（提示/计划/开口）一定能挂回本轮、随历史在后续轮喂回深层。
        if deep["needs_help"]:
            _stash_pending_think(turn_id, deep_request=deep["thought"] or deep["speech"],
                                 reason=help_reason)
        return True

    try:
        if model_key not in AVAILABLE_MODELS:
            _emit("error", {"message": f"未知模型: {model_key}"})
            discard_turn(turn_id)
            _emit("end")
            return

        model_config = AVAILABLE_MODELS[model_key]
        deep_model_config = AVAILABLE_MODELS.get(deep_model_key, model_config)

        # proactive=True 让发声端（STT）识别这是服务端主动发起的轮次：
        # 它没为这轮发过 message，turn_id 对不上 committed/current，需靠这个标记
        # 主动「认领」本轮，否则 begin/deep_chunk/deep_done 会被当 stale 丢弃、没声音。
        # reply_lang：这一轮她说出口的话应该用的语种（发声端用来给 MIXED/纯汉字句子定 TTS 语言）。
        begin_payload = {"proactive": bool(proactive_cue),
                         "continuation": bool(entry.get("continuation")),
                         "reply_lang": reply_lang,
                         "reply_lang_reason": reply_lang_reason}
        # TELEMETRY_SPEC §1.1：思考层开口起的这一轮，begin 带上 origin（哪条思考层调用促成的）。
        if entry.get("origin"):
            begin_payload["origin"] = entry["origin"]
        _emit("begin", begin_payload)

        # ── 开口轮 / 注入指导轮：跳过表层，深层直接顺着历史末尾那句括号反应 ──
        # 历史末尾已带那句括号（build_deep_history 渲染），深层顺着它说话/思考即可。
        if proactive_cue:
            deep_parts = build_messages("", reply_lang=reply_lang, reply_lang_reason=reply_lang_reason)
            if not _run_deep(deep_parts, None, "开口轮深层【想想】"):
                _handle_cancel()
                return
            f_mark_complete(turn_id)
            _emit("end")
            # 开口轮说完也过一遍书记员：她可能这时才答应他上一轮的要求（引用来源仍是他自己的话；注入轮不跑）。
            _tools_after_turn(turn_id, "", None, entry.get("deep_parsed"), proactive_cue, reply_lang, entry)
            return

        # ── 表层 ──
        parts = build_surface_messages(text, lang_text=lang_text)
        parts = _with_round_context(parts, entry.get("context", ""))
        parts = _with_capabilities(parts)
        parts["conv_id"] = sid   # xAI 缓存：surface 也 pin 到同一 server 命中前缀缓存（非 xai provider 忽略）
        # 表层和深层一样走 _pick_stream：f_roles 把 OpenRouter / Ollama / Alibaba 的角色模型交给各自的 transport。
        # A surface on Ollama must not call _stream_openai directly: f_bridge's metered stream takes only anthropic /
        # xai, so every Fully Local turn failed before any model call ("Build F supports its configured …").
        _surface_stream = _pick_stream(parts, model_config)
        for chunk in _surface_stream:
            if cancel.is_set():
                _handle_cancel()
                return
            surface_full += chunk
            _emit("surface_chunk", {"text": chunk})

        if cancel.is_set():
            _handle_cancel()
            return

        sf = _extract_surface_fields(surface_full)
        surface_mode = sf["mode"]
        surface_reply_saved = sf["reply"]
        with _hist_lock:
            current = _find_turn(turn_id)
            if current is not None:
                current["f_surface_mode"] = surface_mode

        # C15：没有 recall。status 只作参考（C18），不拦生成。
        _emit("surface_done", {
            "mode": surface_mode,
            "reply": surface_reply_saved,
            "tone": sf["tone"],
            "status": sf["status"],
            "raw": surface_full,
            "reply_lang": reply_lang,
            "reply_lang_reason": reply_lang_reason,
        })

        update_turn_surface(turn_id, surface_reply_saved, sf["status"], sf["tone"])

        # ── 深层（如需要）──
        # C14：think 模式带了垫话（"我想想……"）时，垫话同样已经说出口，
        # 和 say+think 一样作为「脱口而出」交给深层，深层接着说、不再重复。
        if surface_mode in ("say+think", "think"):
            # P2: a speculative turn waits for the speech server's commit before the deep starts.
            if not _await_commit(entry, cancel):
                _handle_cancel()
                return
            blurt = surface_reply_saved or None
            deep_parts = build_messages(text, blurted_reply=blurt, reply_lang=reply_lang,
                                        reply_lang_reason=reply_lang_reason)
            if not _run_deep(deep_parts, blurt, "深层【想想】"):
                _handle_cancel()
                return

        f_mark_complete(turn_id)
        _emit("end")
        # 说完了才轮到工具：书记员只把她刚答应了的事交办出去（开口轮不跑）。
        _tools_after_turn(turn_id, lang_text or text, surface_reply_saved, entry.get("deep_parsed"),
                          proactive_cue, reply_lang)

    except Exception as e:
        if cancel.is_set():
            _handle_cancel()
        else:
            # the provider's own first line ("OpenRouter (HTTP 402): Insufficient credits …") when it said one; the
            # page shows it in the chat log, a Discord / Telegram reply carries it as her system line
            detail = _describe_provider_error(e)
            _emit("error", {"message": detail or str(e), "provider": bool(detail)})
            discard_turn(turn_id)
            _emit("end")
    finally:
        with _ws_active_lock:
            _ws_active.pop(turn_id, None)
        # 一轮生成收尾（含她主动开口）→ 重置静默计时，从此刻开始数"对方没接话"。
        _mark_activity()


def _handle_first_interrupt_if_needed() -> None:
    """打断后第一条消息到达时调用。
    找到最近的 protected turn（上一轮被打断的那轮），同步标记 interrupted；
    若它的生成还在跑，给它发 interrupt 取消，后台线程会把 partial 存下来。
    再次调用时（同一打断状态下的后续短停顿消息）会因为 interrupted 已置而直接跳过。
    """
    with _hist_lock:
        prot = None
        for t in reversed(CONVERSATION_HISTORY):
            if t.get("protected"):
                prot = t
                break
        if prot is None or prot.get("interrupted"):
            return
        prot["interrupted"] = True
        prot_turn_id = prot.get("turn_id")
    _save_history()

    if prot_turn_id:
        # 若还在跑 → 后台线程会以 interrupt 分支保 partial
        # 若已结束 → no-op
        _cancel_turn_gen(prot_turn_id, "interrupt")


# P2 (reports/cache_proposals.md, approved 2026-10-01): a speculative turn (sent by the speech server on a
# micro-pause, before the utterance is final) runs its surface at once but starts the deep only after the
# speech server's "commit" for that turn id, so a superseded partial never starts a deep call. f_bridge
# installs both values from build_f.json (deep_waits_for_commit, speculative_deep_wait_s).
DEEP_WAITS_FOR_COMMIT = True
SPECULATIVE_DEEP_WAIT_S = 2.0


def _mark_committed(turn_id: str) -> bool:
    """Speech-server commit for a (speculative) turn still in flight: release its deep."""
    with _ws_active_lock:
        entry = _ws_active.get(turn_id)
    if not entry:
        return False
    event = entry.get("committed")
    if event is not None:
        event.set()
    return True


def _await_commit(entry: dict, cancel, poll: float = 0.05) -> bool:
    """Before the deep: True = go ahead (committed, not speculative, waiting disabled, or waited out);
    False = the turn was cancelled meanwhile (a newer partial superseded it)."""
    if not entry.get("speculative") or not DEEP_WAITS_FOR_COMMIT:
        return not cancel.is_set()
    event = entry.get("committed")
    budget = max(0.0, float(SPECULATIVE_DEEP_WAIT_S or 0))
    deadline = _time.monotonic() + budget
    while True:
        if cancel.is_set():
            return False
        if event is not None and event.is_set():
            return True
        remaining = deadline - _time.monotonic()
        if remaining <= 0:
            print(f"[Hane] speculative turn not committed within {budget:.1f}s; starting the deep anyway")
            return True
        if event is not None:
            event.wait(min(poll, remaining))
        else:
            _time.sleep(min(poll, remaining))


def _start_message_gen(sid: str, text: str, my_partial: str,
                       model_key: str, deep_model_key: str,
                       turn_id: str | None = None, context: str = "", speculative: bool = False):
    """处理 my_partial（如有）→ 清未保护 turn → 新建 User turn → 开生成。

    turn_id 若由客户端提供则复用作为内部 id；未提供时后端生成一个 UUID。
    """
    if my_partial:
        _handle_first_interrupt_if_needed()
        user_field = INTERRUPT_MARKER + f'When I was saying "{my_partial}", they cut in: "{text}"'
    else:
        user_field = text

    _prune_unprotected()
    # B6/B7：这一轮她说出口的话用什么语种。用干净原话判断（打断包装之前）；太短/没字母/
    # 混合就沿用上一轮；明确要求换语种（switch）只管这一轮。
    reply_lang, reply_lang_reason = po_contract.reply_lang(text, _prev_reply_lang())
    turn_id = turn_id or str(uuid.uuid4())
    turn = create_turn(turn_id, user_field)
    with _hist_lock:
        turn["f_user_text"] = text
        turn["reply_lang"] = reply_lang
        turn["reply_lang_reason"] = reply_lang_reason
        if context:
            turn["context_inject"] = context
    _save_history()
    entry = {"cancel": threading.Event(), "reason": None, "sid": sid, "context": context,
             "speculative": bool(speculative), "committed": threading.Event()}
    if not speculative:
        entry["committed"].set()
    with _ws_active_lock:
        _ws_active[turn_id] = entry
    socketio.start_background_task(
        _ws_run_generation, sid, turn_id, user_field,
        model_key, deep_model_key, entry,
    )


def _start_open_gen(sid: str, cue: str,
                    model_key: str = None,
                    deep_model_key: str = None,
                    turn_id: str | None = None,
                    origin: dict | None = None) -> str | None:
    """开口（思考层第三种指导，B12）：建一个开口轮，跳过表层让深层主动发声。

    cue 是第一人称括号提示（如「（我现在先说…再说…）」），只喂这一轮的 prompt、
    不进历史；她说出口的话照常入历史（并作为 cue=开口提示、user="" 的事件存进 F 记忆），
    被打断也照常记「我准备说」（自然复用打断那套）。语种沿用上一轮。
    origin：由思考层开口时 f_bridge 传入 {kind: "reflection", receipt_turn_id, receipt_started_ms, …}，
    原样放进这一轮的 begin（TELEMETRY_SPEC §1.1，发声端据此把思考层那条耗时接在这一轮前面）。
    """
    if not cue or not cue.strip():
        return None
    cue = cue.strip()
    model_key = model_key or DEFAULT_SURFACE_MODEL
    deep_model_key = deep_model_key or DEFAULT_DEEP_MODEL
    _prune_unprotected()
    reply_lang, reply_lang_reason = _inherited_reply_lang()
    turn_id = turn_id or str(uuid.uuid4())
    turn = create_turn(turn_id, "")
    with _hist_lock:
        turn["open_cue"] = cue
        turn["reply_lang"] = reply_lang
        turn["reply_lang_reason"] = reply_lang_reason
    _save_history()
    entry = {"cancel": threading.Event(), "reason": None,
             "sid": sid, "open_cue": cue}
    if origin:
        entry["origin"] = dict(origin)
    with _ws_active_lock:
        _ws_active[turn_id] = entry
    socketio.start_background_task(
        _ws_run_generation, sid, turn_id, "",
        model_key, deep_model_key, entry,
    )
    return turn_id


CONTINUE_CUE = "(Keep going — just naturally pick up and say the bit I decided a moment ago I still wanted to add.)"


def _start_continue_gen(sid: str,
                        model_key: str = None,
                        deep_model_key: str = None,
                        turn_id: str | None = None) -> str | None:
    """自续说轮（【接着说】）：本版停用（CONTINUE_ENABLED=False，f_bridge 把它换成空操作）。
    保留入口：以「裸括号消息」(CONTINUE_CUE) 起一轮主动轮（建轮、跳表层、深层顺着历史末尾
    那句括号自己接着说）。"""
    model_key = model_key or DEFAULT_SURFACE_MODEL
    deep_model_key = deep_model_key or DEFAULT_DEEP_MODEL
    _prune_unprotected()
    reply_lang, reply_lang_reason = _inherited_reply_lang()
    turn_id = turn_id or str(uuid.uuid4())
    turn = create_turn(turn_id, "")
    with _hist_lock:
        turn["inject_cue"] = CONTINUE_CUE
        turn["reply_lang"] = reply_lang
        turn["reply_lang_reason"] = reply_lang_reason
    _save_history()
    entry = {"cancel": threading.Event(), "reason": None,
             "sid": sid, "inject_cue": CONTINUE_CUE, "continuation": True}
    with _ws_active_lock:
        _ws_active[turn_id] = entry
    socketio.start_background_task(
        _ws_run_generation, sid, turn_id, "",
        model_key, deep_model_key, entry,
    )
    return turn_id


def _start_inject_gen(sid: str, note: str,
                      model_key: str = None,
                      deep_model_key: str = None,
                      turn_id: str | None = None, context: str = "",
                      reply_lang: str | None = None) -> str | None:
    """手动注入指导轮：和开口同一套机制（建轮、跳表层、深层立刻反应），
    区别是这句无前缀裸括号会正常留在历史里（不像开口 cue 那样用完即弃）。

    note 例：（你看到弹幕里写了…这个梗似乎和…有关。你在考虑回复哪些，准备直接开口还是先想一想）
    没带括号就自动补一对。她顺着它说话/思考；说出口的话照常入历史，被打断照常记。语种沿用上一轮。
    """
    if not note or not note.strip():
        return None
    note = note.strip()
    if not (note.startswith("（") or note.startswith("(")):
        note = f"（{note}）"
    model_key = model_key or DEFAULT_SURFACE_MODEL
    deep_model_key = deep_model_key or DEFAULT_DEEP_MODEL
    _prune_unprotected()
    # 工具层的转述轮带着对方提出请求那一轮的语种（reply_lang），其余注入轮照旧沿用上一轮。
    if reply_lang in ("zh", "en", "ja"):
        reply_lang_reason = "tools"
    else:
        reply_lang, reply_lang_reason = _inherited_reply_lang()
    turn_id = turn_id or str(uuid.uuid4())
    turn = create_turn(turn_id, "")
    with _hist_lock:
        turn["inject_cue"] = note
        turn["reply_lang"] = reply_lang
        turn["reply_lang_reason"] = reply_lang_reason
        if context:
            turn["context_inject"] = context
    _save_history()
    entry = {"cancel": threading.Event(), "reason": None,
             "sid": sid, "inject_cue": note, "context": context}
    with _ws_active_lock:
        _ws_active[turn_id] = entry
    socketio.start_background_task(
        _ws_run_generation, sid, turn_id, "",
        model_key, deep_model_key, entry,
    )
    return turn_id


@socketio.on("connect")
def ws_connect():
    global _LAST_SID
    _LAST_SID = request.sid
    _mark_activity()
    print(f"[Hane WS] page connected: {request.sid}")


@socketio.on("disconnect")
def ws_disconnect():
    global _LAST_SID
    sid = request.sid
    if _LAST_SID == sid:
        _LAST_SID = None
    # TELEMETRY_SPEC §1.1：之后迟到的 call_receipt（记忆写入、drain）改发给当前连接，不发给已断开的 sid
    telemetry = globals().get("F_TELEMETRY")
    if telemetry is not None:
        try:
            telemetry.forget_sid(sid)
        except Exception:
            pass
    print(f"[Hane WS] page disconnected: {sid}")
    with _ws_active_lock:
        # 只取消本 sid 的生成；entry 由后台线程 finally 段自己从表里 pop
        for entry in _ws_active.values():
            if entry.get("sid") == sid:
                entry["reason"] = entry.get("reason") or "discard"
                entry["cancel"].set()


@socketio.on("message")
def ws_message(data):
    global _LAST_SID, _CURRENT_CHANNEL
    sid = request.sid
    _LAST_SID = sid
    _mark_activity()
    data = data or {}
    # 舞台（语音/打字）不带 channel → 他在家；messengers 带 "discord"/"telegram" → 她在手机上看文字
    _CURRENT_CHANNEL = str(data.get("channel") or "").strip().lower()
    text = (data.get("text") or "").strip()
    turn_id = (data.get("turn_id") or "").strip() or None
    if not text:
        socketio.emit(
            "error",
            {"message": "text 必填", **({"turn_id": turn_id} if turn_id else {})},
            to=sid,
        )
        return
    my_partial = (data.get("my_partial") or "").strip()
    _start_message_gen(
        sid, text, my_partial,
        DEFAULT_SURFACE_MODEL, DEFAULT_DEEP_MODEL,
        turn_id=turn_id, context=str(data.get("context") or ""),
        speculative=bool(data.get("speculative")),
    )


@socketio.on("inject")
def ws_inject(data):
    global _LAST_SID
    _LAST_SID = request.sid
    _mark_activity()
    data = data or {}
    note = str(data.get("text") or data.get("note") or "").strip()
    if not note:
        return {"ok": False}
    tid = _start_inject_gen(request.sid, note, DEFAULT_SURFACE_MODEL, DEFAULT_DEEP_MODEL,
                            turn_id=data.get("turn_id"), context=str(data.get("context") or ""))
    return {"ok": bool(tid), "turn_id": tid}









@socketio.on("protect")
def ws_protect(_data=None):
    """TTS 开播时调用。把最近一条 turn 标为 protected。
    返回值用于 Socket.IO ACK，便于客户端用 call() 同步等待。"""
    sid = request.sid
    ok = _protect_latest()
    if not ok:
        socketio.emit("error", {"message": "无 turn 可保护"}, to=sid)
        return {"ok": False}
    return {"ok": True}


@socketio.on("commit")
def ws_commit(data=None):
    """发声端定稿信号（P2）：复用推测 id 的那一轮已成为正式输入，深层可以开始。"""
    tid = str((data or {}).get("turn_id") or "").strip()
    return {"ok": bool(tid) and _mark_committed(tid)}


@socketio.on("speech_done")
def ws_speech_done(data=None):
    """发声端通知：某轮的 TTS 音频已彻底播完、排空。
    【接着说】已停用，这里不再触发续说轮；保留 handler 只为兼容 STT 仍会发的事件。"""
    return {"ok": True}


@app.route("/api/evo/health")
def evo_health():
    return jsonify({"app": APP_NAME, "component": "brain", "status": "ok"})


from f_bridge import install as _install_build_f
_install_build_f(globals())


if __name__ == "__main__":
    reload_template()
    reload_surface_template()
    reload_thinking_template()
    run_template_check()          # R2：只打日志，不拒绝启动
    _load_history()
    _load_consolidated()
    _load_thinking_log()
    _startup_catchup()            # f_bridge 停用（旧整理系统）
    _init_current_cp()
    f_resume_pending()
    f_start_idle_reflection()     # B12：idle_reflection=true 时起空闲节奏线程
    print(f"[{APP_NAME}] Evidence memory active; idle reflection "
          f"{'on' if F_IDLE_REFLECTION else 'off'}, reflection-initiated speech "
          f"{'on' if F_AUTO_OPEN else 'off'}; self-continuation and legacy consolidation disabled.")
    host = os.getenv("HANE_HOST", "127.0.0.1")
    port = int(os.getenv("HANE_PORT", "5201"))
    print(f"[{APP_NAME} Hane] http://{host}:{port}")
    socketio.run(app, host=host, port=port, debug=False, use_reloader=False,
                 allow_unsafe_werkzeug=True)
