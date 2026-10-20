# Deployment

## Option A: Render (Blueprint included)

1. Push this repo to GitHub.
2. Render dashboard → **New → Blueprint** → select the repo. It reads `render.yaml`.
3. Set the secrets Render asks for (`sync: false` values):
   - `MEDVANI_API_KEYS`: generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   - `MEDVANI_CORS_ORIGINS`: your front-end origin, for example `https://app.example.com`
4. Wait for the build, then verify:

```bash
scripts/smoke_test.sh https://medvani-ai.onrender.com YOUR_API_KEY
```

The free plan sleeps when idle (the first request after idle takes about 30 seconds). Use a paid plan for real traffic.

## Option B: any Docker host (Fly.io, Cloud Run, a VPS)

```bash
docker build -t medvani-ai .
docker run -d --restart unless-stopped -p 8000:8000 \
  -e MEDVANI_API_KEYS=... -e MEDVANI_CORS_ORIGINS=... medvani-ai
```

Put TLS in front (the platform's HTTPS, or nginx/Caddy). The container honours `PORT` and `WEB_CONCURRENCY`.

## Capacity notes

- Each worker loads the corpus and TF-IDF matrix (small) and handles requests in a threadpool. Typical requests are CPU-light; measure with your own load test before promising numbers.
- Scale out by adding instances. The rate limiter is per instance, so add a gateway-level limit when running more than one.

## Pre-launch checklist (do not skip)

- [ ] A qualified clinician has reviewed every entry in `data/guidelines.json`
- [ ] `MEDVANI_API_KEYS` set; `MEDVANI_ENV=production`
- [ ] HTTPS only; CORS restricted to your front end
- [ ] Privacy notice published: what is processed, that queries are not stored or logged
- [ ] LangSmith tracing OFF unless users consent and a data agreement exists
- [ ] A visible "not medical advice" notice in every client UI
- [ ] Uptime monitor on `/health`; alerts on 5xx
- [ ] Load test run from your own machine against staging
- [ ] Legal review for your jurisdiction (health-information services can be regulated)
