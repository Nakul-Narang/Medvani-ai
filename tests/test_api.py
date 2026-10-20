"""HTTP-level tests. Skipped automatically when FastAPI is not installed."""

from __future__ import annotations

import unittest

try:
    from fastapi.testclient import TestClient

    from app.main import create_app

    HAVE_FASTAPI = True
except ImportError:  # pragma: no cover
    HAVE_FASTAPI = False

from tests.helpers import make_services, make_settings


@unittest.skipUnless(HAVE_FASTAPI, "fastapi is not installed")
class ApiTests(unittest.TestCase):
    def client(self, **overrides) -> "TestClient":
        settings = make_settings(**overrides)
        app = create_app(settings=settings, services=make_services(**overrides))
        return TestClient(app)

    def test_health_and_ready(self):
        with self.client() as c:
            self.assertEqual(c.get("/health").json(), {"status": "ok"})
            ready = c.get("/ready").json()
            self.assertEqual(ready["status"], "ready")
            self.assertGreater(ready["guidelines"], 5)

    def test_home_page_is_served(self):
        with self.client() as c:
            r = c.get("/")
            self.assertEqual(r.status_code, 200)
            self.assertIn("MedVani AI", r.text)
            self.assertIn("viewport", r.text)

    def test_consult_hindi(self):
        with self.client() as c:
            r = c.post("/api/v1/consult", json={"query": "मुझे तेज़ सिरदर्द और बुखार है"})
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertEqual(body["response_language"], "hi")
            self.assertFalse(body["emergency"])
            self.assertTrue(body["sources"])
            self.assertTrue(r.headers["x-request-id"])
            self.assertEqual(body["history"][-2]["role"], "user")

    def test_consult_emergency(self):
        with self.client() as c:
            body = c.post("/api/v1/consult", json={"query": "chest pain and cannot breathe"}).json()
            self.assertTrue(body["emergency"])
            self.assertIn("chest_pain", body["emergency_reasons"])
            self.assertEqual(body["sources"], [])

    def test_validation_does_not_echo_input(self):
        with self.client() as c:
            r = c.post("/api/v1/consult", json={"query": "   "})
            self.assertEqual(r.status_code, 422)
            self.assertNotIn("input", r.json()["detail"][0])
            self.assertEqual(set(r.json()["detail"][0]), {"loc", "msg"})

    def test_query_length_limit(self):
        with self.client(max_query_chars=20) as c:
            r = c.post("/api/v1/consult", json={"query": "fever " * 10})
            self.assertEqual(r.status_code, 413)

    def test_api_key_required_when_configured(self):
        with self.client(api_keys=("secret",)) as c:
            self.assertEqual(c.post("/api/v1/consult", json={"query": "fever"}).status_code, 401)
            ok = c.post("/api/v1/consult", json={"query": "fever"}, headers={"X-API-Key": "secret"})
            self.assertEqual(ok.status_code, 200)
            self.assertEqual(c.get("/health").status_code, 200)  # health stays open

    def test_rate_limit(self):
        with self.client(rate_limit_per_minute=2) as c:
            codes = [c.post("/api/v1/consult", json={"query": "fever"}).status_code for _ in range(3)]
            self.assertEqual(codes, [200, 200, 429])


if __name__ == "__main__":
    unittest.main()
