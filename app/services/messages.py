"""Fixed, human-reviewed response strings in English and Hindi.

These are never machine-generated, so the safety-critical wording (disclaimer,
emergency instructions) cannot drift or hallucinate.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Message:
    en: str
    hi: str


DISCLAIMER = Message(
    en=(
        "This is general health information, not a diagnosis or medical advice. "
        "It does not replace a doctor. If you are worried, or symptoms get worse, "
        "please see a qualified doctor."
    ),
    hi=(
        "यह केवल सामान्य स्वास्थ्य जानकारी है, निदान या चिकित्सकीय सलाह नहीं। "
        "यह डॉक्टर का विकल्प नहीं है। यदि आप चिंतित हैं या लक्षण बढ़ रहे हैं, "
        "तो कृपया किसी योग्य डॉक्टर को दिखाएँ।"
    ),
)

GUIDANCE_INTRO = Message(
    en="General guidance related to what you described:",
    hi="आपने जो बताया उससे जुड़ी सामान्य जानकारी:",
)

NO_MATCH = Message(
    en=(
        "I could not find reliable guidance for this in my knowledge base. "
        "Please describe your main symptoms in a short sentence "
        "(for example: fever, cough, stomach pain), or consult a doctor."
    ),
    hi=(
        "मेरे ज्ञान-भंडार में इसके लिए भरोसेमंद जानकारी नहीं मिली। "
        "कृपया अपने मुख्य लक्षण छोटे वाक्य में बताएँ (जैसे: बुखार, खाँसी, पेट दर्द), "
        "या डॉक्टर से सलाह लें।"
    ),
)

EMERGENCY_HEADER = Message(
    en="This may be an emergency. Please act now:",
    hi="यह आपातकालीन स्थिति हो सकती है। कृपया अभी कदम उठाएँ:",
)

EMERGENCY_NUMBERS = Message(
    en=(
        "In India call 112 (national emergency number) or 108 (ambulance). "
        "Do not wait for an online answer. If you are outside India, call your local emergency number."
    ),
    hi=(
        "भारत में 112 (राष्ट्रीय आपातकालीन नंबर) या 108 (एम्बुलेंस) पर कॉल करें। "
        "ऑनलाइन उत्तर का इंतज़ार न करें। यदि आप भारत से बाहर हैं तो अपने स्थानीय आपातकालीन नंबर पर कॉल करें।"
    ),
)

MENTAL_HEALTH_SUPPORT = Message(
    en=(
        "You are not alone. In India you can call Tele-MANAS at 14416 (free, 24x7, many languages) "
        "or talk to someone you trust right now."
    ),
    hi=(
        "आप अकेले नहीं हैं। भारत में आप Tele-MANAS को 14416 पर कॉल कर सकते हैं "
        "(निःशुल्क, 24x7, कई भाषाओं में) या अभी किसी भरोसेमंद व्यक्ति से बात करें।"
    ),
)

PARTIAL_TRANSLATION_WARNING = (
    "Some parts are shown in English because this language is not supported offline. "
    "Set MEDVANI_TRANSLATOR=llm to enable more languages."
)
