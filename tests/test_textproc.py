"""Tests for deterministic transcript post-processing.

Run with: ``python -m unittest discover tests`` (no pytest required).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from inkit_popos.textproc import apply_replacements, apply_spoken_punctuation  # noqa: E402


class SpokenPunctuationTests(unittest.TestCase):
    def punct(self, text, **cfg):
        cfg.setdefault("enabled", True)
        return apply_spoken_punctuation(text, cfg)

    def test_basic_sentence(self):
        self.assertEqual(
            self.punct("hello comma world period"),
            "Hello, world.",
        )

    def test_full_stop_and_question(self):
        self.assertEqual(
            self.punct("are you sure question mark"),
            "Are you sure?",
        )
        self.assertEqual(self.punct("done full stop"), "Done.")

    def test_new_line_and_paragraph(self):
        self.assertEqual(
            self.punct("item one new line item two"),
            "Item one\nItem two",
        )
        self.assertEqual(
            self.punct("intro new paragraph body"),
            "Intro\n\nBody",
        )

    def test_longest_phrase_wins(self):
        self.assertEqual(self.punct("wow exclamation point"), "Wow!")

    def test_parens_hug_correctly(self):
        self.assertEqual(
            self.punct("see open paren note close paren"),
            "See (note)",
        )

    def test_capitalize_can_be_disabled(self):
        self.assertEqual(
            self.punct("hello comma world", capitalize=False),
            "hello, world",
        )

    def test_extra_mappings_add_symbols(self):
        # Custom symbols keep natural spacing (only sentence punctuation hugs).
        self.assertEqual(
            self.punct("rock and sign roll", extra={"and sign": "&"}),
            "Rock & roll",
        )

    def test_disabled_is_passthrough(self):
        self.assertEqual(
            apply_spoken_punctuation("hello comma", {"enabled": False}),
            "hello comma",
        )

    def test_word_not_matched_inside_other_words(self):
        # "comma" appears as a substring of nothing here, but guard \b anyway.
        self.assertEqual(self.punct("commando period"), "Commando.")


class ReplacementTests(unittest.TestCase):
    def repl(self, text, mapping, **cfg):
        cfg.setdefault("enabled", True)
        cfg["map"] = mapping
        return apply_replacements(text, cfg)

    def test_case_insensitive_default(self):
        self.assertEqual(
            self.repl("i love pop os", {"pop os": "Pop!_OS"}),
            "i love Pop!_OS",
        )

    def test_preserves_replacement_casing(self):
        self.assertEqual(self.repl("inkit rocks", {"inkit": "InkIt"}), "InkIt rocks")

    def test_whole_word_only(self):
        self.assertEqual(self.repl("scattered", {"cat": "dog"}), "scattered")

    def test_longest_source_wins(self):
        mapping = {"new york": "NYC", "york": "York"}
        self.assertEqual(self.repl("new york city", mapping), "NYC city")

    def test_case_sensitive_mode(self):
        self.assertEqual(
            self.repl("API and api", {"api": "REST"}, case_sensitive=True),
            "API and REST",
        )

    def test_literal_replacement_with_backslashes(self):
        # Replacement text must not be interpreted as a regex template.
        self.assertEqual(self.repl("path", {"path": r"C:\n\1"}), r"C:\n\1")

    def test_disabled_or_empty_is_passthrough(self):
        self.assertEqual(apply_replacements("hi", {"enabled": False, "map": {"hi": "yo"}}), "hi")
        self.assertEqual(apply_replacements("hi", {"enabled": True, "map": {}}), "hi")


if __name__ == "__main__":
    unittest.main()
