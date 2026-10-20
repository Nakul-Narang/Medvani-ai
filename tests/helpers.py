from __future__ import annotations

import dataclasses

from app.agents.graph import build_pipeline
from app.agents.nodes import Services
from app.core.config import Settings
from app.services.retriever import GuidelineRetriever
from app.services.safety import SafetyService
from app.services.translator import OfflineTranslator


def make_settings(**overrides) -> Settings:
    return dataclasses.replace(Settings.from_env(), **overrides)


def make_services(**overrides) -> Services:
    settings = make_settings(**overrides)
    return Services(
        settings=settings,
        translator=OfflineTranslator(),
        retriever=GuidelineRetriever.from_file(settings.guidelines_path),
        safety=SafetyService(),
    )


def run(query: str, language: str = "auto", history=None, **overrides) -> dict:
    pipeline = build_pipeline(make_services(**overrides))
    return pipeline.invoke(
        {
            "request_id": "test",
            "raw_user_query": query,
            "user_language": language,
            "chat_history": history or [],
        }
    )
