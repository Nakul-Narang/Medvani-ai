"""Local retrieval over the bilingual guideline corpus (TF-IDF, no network).

The corpus is a JSON list of entries:
    {id, title, source, keywords[], en, hi}
Answers are extractive: the service only ever returns text that exists in the
corpus, so it cannot invent medical content.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel


@dataclass(frozen=True)
class Guideline:
    id: str
    title: str
    source: str
    keywords: tuple[str, ...]
    en: str
    hi: str | None


@dataclass(frozen=True)
class Hit:
    guideline: Guideline
    score: float


class GuidelineRetriever:
    def __init__(self, guidelines: list[Guideline]) -> None:
        if not guidelines:
            raise ValueError("guideline corpus is empty")
        self._guidelines = guidelines
        self._vectorizer = TfidfVectorizer(
            ngram_range=(1, 2), stop_words="english", sublinear_tf=True
        )
        documents = [self._document_text(g) for g in guidelines]
        self._matrix = self._vectorizer.fit_transform(documents)

    @staticmethod
    def _document_text(g: Guideline) -> str:
        # Keywords are repeated so they weigh more than body text.
        return " ".join([g.title, *g.keywords, *g.keywords, g.en])

    @classmethod
    def from_file(cls, path: Path) -> "GuidelineRetriever":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        guidelines = [
            Guideline(
                id=item["id"],
                title=item["title"],
                source=item["source"],
                keywords=tuple(item.get("keywords", [])),
                en=item["en"],
                hi=item.get("hi"),
            )
            for item in raw["guidelines"]
        ]
        return cls(guidelines)

    def __len__(self) -> int:
        return len(self._guidelines)

    def search(self, query: str, top_k: int = 3, min_score: float = 0.12) -> list[Hit]:
        query = query.strip()
        if not query:
            return []
        scores = linear_kernel(self._vectorizer.transform([query]), self._matrix).ravel()
        ranked = sorted(enumerate(scores), key=lambda pair: pair[1], reverse=True)
        hits = [
            Hit(self._guidelines[i], float(score))
            for i, score in ranked[:top_k]
            if score >= min_score
        ]
        return hits
