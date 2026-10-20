# Architecture

## Request flow

1. **Middleware** assigns `X-Request-ID`, applies the per-IP rate limit to `/api/*`, adds security headers, and logs method/path/status/latency. Request bodies are never logged.
2. **Route** (`app/api/v1/consult.py`) checks the API key, enforces the length limit, and builds the initial `MedicalAgentState`.
3. **Pipeline** (`app/agents/graph.py`) runs five nodes over the shared state:

| Node | Reads | Writes |
|------|-------|--------|
| `translate_input` | raw query, requested language, history | detected/response language, English query, retrieval query, trimmed history |
| `safety_check` | English + original text | `emergency`, matched rule ids, fixed messages |
| `retrieve` | retrieval query | top-k guideline hits (skipped on emergency) |
| `compose` | emergency flag / hits | ordered response parts (English + pre-written Hindi) |
| `translate_output` | parts, response language | final text, warnings, updated history |

4. **Response** is validated by `ConsultResponse`.

## Why these boundaries

- **Services are injected** (`Services` dataclass), so tests swap providers without patching.
- **Nodes are plain functions.** LangGraph is an orchestration layer, not a dependency of the logic: without it, `_SimplePipeline` runs the same nodes in the same order. Tests run on that path; production images use LangGraph.
- **Safety is its own service**, with rules as data (`RULES`), so adding a rule is one entry plus one test.
- **The translator interface** (`to_english`, `render`) hides whether text came from the glossary, pre-written Hindi, or an LLM.

## Extending

- *New guideline:* add an entry with `en` and `hi` to `data/guidelines.json`. The corpus test fails if `hi` is missing or dosing terms appear.
- *New emergency rule:* add a `Rule` in `app/services/safety.py` and a case in `tests/test_services.py`.
- *New language:* run with `MEDVANI_TRANSLATOR=llm`. For quality, add human-written text per guideline, as for Hindi.
- *Embeddings:* implement the same `search(query, top_k, min_score)` signature and swap it in `main.py`.
