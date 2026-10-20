#!/usr/bin/env bash
# Usage: scripts/smoke_test.sh https://your-app.onrender.com [API_KEY]
set -euo pipefail
BASE="${1:?base url required}"
KEY="${2:-}"
H=(-H "Content-Type: application/json"); [ -n "$KEY" ] && H+=(-H "X-API-Key: $KEY")

echo "health:";  curl -fsS "$BASE/health"; echo
echo "ready:";   curl -fsS "$BASE/ready"; echo
echo "english:"; curl -fsS -X POST "$BASE/api/v1/consult" "${H[@]}" -d '{"query":"fever and cough for 4 days"}' | head -c 400; echo
echo "hindi:";   curl -fsS -X POST "$BASE/api/v1/consult" "${H[@]}" -d '{"query":"मुझे तेज़ सिरदर्द और बुखार है"}' | head -c 400; echo
echo "emergency:"; curl -fsS -X POST "$BASE/api/v1/consult" "${H[@]}" -d '{"query":"chest pain and cannot breathe"}' | head -c 400; echo
echo "OK"
