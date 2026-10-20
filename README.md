# MedVani AI

Multilingual (Hindi + English) health-information API. A user describes symptoms in their own language; the service understands the message, checks it for emergencies, retrieves matching general guidance from a local knowledge base, and answers in the user's language.

> **Not a medical device. Not medical advice.** The bundled knowledge base is a *starter corpus that has not been clinically reviewed*. Do not present this service to the public as a source of medical guidance until a qualified clinician has reviewed `data/guidelines.json`. See [Safety design](#safety-design).

## How it works

```text
 Client (Hindi / English)
        │  POST /api/v1/consult
        ▼
 ┌──────────────────────── FastAPI ─────────────────────────┐
 │ request id · rate limit · API key · input validation      │
 └───────────────────────────┬──────────────────────────────┘
                             ▼
 ┌─────────────── LangGraph pipeline (app/agents) ──────────┐
 │ 1 translate_input  language detect + Hindi → English      │
 │ 2 safety_check     deterministic red-flag rules           │
 │        ├─ emergency ──────────────┐                       │
 │ 3 retrieve         TF-IDF search  │  (skipped)            │
 │ 4 compose          extractive answer + disclaimer ◄───────┘
 │ 5 translate_output pre-written Hindi (or LLM) → user lang │
 └───────────────────────────┬──────────────────────────────┘
                             ▼
        answer · sources · emergency flag · request id
```

Design choices that matter:

- **Extractive, not generative.** Answers are assembled from reviewed corpus text, so the service cannot invent medical content. The LLM (optional) is used only for *translation*, never to write advice.
- **Safety runs before retrieval, on the original text too.** Emergency rules check both the English translation and the user's original Hindi, so a bad translation cannot hide chest pain or self-harm. A match skips retrieval and returns fixed, human-written emergency messages (112 / 108 / Tele-MANAS 14416).
- **No dosing.** The corpus contains no drug names or doses, and a test enforces that.
- **Works with zero API keys.** The default offline translator uses a curated Hindi symptom glossary in, and pre-written Hindi out. It says so (`warnings`) when it cannot understand a message instead of guessing.

## API

`POST /api/v1/consult`

```json
{
  "query": "मुझे पिछले दो दिनों से तेज़ सिरदर्द और बुखार है।",
  "language": "auto",
  "history": []
}
```

| Field | Notes |
|-------|-------|
| `query` | 1–2000 chars (server limit `MEDVANI_MAX_QUERY_CHARS`, default 1000) |
| `language` | `auto`, `en`, `hi`; other ISO codes need `MEDVANI_TRANSLATOR=llm` |
| `history` | Previous turns; the server keeps the last `MEDVANI_HISTORY_MAX_TURNS` exchanges and returns the updated list. The server stores nothing. |

Response (abridged):

```json
{
  "request_id": "9f1c…",
  "detected_language": "hi",
  "response_language": "hi",
  "answer": "आपने जो बताया उससे जुड़ी सामान्य जानकारी: …",
  "emergency": false,
  "emergency_reasons": [],
  "sources": [{"id": "fever-headache-warning", "title": "…", "source": "…", "score": 0.41}],
  "warnings": [],
  "history": [{"role": "user", "content": "…"}, {"role": "assistant", "content": "…"}]
}
```

Other endpoints: `GET /health` (liveness), `GET /ready` (knowledge base loaded), `GET /docs` (Swagger, disabled when `MEDVANI_ENV=production`).

Errors: `401` bad API key · `413` query too long · `422` validation · `429` rate limited (`Retry-After` header) · `500` generic message that still points to 112.

```bash
curl -X POST http://localhost:8000/api/v1/consult \
  -H "Content-Type: application/json" \
  -d '{"query":"fever and cough for 4 days"}'
```

## Run locally

```bash
git clone https://github.com/Nakul-Narang/Medvani-ai.git
cd Medvani-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs.

### Docker

```bash
docker build -t medvani-ai .
docker run --rm -p 8000:8000 --env-file .env medvani-ai
```

### Termux (Android)

Heavy wheels (`pydantic-core`, `scikit-learn`) may need the Rust and clang toolchains:

```bash
pkg install python clang rust binutils
export CARGO_BUILD_TARGET=aarch64-linux-android   # only if a wheel build fails
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Configuration

All settings are environment variables; see [`.env.example`](.env.example). The important ones:

| Variable | Default | Purpose |
|----------|---------|---------|
| `MEDVANI_ENV` | `development` | `production` hides `/docs` |
| `MEDVANI_API_KEYS` | empty | Comma-separated keys for `X-API-Key`. Empty disables auth. **Set this in production.** |
| `MEDVANI_RATE_LIMIT_PER_MINUTE` | `30` | Per client IP, per instance |
| `MEDVANI_TRUST_PROXY` | `false` | Read client IP from `X-Forwarded-For` (only behind a trusted proxy) |
| `MEDVANI_TRANSLATOR` | `offline` | `offline` or `llm` |
| `MEDVANI_LLM_*` | empty | Base URL, key and model for any OpenAI-compatible API |

## Tests

```bash
python -m pytest -q        # or: python -m unittest discover -s tests -t .
```

Covers language detection, the Hindi glossary (including a false-positive guard for "दौरान"), every emergency rule, retrieval relevance, a corpus check that forbids dosing text, the sliding-window history, rate limiting, API-key auth and the HTTP layer. CI runs the suite on Python 3.12 and 3.13 and smoke-tests the Docker image.

## Deploy

See [DEPLOYMENT.md](DEPLOYMENT.md) for Render (Blueprint included), Docker anywhere, and the pre-launch checklist.

## Safety design

| Risk | Mitigation |
|------|------------|
| Hallucinated medical advice | Extractive answers only; LLM used for translation only |
| Missed emergency | Deterministic rules on original *and* translated text; fixed emergency messages; tests per rule |
| Dangerous dosing text | None in corpus; automated test blocks it |
| Mistranslation of advice | Human-written Hindi shipped with every guideline; LLM only for other languages, with fallback to English and a visible warning |
| Health data leakage | Query text is never logged; tracing to third parties is off by default; the server stores no conversations |
| Abuse | API keys, per-IP rate limit, input length limits, no echo of invalid input |

## Known limitations

- The corpus is small (13 entries) and unreviewed. Clinical review and expansion come before public launch.
- Offline Hindi understanding is a symptom glossary, not general translation. Unknown phrasing returns a "could not understand" fallback.
- The rate limiter is in-memory, so it limits per instance. Use a gateway or Redis for multi-instance fleets.
- Retrieval is TF-IDF. Embeddings (for example ChromaDB with a multilingual model) are a planned upgrade; measure on an evaluation set first.
- Emergency numbers are India-specific.

## Roadmap

- [ ] Clinician review of `data/guidelines.json`, with reviewer name and date in each entry
- [ ] Evaluation set (labelled queries) with retrieval hit-rate and emergency recall reported in CI
- [ ] Embedding retriever behind the same interface
- [ ] More languages through the LLM translator, with back-translation checks
- [ ] Redis-backed rate limiting

## Project layout

```text
app/
  main.py              app factory, middleware, error handlers
  api/v1/              consult + health routes
  agents/              state, nodes, graph (LangGraph, with a plain fallback runner)
  services/            translator, safety, retriever, language, messages
  schemas/             request/response models
  core/                config, logging, security
data/guidelines.json   bilingual knowledge base
tests/                 unit + API tests
```

## License

MIT
