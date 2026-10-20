"""Runtime configuration, read once from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


def _csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw not in (None, "") else default
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    try:
        return float(raw) if raw not in (None, "") else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    project_name: str
    version: str
    environment: str
    api_keys: tuple[str, ...]
    cors_origins: tuple[str, ...]
    trust_proxy_headers: bool
    rate_limit_per_minute: int
    max_query_chars: int
    history_max_turns: int
    retrieval_top_k: int
    retrieval_min_score: float
    guidelines_path: Path
    translator_provider: str  # "offline" or "llm"
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout_seconds: float
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            project_name="MedVani AI",
            version="1.0.0",
            environment=os.getenv("MEDVANI_ENV", "development"),
            api_keys=_csv(os.getenv("MEDVANI_API_KEYS")),
            cors_origins=_csv(os.getenv("MEDVANI_CORS_ORIGINS")),
            trust_proxy_headers=os.getenv("MEDVANI_TRUST_PROXY", "false").lower() == "true",
            rate_limit_per_minute=_int("MEDVANI_RATE_LIMIT_PER_MINUTE", 30),
            max_query_chars=_int("MEDVANI_MAX_QUERY_CHARS", 1000),
            history_max_turns=_int("MEDVANI_HISTORY_MAX_TURNS", 4),
            retrieval_top_k=_int("MEDVANI_TOP_K", 3),
            retrieval_min_score=_float("MEDVANI_MIN_SCORE", 0.12),
            guidelines_path=Path(
                os.getenv("MEDVANI_GUIDELINES_PATH", str(ROOT_DIR / "data" / "guidelines.json"))
            ),
            translator_provider=os.getenv("MEDVANI_TRANSLATOR", "offline").lower(),
            llm_base_url=os.getenv("MEDVANI_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            llm_api_key=os.getenv("MEDVANI_LLM_API_KEY", ""),
            llm_model=os.getenv("MEDVANI_LLM_MODEL", ""),
            llm_timeout_seconds=_float("MEDVANI_LLM_TIMEOUT", 15.0),
            log_level=os.getenv("MEDVANI_LOG_LEVEL", "INFO").upper(),
        )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
