"""API -> database -> subprocess/catalog -> response, using isolated local fixtures."""
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

from backend.src.main import app
from backend.src.database.connection import Base, get_db
from backend.src.models.orm import User, UserEvent, UserPreference, RecommendationRequest, RecommendationItem
from backend.src.security.jwt import create_access_token


class PersonalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import duckdb
        cls.directory = tempfile.TemporaryDirectory()
        root = Path(cls.directory.name)
        cls.engine = create_engine("sqlite:///" + str(root / "users.sqlite"), connect_args={"check_same_thread": False})
        Base.metadata.create_all(cls.engine)
        cls.sessions = sessionmaker(bind=cls.engine)
        cls.catalog = root / "catalog.parquet"
        with duckdb.connect() as db:
            db.execute("""CREATE TABLE catalog AS SELECT CAST(i AS VARCHAR) item_id,
                CAST(i AS VARCHAR) AS product_id, 'Product ' || i AS name, 10.0 + i AS price,
                CASE WHEN i < 40 THEN 'Electronics' ELSE 'Beauty' END category0,
                CASE WHEN i < 40 THEN 'Phone' ELSE 'Skincare' END category1,
                'Test' AS category2, 'Brand' AS brand, 'Good' AS condition, 'seller' AS shipper,
                TIMESTAMP '2026-01-01' + i * INTERVAL '1 day' last_seen_ts
                FROM range(80) t(i)""")
            db.execute("COPY catalog TO ? (FORMAT PARQUET)", [str(cls.catalog)])
        cls.environment = patch.dict(os.environ, {"MERREC_CATALOG_PATH": str(cls.catalog), "MERREC_RANKER": "rules"})
        cls.environment.start()

    @classmethod
    def tearDownClass(cls):
        cls.environment.stop()
        cls.engine.dispose()
        cls.directory.cleanup()

    def setUp(self):
        def session():
            with self.sessions() as db:
                yield db
        app.dependency_overrides[get_db] = session
        self.client = TestClient(app)
        self.user_id = str(uuid.uuid4())
        with self.sessions() as db:
            db.add(User(id=self.user_id, email=self.user_id + "@example.com", is_active=True, is_verified=True))
            db.commit()
        self.headers = {"Authorization": "Bearer " + create_access_token(self.user_id)}

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def test_preferences_roundtrip_retry_and_isolation(self):
        url = "/api/v1/profile/preferences"
        self.assertEqual(self.client.get(url, headers=self.headers).json(), {"categories": [], "completed": False})
        for _ in range(2):
            response = self.client.put(url, headers=self.headers, json={"categories": ["tech"]})
            self.assertEqual(response.status_code, 200, response.text)
        # New ORM session and a fresh public read, rather than returning optimistic state.
        self.assertEqual(self.client.get(url, headers=self.headers).json(), {"categories": ["tech"], "completed": True})
        with self.sessions() as db:
            self.assertEqual(db.query(UserPreference).filter_by(user_id=self.user_id).count(), 1)
        self.assertEqual(self.client.get(url).status_code, 401)
        for invalid in (["wrong"], ["tech", "tech"], ["tech", "home", "beauty", "books"]):
            self.assertEqual(self.client.put(url, headers=self.headers, json={"categories": invalid}).status_code, 422)
        other_id = str(uuid.uuid4())
        with self.sessions() as db:
            db.add(User(id=other_id, email=other_id + "@example.com", is_active=True))
            db.commit()
        self.assertFalse(self.client.get(url, headers={"Authorization": "Bearer " + create_access_token(other_id)}).json()["completed"])

    def test_content_preferences_change_recommendations_after_fresh_read(self):
        url = "/api/v1/profile/preferences"
        self.client.put(url, headers=self.headers, json={"categories": ["tech"]})
        response = self.client.get("/api/v1/recommendations/feed?limit=10", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["segment"], "cold")
        self.assertTrue(all(item["c0_name"] == "Electronics" for item in response.json()["items"]))
        self.client.put(url, headers=self.headers, json={"categories": ["beauty"]})
        response = self.client.get("/api/v1/recommendations/feed?limit=10", headers=self.headers)
        self.assertTrue(all(item["c0_name"] == "Beauty" for item in response.json()["items"]))

    def test_cold_without_onboarding_uses_popularity_trending_only(self):
        response = self.client.get("/api/v1/recommendations/feed?limit=10", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["segment"], "cold")
        self.assertEqual(data["model_status"]["als"], "not_applicable")
        self.assertEqual(data["model_status"]["gru"], "not_applicable")
        self.assertEqual(data["model_status"]["twotower"], "not_applicable")

    def test_events_idempotency_validation_and_few_context(self):
        payload = {"item_id": "1", "event_type": "view", "session_id": str(uuid.uuid4()), "event_key": str(uuid.uuid4())}
        first = self.client.post("/api/v1/events", headers=self.headers, json=payload)
        second = self.client.post("/api/v1/events", headers=self.headers, json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json(), second.json())
        payload["item_id"] = "2"
        self.assertEqual(self.client.post("/api/v1/events", headers=self.headers, json=payload).status_code, 409)
        payload["event_type"] = "invalid"
        self.assertEqual(self.client.post("/api/v1/events", headers=self.headers, json=payload).status_code, 422)
        response = self.client.get("/api/v1/recommendations/feed?limit=10", headers=self.headers)
        self.assertEqual(response.json()["segment"], "few")
        self.assertNotIn("1", [item["id"] for item in response.json()["items"]])

    def test_return_home_after_three_interactions_uses_fresh_history(self):
        session = str(uuid.uuid4())
        url = f"/api/v1/recommendations/feed?context=home&session_id={session}&limit=10"
        initial = self.client.get(url, headers=self.headers)
        self.assertEqual(initial.status_code, 200, initial.text)
        old_ids = [item["id"] for item in initial.json()["items"]]
        for item_id in ("2", "3", "4"):
            receipt = self.client.post("/api/v1/events", headers=self.headers, json={
                "event_key": str(uuid.uuid4()), "session_id": session,
                "item_id": item_id, "event_type": "view", "source_page": "product_detail"
            })
            self.assertEqual(receipt.status_code, 200, receipt.text)
        refreshed = self.client.get(url, headers=self.headers)
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        data = refreshed.json()
        self.assertEqual(data["segment"], "session")
        self.assertEqual(data["ranker"], "hybrid_feature_ranker_v2")
        self.assertEqual(data["model_status"]["lightgbm"], "not_in_use")
        self.assertTrue(any(item["c0_name"] == "Electronics" for item in data["items"][:5]))
        self.assertNotEqual(old_ids[:5], [item["id"] for item in data["items"][:5]])
        self.assertFalse({"2", "3", "4"} & {item["id"] for item in data["items"]})
        # A new session object reads committed rows after a simulated server restart.
        with self.sessions() as db:
            self.assertEqual(db.query(UserEvent).filter(UserEvent.user_id == self.user_id).count(), 3)
            request = db.get(RecommendationRequest, data["request_id"])
            self.assertIsNotNone(request)
            self.assertEqual(request.user_id, self.user_id)
            self.assertEqual(db.query(RecommendationItem).filter_by(request_id=data["request_id"]).count(), len(data["items"]))

    def test_returning_user_with_active_session_routes_long_and_short_term_models(self):
        from scripts.online_models import retrievers_for

        payload = {"segment": "session", "session_distinct_count": 3, "history_distinct_count": 14,
                   "long_term_eligible": True}
        self.assertEqual(retrievers_for(payload), {"gru", "als", "twotower"})
        payload = {"segment": "cold", "session_distinct_count": 0, "history_distinct_count": 0,
                   "long_term_eligible": False}
        self.assertEqual(retrievers_for(payload), set())

    def test_recommendation_click_is_attributed_to_own_request(self):
        session = str(uuid.uuid4())
        result = self.client.get(f"/api/v1/recommendations/feed?session_id={session}&limit=10", headers=self.headers).json()
        item_id = result["items"][0]["id"]
        payload = {"item_id": item_id, "event_type": "click", "session_id": session,
                   "event_key": str(uuid.uuid4()), "recommendation_request_id": result["request_id"],
                   "position": 1, "source_page": "home"}
        receipt = self.client.post("/api/v1/events", headers=self.headers, json=payload)
        self.assertEqual(receipt.status_code, 200, receipt.text)
        with self.sessions() as db:
            event = db.query(UserEvent).filter_by(event_key=payload["event_key"]).one()
            self.assertEqual(event.recommendation_request_id, result["request_id"])
            self.assertEqual(event.position, 1)
            self.assertEqual(event.source_page, "home")
        other_id = str(uuid.uuid4())
        with self.sessions() as db:
            db.add(User(id=other_id, email=other_id + "@example.com", is_active=True))
            db.commit()
        other = {"Authorization": "Bearer " + create_access_token(other_id)}
        payload["session_id"] = str(uuid.uuid4())
        payload["event_key"] = str(uuid.uuid4())
        self.assertEqual(self.client.post("/api/v1/events", headers=other, json=payload).status_code, 403)

    def test_safe_dependency_failure_and_invalid_input(self):
        import subprocess
        with patch("backend.src.services.personalization_service.subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 40)):
            response = self.client.get("/api/v1/recommendations/feed", headers=self.headers)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("worker", response.text)
        self.assertEqual(self.client.get("/api/v1/recommendations/feed?limit=0").status_code, 422)
        self.assertEqual(self.client.get("/api/v1/recommendations/feed?context=invalid").status_code, 422)
        self.assertEqual(self.client.get("/api/v1/recommendations/feed", headers={"Authorization": "Bearer invalid"}).status_code, 401)
        with patch("backend.src.api.profile.read_preferences", side_effect=OperationalError("private SQL", {}, Exception("secret"))):
            response = self.client.get("/api/v1/profile/preferences", headers=self.headers)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("secret", response.text)

    def test_google_rejects_unverified_identity_and_missing_state(self):
        response = self.client.post("/api/v1/auth/google", json={"email": "fake@example.com", "google_id": "fake"})
        self.assertEqual(response.status_code, 401)
        response = self.client.get("/auth/google/callback?code=fake", follow_redirects=False)
        self.assertEqual(response.status_code, 400)

    def test_verified_google_new_and_returning_account(self):
        claims = {"sub": str(uuid.uuid4()), "email": str(uuid.uuid4()) + "@gmail.com", "name": "Google Test"}
        with patch("backend.src.services.google_identity.verify_google_token", return_value=claims):
            first = self.client.post("/api/v1/auth/google", json={"id_token": "isolated-google-boundary"})
            second = self.client.post("/api/v1/auth/google", json={"id_token": "isolated-google-boundary"})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["user_id"], second.json()["user_id"])
        headers = {"Authorization": "Bearer " + second.json()["access_token"]}
        self.assertFalse(self.client.get("/api/v1/profile/preferences", headers=headers).json()["completed"])


if __name__ == "__main__":
    unittest.main()
