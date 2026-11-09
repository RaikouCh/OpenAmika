"""The last fixes to a sentence before it goes to her voice server (what she *says*; what she writes is untouched).

The voice engine reads a word in capitals as an acronym, letter by letter ("YOUR" -> Y-O-U-R), and the English front
end reads an ellipsis as "dot dot dot" and stumbles on dashes. The LLM writes capitals for emphasis and uses dashes
and ellipses freely, so every sentence passes through voice_text() after the word map (config/word_replace.json,
llm_to_tts) has run:

  - a word of three or more capital letters is lower-cased ("YOUR" -> "your"), unless it is a known acronym
    (ACRONYMS, plus the "tts_keep_caps" list of config/word_replace.json) or has a digit attached ("GPT4", "CODE27");
  - an em dash or an en dash becomes a comma ("wait—what" -> "wait, what"); an en dash between two numbers ("5–10")
    is a range and stays;
  - an ellipsis ("…", "……" or three or more dots) becomes a full stop.

After Chinese or Japanese text the comma and the full stop are the full-width ones (，。).
"""
from __future__ import annotations

import re
from typing import Iterable

# acronyms her voice should spell (the word map can still rewrite any of them)
ACRONYMS = frozenset({"TTS", "GPU", "AI", "OK", "PC", "USB", "API", "LLM", "VRAM", "NVIDIA", "RTX", "HDMI", "URL", "ID"})

_APOS = "'’"
# a run of capitals, possibly with an apostrophe inside ("DON'T"), not touching another letter, a digit or an apostrophe
_CAPS = re.compile(rf"(?<![A-Za-z0-9{_APOS}])[A-Z]+(?:[{_APOS}][A-Z]+)*(?![A-Za-z0-9{_APOS}])")
_RANGE_DASH = re.compile(r"(?<=\d)\s*–\s*(?=\d)")             # 5–10: a range, not a pause
_DASH = re.compile(r"[ \t]*[—–]+[ \t]*")                # — and – (also —— in Chinese text)
_ELLIPSIS = re.compile(r"[ \t]*(?:…+|\.{3,})")                # … …… ... ....
_CJK = re.compile(r"[぀-ヿ㐀-鿿豈-﫿ｦ-ﾟ]")
_RANGE_MARK = "\u0000"


def _cjk_before(text: str, index: int) -> bool:
    """Is the last visible character before index Chinese or Japanese?"""
    before = text[:index].rstrip()
    return bool(before) and bool(_CJK.match(before[-1]))


def lower_shouting(text: str, keep: Iterable[str] = ()) -> str:
    """Lower-case every word of three or more capital letters that is not an acronym to keep."""
    keep_set = ACRONYMS | {str(k).strip().upper() for k in keep if str(k).strip()}

    def fix(match: re.Match) -> str:
        word = match.group(0)
        letters = re.sub(f"[{_APOS}]", "", word)
        if len(letters) < 3 or letters in keep_set:
            return word
        return word.lower()

    return _CAPS.sub(fix, text)


def calm_punctuation(text: str) -> str:
    """Dashes become commas and ellipses full stops (full-width after Chinese or Japanese text)."""
    if not text:
        return text
    text = _RANGE_DASH.sub(_RANGE_MARK, text)

    def comma(match: re.Match) -> str:
        if _cjk_before(match.string, match.start()):
            return "，"
        rest = match.string[match.end():]
        return "," if not rest or rest[0] in ",.!?;:，。！？" else ", "

    def stop(match: re.Match) -> str:
        if _cjk_before(match.string, match.start()):
            return "。"
        rest = match.string[match.end():]
        return "." if not rest or not rest[0].isalnum() else ". "

    text = _DASH.sub(comma, text)
    text = _ELLIPSIS.sub(stop, text)
    text = text.replace(_RANGE_MARK, "–")
    # nothing to say before a leading comma or full stop, nor after a trailing comma; no doubled marks
    # ("well..., " -> "well.", "really?..." -> "really?")
    text = re.sub(r"^[\s,.，。]+", "", text)
    text = re.sub(r"[\s,，]+$", "", text)
    text = re.sub(r"([,.，。])\s*[,，]+", r"\1", text)
    text = re.sub(r"[,，]\s*([.!?。！？])", r"\1", text)
    text = re.sub(r"([!?！？])[.。]+", r"\1", text)
    return text


def voice_text(text: str, keep: Iterable[str] = ()) -> str:
    """The sentence as her voice should read it: calm punctuation, then no shouting."""
    if not text:
        return text
    return lower_shouting(calm_punctuation(text), keep)
