"""Deterministic red-flag detection.

Rules run on BOTH the English translation and the normalised original text, so
a mistranslation cannot hide an emergency. A match short-circuits the pipeline:
no retrieval, no generated text, only fixed emergency messages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.messages import (
    DISCLAIMER,
    EMERGENCY_HEADER,
    EMERGENCY_NUMBERS,
    MENTAL_HEALTH_SUPPORT,
    Message,
)
from app.services.translator import normalize_devanagari


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: re.Pattern[str]
    message: Message
    mental_health: bool = False


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


def _n(text: str) -> str:
    """Normalise a Hindi pattern fragment the same way input text is normalised."""
    return normalize_devanagari(text)


RULES: tuple[Rule, ...] = (
    Rule(
        "chest_pain",
        _rx(rf"chest (pain|tightness|pressure)|pain in (my )?chest|{_n('सीने में दर्द')}|{_n('छाती में दर्द')}|{_n('सीने में जकड़न')}"),
        Message(
            "Chest pain, pressure or tightness can be a sign of a heart attack.",
            "सीने में दर्द, दबाव या जकड़न दिल के दौरे का संकेत हो सकता है।",
        ),
    ),
    Rule(
        "breathing",
        _rx(
            r"(difficulty|trouble|hard to|unable to|can.?t) breath|short(ness)? of breath|gasping|struggling to breathe"
            rf"|{_n('सांस लेने में तकलीफ')}|{_n('साँस लेने में तकलीफ')}|{_n('सांस लेने में दिक्कत')}|{_n('साँस लेने में दिक्कत')}|{_n('सांस फूल')}|{_n('साँस फूल')}"
        ),
        Message(
            "Difficulty breathing needs urgent medical attention.",
            "सांस लेने में कठिनाई के लिए तुरंत चिकित्सा सहायता चाहिए।",
        ),
    ),
    Rule(
        "meningitis_signs",
        _rx(
            r"(?=.*\b(fever|high temperature)\b)(?=.*(stiff neck|neck stiffness|neck is stiff))"
            rf"|(?=.*{_n('बुखार')})(?=.*({_n('गर्दन में अकड़न')}|{_n('गर्दन अकड़')}|{_n('गर्दन जकड़')}))"
        ),
        Message(
            "Fever together with a stiff neck can be a sign of meningitis, which is an emergency.",
            "बुखार के साथ गर्दन में अकड़न मस्तिष्क ज्वर (मेनिन्जाइटिस) का संकेत हो सकता है, जो आपातकाल है।",
        ),
    ),
    Rule(
        "seizure",
        _rx(rf"seizure|convulsion|fitting|epilep|{_n('दौरे पड़')}|{_n('दौरा पड़')}|{_n('मिर्गी')}"),
        Message(
            "A seizure or convulsion needs urgent medical attention.",
            "दौरा पड़ने (झटके आने) पर तुरंत चिकित्सा सहायता चाहिए।",
        ),
    ),
    Rule(
        "unconscious",
        _rx(rf"unconscious|unresponsive|passed out|fainted|not waking|{_n('बेहोश')}"),
        Message(
            "Loss of consciousness is an emergency.",
            "बेहोशी एक आपातकालीन स्थिति है।",
        ),
    ),
    Rule(
        "stroke",
        _rx(
            r"face (is )?droop|slurred speech|sudden weakness (on|in) (one|the) (side|arm|leg)|can.?t (move|lift) (my|his|her) (arm|leg)"
            rf"|{_n('चेहरा टेढ़ा')}|{_n('बोलने में दिक्कत')}|{_n('एक तरफ कमजोरी')}"
        ),
        Message(
            "These can be signs of a stroke. Every minute matters.",
            "ये स्ट्रोक (लकवा) के संकेत हो सकते हैं। हर मिनट कीमती है।",
        ),
    ),
    Rule(
        "severe_bleeding",
        _rx(
            r"severe bleeding|heavy bleeding|won.?t stop bleeding|bleeding (a lot|heavily)|vomiting blood|vomit(ed|ing)? blood|coughing (up )?blood"
            rf"|{_n('बहुत खून बह')}|{_n('खून की उल्टी')}|{_n('खून की उलटी')}"
        ),
        Message(
            "Heavy bleeding or vomiting blood needs urgent care.",
            "अधिक रक्तस्राव या खून की उल्टी में तुरंत इलाज चाहिए।",
        ),
    ),
    Rule(
        "poisoning",
        _rx(rf"poison|overdose|swallowed (bleach|pesticide|kerosene)|{_n('जहर')}|{_n('ज़हर')}"),
        Message(
            "Suspected poisoning or overdose is an emergency.",
            "जहर खाने या दवा की अधिक मात्रा का संदेह आपातकाल है।",
        ),
    ),
    Rule(
        "allergic_reaction",
        _rx(r"swelling (of|in) (the )?(face|lips|tongue|throat)|throat (is )?closing|anaphyla"),
        Message(
            "Swelling of the face, lips or throat can be a severe allergic reaction.",
            "चेहरे, होंठ या गले में सूजन गंभीर एलर्जी प्रतिक्रिया हो सकती है।",
        ),
    ),
    Rule(
        "self_harm",
        _rx(
            r"suicid|kill myself|end my life|want to die|self.?harm|hurt myself|no reason to live"
            rf"|{_n('आत्महत्या')}|{_n('जान देना')}|{_n('मरना चाहता')}|{_n('मरना चाहती')}|{_n('जीना नहीं चाहता')}|{_n('जीना नहीं चाहती')}"
        ),
        Message(
            "I am concerned about your safety.",
            "मुझे आपकी सुरक्षा की चिंता है।",
        ),
        mental_health=True,
    ),
)


@dataclass(frozen=True)
class SafetyResult:
    emergency: bool
    rule_ids: tuple[str, ...]
    messages: tuple[Message, ...]  # ordered: header, per-rule, support/numbers, disclaimer


class SafetyService:
    def evaluate(self, english_text: str, original_text: str) -> SafetyResult:
        haystack = f"{english_text}\n{normalize_devanagari(original_text)}"
        hits = [rule for rule in RULES if rule.pattern.search(haystack.replace("\n", " "))]
        if not hits:
            return SafetyResult(False, (), ())

        messages: list[Message] = [EMERGENCY_HEADER]
        messages.extend(rule.message for rule in hits)
        if any(rule.mental_health for rule in hits):
            messages.append(MENTAL_HEALTH_SUPPORT)
        messages.append(EMERGENCY_NUMBERS)
        messages.append(DISCLAIMER)
        return SafetyResult(True, tuple(rule.id for rule in hits), tuple(messages))
