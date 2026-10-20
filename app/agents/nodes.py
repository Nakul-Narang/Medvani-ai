"""Pipeline nodes. Each takes the state and returns a partial update."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from app.agents.state import MedicalAgentState
from app.core.config import Settings
from app.services.language import detect_language, normalize_language_code
from app.services.messages import DISCLAIMER, GUIDANCE_INTRO, NO_MATCH
from app.services.retriever import GuidelineRetriever
from app.services.safety import SafetyService
from app.services.translator import Part, Translator

logger = logging.getLogger(__name__)

NodeFn = Callable[[MedicalAgentState], dict]


@dataclass
class Services:
    settings: Settings
    translator: Translator
    retriever: GuidelineRetriever
    safety: SafetyService


def trim_history(history: list[dict[str, str]], max_turns: int) -> list[dict[str, str]]:
    """Sliding window: keep only the last ``max_turns`` user/assistant exchanges."""
    return list(history[-(max_turns * 2) :]) if max_turns > 0 else []


def make_nodes(svc: Services) -> dict[str, NodeFn]:
    def translate_input(state: MedicalAgentState) -> dict:
        query = state["raw_user_query"].strip()
        requested = normalize_language_code(state.get("user_language"))
        detected = detect_language(query) if requested == "auto" else requested
        response_lang = detected

        translated = svc.translator.to_english(query, detected)
        history = trim_history(state.get("chat_history", []), svc.settings.history_max_turns)

        # Short follow-ups ("and for how long?") borrow context from the last user turn.
        retrieval_query = translated.text
        previous_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), None)
        if previous_user and len(translated.text.split()) < 4:
            previous_en = svc.translator.to_english(previous_user, detect_language(previous_user))
            retrieval_query = f"{previous_en.text} {translated.text}"

        return {
            "detected_language": detected,
            "response_language": response_lang,
            "translated_english_query": translated.text,
            "retrieval_query": retrieval_query,
            "translation_confident": translated.confident,
            "chat_history": history,
            "warnings": [],
        }

    def safety_check(state: MedicalAgentState) -> dict:
        result = svc.safety.evaluate(
            state["translated_english_query"] + " " + state.get("retrieval_query", ""),
            state["raw_user_query"],
        )
        if result.emergency:
            logger.warning(
                "emergency rules matched",
                extra={"request_id": state.get("request_id"), "rules": list(result.rule_ids)},
            )
        return {
            "emergency": result.emergency,
            "emergency_rules": list(result.rule_ids),
            "emergency_messages": list(result.messages),
        }

    def retrieve(state: MedicalAgentState) -> dict:
        hits = svc.retriever.search(
            state["retrieval_query"],
            top_k=svc.settings.retrieval_top_k,
            min_score=svc.settings.retrieval_min_score,
        )
        return {
            "retrieved": [
                {
                    "id": h.guideline.id,
                    "title": h.guideline.title,
                    "source": h.guideline.source,
                    "score": round(h.score, 4),
                    "en": h.guideline.en,
                    "hi": h.guideline.hi,
                }
                for h in hits
            ]
        }

    def compose(state: MedicalAgentState) -> dict:
        parts: list[Part]
        if state.get("emergency"):
            parts = [Part(m.en, m.hi) for m in state["emergency_messages"]]
        elif state.get("retrieved"):
            parts = [Part(GUIDANCE_INTRO.en, GUIDANCE_INTRO.hi)]
            parts += [Part(h["en"], h.get("hi")) for h in state["retrieved"]]
            parts.append(Part(DISCLAIMER.en, DISCLAIMER.hi))
        else:
            parts = [Part(NO_MATCH.en, NO_MATCH.hi), Part(DISCLAIMER.en, DISCLAIMER.hi)]
        return {
            "response_parts": parts,
            "raw_clinical_response": "\n\n".join(p.en for p in parts),
        }

    def translate_output(state: MedicalAgentState) -> dict:
        target = state.get("response_language", "en")
        rendered = svc.translator.render(state["response_parts"], target)
        warnings = list(state.get("warnings", [])) + list(rendered.warnings)
        if not state.get("translation_confident", True) and not state.get("retrieved") and not state.get("emergency"):
            warnings.append("Your message could not be fully understood in this language.")

        history = list(state.get("chat_history", []))
        history.append({"role": "user", "content": state["raw_user_query"]})
        history.append({"role": "assistant", "content": rendered.text})
        history = trim_history(history, svc.settings.history_max_turns)
        return {
            "final_translated_response": rendered.text,
            "warnings": warnings,
            "chat_history": history,
        }

    return {
        "translate_input": translate_input,
        "safety_check": safety_check,
        "retrieve": retrieve,
        "compose": compose,
        "translate_output": translate_output,
    }
