from __future__ import annotations

import unittest

from tests.helpers import run


class PipelineTests(unittest.TestCase):
    def test_hindi_end_to_end(self):
        r = run("मुझे पिछले दो दिनों से तेज़ सिरदर्द और बुखार है।")
        self.assertEqual(r["detected_language"], "hi")
        self.assertFalse(r["emergency"])
        self.assertTrue(r["retrieved"])
        # Answer is Hindi (Devanagari) and carries the Hindi disclaimer.
        self.assertIn("डॉक्टर", r["final_translated_response"])
        self.assertIn("सामान्य स्वास्थ्य जानकारी", r["final_translated_response"])

    def test_english_end_to_end(self):
        r = run("I have a cough and fever for 4 days")
        self.assertEqual(r["response_language"], "en")
        self.assertIn("not a diagnosis", r["final_translated_response"])
        self.assertIn("pneumonia-warning", [h["id"] for h in r["retrieved"]])

    def test_emergency_short_circuits_retrieval(self):
        r = run("I have chest pain and shortness of breath")
        self.assertTrue(r["emergency"])
        self.assertNotIn("retrieved", r)  # retrieval node never ran
        self.assertIn("112", r["final_translated_response"])

    def test_hindi_emergency(self):
        r = run("मुझे सीने में दर्द और सांस लेने में तकलीफ है")
        self.assertTrue(r["emergency"])
        self.assertIn("112", r["final_translated_response"])
        self.assertIn("आपातकालीन", r["final_translated_response"])

    def test_no_match_gives_safe_fallback(self):
        r = run("what is the capital of france")
        self.assertFalse(r["emergency"])
        self.assertEqual(r["retrieved"], [])
        self.assertIn("consult a doctor", r["final_translated_response"])

    def test_answers_never_contain_dosing(self):
        for q in ("fever", "headache", "diarrhoea", "cough", "stomach pain", "rash"):
            with self.subTest(q=q):
                text = run(q)["final_translated_response"].lower()
                self.assertNotIn(" mg", text)

    def test_explicit_language_overrides_detection(self):
        r = run("fever", language="hi")
        self.assertEqual(r["response_language"], "hi")
        self.assertIn("बुखार", r["final_translated_response"])

    def test_unsupported_language_warns_and_falls_back_to_english(self):
        r = run("fever", language="ta")
        self.assertTrue(r["warnings"])
        self.assertIn("not a diagnosis", r["final_translated_response"])

    def test_history_is_a_sliding_window(self):
        history = []
        for i in range(10):
            history += [{"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": f"a{i}"}]
        r = run("fever", history=history, history_max_turns=2)
        self.assertEqual(len(r["chat_history"]), 4)  # 2 turns * (user + assistant)
        self.assertEqual(r["chat_history"][-2]["content"], "fever")

    def test_short_followup_borrows_previous_question(self):
        history = [
            {"role": "user", "content": "I have diarrhoea"},
            {"role": "assistant", "content": "..."},
        ]
        r = run("how long?", history=history)
        self.assertEqual(r["retrieved"][0]["id"], "diarrhoea")


if __name__ == "__main__":
    unittest.main()
