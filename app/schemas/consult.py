from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ConsultRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="Symptoms or question, in any supported language")
    language: str = Field(
        default="auto",
        max_length=16,
        description='"auto" (detect), "en", "hi", or another ISO code when MEDVANI_TRANSLATOR=llm',
    )
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)

    @field_validator("query")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value


class Source(BaseModel):
    id: str
    title: str
    source: str
    score: float


class ConsultResponse(BaseModel):
    request_id: str
    detected_language: str
    response_language: str
    answer: str
    emergency: bool
    emergency_reasons: list[str]
    sources: list[Source]
    warnings: list[str]
    history: list[ChatTurn]
    disclaimer: str = (
        "General health information only. Not a diagnosis or medical advice. "
        "In an emergency call 112 (India)."
    )
