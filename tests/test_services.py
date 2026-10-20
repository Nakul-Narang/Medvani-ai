from __future__ import annotations

import unittest

from app.core.security import SlidingWindowRateLimiter, api_key_is_valid
from app.services.language import detect_language, normalize_language_code
from app.services.safety import SafetyService
from app.services.translator import OfflineTranslator, Part
from tests.helpers import make_settings
from app.services.retriever import GuidelineRetriever


class LanguageTests(unittest.TestCase):
    def test_detects_hindi_and_english(self):
        self.assertEqual(detect_language("मुझे बुखार है"), "hi")
        self.assertEqual(detect_language("I have a fever"), "en")
        self.assertEqual(detect_language("12345"), "en")

    def test_normalize_code(self):
        self.assertEqual(normalize_language_code("hi-IN"), "hi")
        self.assertEqual(normalize_language_code(None), "auto")
        self.assertEqual(normalize_language_code(" AUTO "), "auto")


class OfflineTranslatorTests(unittest.TestCase):
    def setUp(self):
        self.t = OfflineTranslator()

    def test_hindi_symptoms_to_english(self):
        r = self.t.to_english("मुझे पिछले दो दिनों से तेज़ सिरदर्द और बुखार है।", "hi")
        self.assertTrue(r.confident)
        self.assertIn("severe headache", r.text)
        self.assertIn("fever", r.text)

    def test_nukta_variants_match(self):
        a = self.t.to_english("तेज़ बुखार", "hi").text
        b = self.t.to_english("तेज बुखार", "hi").text
        self.assertEqual(a, b)

    def test_unknown_hindi_is_not_confident(self):
        r = self.t.to_english("आज मौसम अच्छा है", "hi")
        self.assertFalse(r.confident)

    def test_dauran_does_not_trigger_seizure(self):
        r = self.t.to_english("यात्रा के दौरान खांसी हुई", "hi")
        self.assertNotIn("seizure", r.text)
        self.assertIn("cough", r.text)

    def test_render_prefers_written_hindi(self):
        out = self.t.render([Part("English", "हिन्दी")], "hi")
        self.assertEqual(out.text, "हिन्दी")
        self.assertEqual(out.warnings, ())

    def test_render_unsupported_language_warns(self):
        out = self.t.render([Part("English", "हिन्दी")], "ta")
        self.assertEqual(out.text, "English")
        self.assertTrue(out.warnings)


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.s = SafetyService()

    def check(self, english, original=None):
        return self.s.evaluate(english, original or english)

    def test_flags_emergencies(self):
        cases = {
            "chest_pain": "I have chest pain since morning",
            "breathing": "I cannot breathe properly, shortness of breath",
            "meningitis_signs": "high fever and stiff neck",
            "seizure": "my brother had a seizure",
            "self_harm": "I want to die",
            "severe_bleeding": "he is vomiting blood",
        }
        for rule, text in cases.items():
            with self.subTest(rule=rule):
                self.assertIn(rule, self.check(text).rule_ids)

    def test_hindi_original_is_checked_even_if_translation_misses(self):
        r = self.check("unclear", "मुझे सीने में दर्द है")
        self.assertTrue(r.emergency)
        self.assertIn("chest_pain", r.rule_ids)

    def test_self_harm_adds_support_line(self):
        r = self.check("I want to die")
        self.assertTrue(any("14416" in m.en for m in r.messages))

    def test_ordinary_symptoms_are_not_emergencies(self):
        for text in ("mild headache", "cough and runny nose", "fever for one day", "stomach pain after lunch"):
            with self.subTest(text=text):
                self.assertFalse(self.check(text).emergency)

    def test_fever_alone_is_not_meningitis(self):
        self.assertNotIn("meningitis_signs", self.check("high fever").rule_ids)


class RetrieverTests(unittest.TestCase):
    def setUp(self):
        self.r = GuidelineRetriever.from_file(make_settings().guidelines_path)

    def test_corpus_is_bilingual_and_has_no_dosing(self):
        for g in self.r._guidelines:
            self.assertTrue(g.hi, f"{g.id} is missing Hindi text")
            lowered = g.en.lower()
            for banned in (" mg", "paracetamol", "acetaminophen", "ibuprofen"):
                self.assertNotIn(banned, lowered, f"{g.id} mentions {banned.strip()}")

    def test_relevant_hits(self):
        hits = self.r.search("severe headache and fever", top_k=3)
        self.assertTrue(hits)
        self.assertIn(hits[0].guideline.id, {"fever-headache-warning", "fever-general", "headache-general"})

    def test_diarrhoea_query(self):
        self.assertEqual(self.r.search("loose motions since yesterday")[0].guideline.id, "diarrhoea")

    def test_gibberish_returns_nothing(self):
        self.assertEqual(self.r.search("zzqx blorp wibble"), [])
        self.assertEqual(self.r.search("   "), [])


class SecurityTests(unittest.TestCase):
    def test_api_key(self):
        self.assertTrue(api_key_is_valid(None, ()))
        self.assertTrue(api_key_is_valid("k1", ("k1", "k2")))
        self.assertFalse(api_key_is_valid("nope", ("k1",)))
        self.assertFalse(api_key_is_valid(None, ("k1",)))

    def test_rate_limiter(self):
        rl = SlidingWindowRateLimiter(limit_per_minute=2)
        self.assertTrue(rl.allow("a", now=0)[0])
        self.assertTrue(rl.allow("a", now=1)[0])
        allowed, retry = rl.allow("a", now=2)
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry, 1)
        self.assertTrue(rl.allow("b", now=2)[0])  # other clients unaffected
        self.assertTrue(rl.allow("a", now=61)[0])  # window slid

    def test_rate_limit_disabled(self):
        rl = SlidingWindowRateLimiter(limit_per_minute=0)
        self.assertTrue(all(rl.allow("a", now=i)[0] for i in range(100)))


if __name__ == "__main__":
    unittest.main()
