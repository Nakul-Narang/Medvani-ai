"""Typed shared state passed between pipeline nodes."""

from __future__ import annotations

from typing import Any, TypedDict


class MedicalAgentState(TypedDict, total=False):
    # input
    request_id: str
    raw_user_query: str
    user_language: str  # requested: "auto" or an ISO code such as "hi"
    chat_history: list[dict[str, str]]  # [{"role": "user"|"assistant", "content": ...}]

    # translate_input
    detected_language: str
    response_language: str
    translated_english_query: str
    retrieval_query: str
    translation_confident: bool

    # safety_check
    emergency: bool
    emergency_rules: list[str]
    emergency_messages: list[Any]  # list[Message]

    # retrieve
    retrieved: list[dict[str, Any]]

    # compose / translate_output
    response_parts: list[Any]  # list[Part]
    raw_clinical_response: str
    final_translated_response: str
    warnings: list[str]
