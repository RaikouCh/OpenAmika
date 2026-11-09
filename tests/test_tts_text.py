"""What her voice reads (speech/tts_text.py): no letter-by-letter capitals, no "dot dot dot", dashes as pauses; and
the default llm_to_tts rules that ship in config/word_replace.json."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "speech"))

import tts_text  # noqa: E402
from tts_text import voice_text  # noqa: E402


class CapitalsTests(unittest.TestCase):
    def test_shouting_is_lower_cased(self):
        self.assertEqual(voice_text("I told YOU not to do THAT!"), "I told you not to do that!")
        self.assertEqual(voice_text("ARE YOU SURE???"), "are you sure???")
        self.assertEqual(voice_text("DON'T you DARE"), "don't you dare")
        self.assertEqual(voice_text("I said YOU’RE late"), "I said you’re late")

    def test_acronyms_stay(self):
        line = "Your GPU is an NVIDIA RTX card with 8 GB of VRAM; the TTS and the LLM use the API URL, OK?"
        self.assertEqual(voice_text(line), line)
        for word in ("TTS", "GPU", "AI", "OK", "PC", "USB", "API", "LLM", "VRAM", "NVIDIA", "RTX", "HDMI", "URL", "ID"):
            self.assertIn(word, tts_text.ACRONYMS)
            self.assertEqual(voice_text(f"the {word} works"), f"the {word} works")

    def test_short_words_and_words_with_digits_stay(self):
        self.assertEqual(voice_text("I'M fine, NO worries"), "I'M fine, NO worries")
        self.assertEqual(voice_text("GPT4 and CODE27 and RTX5090"), "GPT4 and CODE27 and RTX5090")
        self.assertEqual(voice_text("USB-C"), "USB-C")

    def test_capitals_next_to_chinese_text(self):
        self.assertEqual(voice_text("我用WINDOWS和GPU"), "我用windows和GPU")

    def test_keep_list_from_the_word_map(self):
        self.assertEqual(voice_text("NASA and FBI"), "nasa and fbi")
        self.assertEqual(voice_text("NASA and FBI", keep=["nasa", "FBI"]), "NASA and FBI")


class PunctuationTests(unittest.TestCase):
    def test_dashes_become_commas(self):
        self.assertEqual(voice_text("Wait—what?"), "Wait, what?")
        self.assertEqual(voice_text("wait — STOP – now"), "wait, stop, now")
        self.assertEqual(voice_text("—hi there"), "hi there")
        self.assertEqual(voice_text("I mean—"), "I mean")

    def test_number_ranges_keep_their_dash(self):
        self.assertEqual(voice_text("5–10 minutes"), "5–10 minutes")

    def test_ellipses_become_full_stops(self):
        self.assertEqual(voice_text("Hmm... I see"), "Hmm. I see")
        self.assertEqual(voice_text("Well…"), "Well.")
        self.assertEqual(voice_text("Really?..."), "Really?")
        self.assertEqual(voice_text("…and then"), "and then")
        self.assertNotIn("...", voice_text("so.... yes"))

    def test_chinese_and_japanese_get_full_width_marks(self):
        self.assertEqual(voice_text("你……不知道"), "你。不知道")
        self.assertEqual(voice_text("我——没事"), "我，没事")
        self.assertEqual(voice_text("私は…大丈夫"), "私は。大丈夫")

    def test_plain_text_is_untouched(self):
        for line in ("Hello there, how are you?", "今天天气不错。", "", "A B C"):
            self.assertEqual(voice_text(line), line)


class ShippedRulesTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads((ROOT / "config" / "word_replace.json").read_text(encoding="utf-8"))

    def test_default_rules_ship(self):
        rules = {str(r["from"]).lower(): r for r in self.doc["llm_to_tts"]}
        for word, said in (("lol", "haha"), ("idk", "I don't know"), ("btw", "by the way"), ("omg", "oh my god")):
            self.assertIn(word, rules)
            self.assertEqual(rules[word]["to"], said)
            self.assertTrue(rules[word]["ci"])
        self.assertIn("—", rules)                      # the em dash rule that was there before
        self.assertEqual(self.doc.get("tts_keep_caps"), [])

    def test_rules_match_whole_words_only(self):
        # speech/api.py bounds a rule whose edge is a letter or digit; the same bounds here
        def bounded(frm):
            left = r"(?<![A-Za-z0-9])" if (frm[:1].isascii() and frm[:1].isalnum()) else ""
            right = r"(?![A-Za-z0-9])" if (frm[-1:].isascii() and frm[-1:].isalnum()) else ""
            return re.compile(left + re.escape(frm) + right, re.IGNORECASE)
        self.assertIsNone(bounded("np").search("input"))
        self.assertIsNone(bounded("lol").search("lollipop"))
        self.assertIsNotNone(bounded("lol").search("that was funny lol"))


if __name__ == "__main__":
    unittest.main()
