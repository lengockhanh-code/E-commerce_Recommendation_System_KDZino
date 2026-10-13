import datetime as dt
import os
import subprocess
import unittest
import uuid
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from tests.test_personalization import PersonalizationTests
from backend.src.models.orm import RecommendationRequest, RecommendationItem, UserEvent, User
from backend.src.security.jwt import create_access_token
from backend.src.services.recommendation_experiment import assignment, parse_cursor, utc_datetime, resolve_feed_cursor
from scripts.report_recommendation_ab import summarize, report


class ExperimentAssignmentTests(unittest.TestCase):
    def test_utc_plus_seven_keeps_the_instant_and_does_not_extend_feed_ttl(self):
        from types import SimpleNamespace
        from fastapi import HTTPException
        local_zone = dt.timezone(dt.timedelta(hours=7))
        now = dt.datetime.now(dt.timezone.utc)
        self.assertEqual(utc_datetime(now.astimezone(local_zone)), now)
        root_id, session = str(uuid.uuid4()), str(uuid.uuid4())
        root = SimpleNamespace(id=root_id, user_id=None, session_id=session, context="home",
            generated_at=(now - dt.timedelta(hours=7)).astimezone(local_zone))
        db = SimpleNamespace(get=lambda *_: root)
        with self.assertRaises(HTTPException) as raised:
            resolve_feed_cursor(db, root_id + ":0", None, session)
        self.assertEqual(raised.exception.status_code, 410)

    def test_assignment_is_stable_and_grouping_not_session_based(self):
        with patch.dict(os.environ, {"MERREC_AB_ENABLED": "1", "MERREC_AB_EXPERIMENT": "test"}):
            guest = str(uuid.uuid4())
            self.assertEqual(assignment(anonymous_id=guest), assignment(anonymous_id=guest))
            values = [assignment(user_id=str(i))["variant"] for i in range(1000)]
            self.assertTrue(400 < values.count("A") < 600)
            self.assertIsNone(assignment(user_id="x", context="cart"))

    def test_bad_cursor_is_rejected(self):
        from fastapi import HTTPException
        for value in ("invalid", f"{uuid.uuid4()}:-1", f"{uuid.uuid4()}:2147483648"):
            with self.assertRaises(HTTPException):
                parse_cursor(value)

    def test_report_counts_only_exposed_unique_clicks_in_window(self):
        now = dt.datetime.now(dt.timezone.utc)
        def event(kind, seconds=0, item="1"):
            return dict(experiment="test", variant="A", subject="user:1", request_id="r", item_id=item,
                        event_type=kind, time=now + dt.timedelta(seconds=seconds))
        result = summarize([event("impression"), event("impression"), event("click", 1),
                            event("click", 2), event("click", 3, "unshown"), event("cart", 1801)], "test")
        self.assertEqual(result["groups"]["A"]["impressions"], 1)
        self.assertEqual(result["groups"]["A"]["clicked_impressions"], 1)
        self.assertEqual(result["groups"]["A"]["cart_impressions"], 0)
        self.assertIsNone(result["groups"]["B"]["CTR"])


class RecommendationExperimentIntegrationTests(PersonalizationTests):
    def test_interest_refresh_does_not_exhaust_a_small_unseen_catalog(self):
        session = str(uuid.uuid4())
        url = f"/api/v1/recommendations/feed?session_id={session}&limit=12"
        first = self.client.get(url, headers=self.headers).json()
        # All 80 fixture products fit in a 240-item draft, only 12 were returned.
        receipt = self.client.post("/api/v1/events", headers=self.headers, json=dict(
            item_id=first["items"][0]["id"], event_type="view", session_id=session, event_key=str(uuid.uuid4())))
        self.assertEqual(receipt.status_code, 200, receipt.text)
        with patch("backend.src.services.personalization_service.subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 40)):
            failed = self.client.get(url + "&cursor=" + first["next_cursor"], headers=self.headers)
        self.assertEqual(failed.status_code, 503)
        with self.sessions() as db:
            self.assertEqual(db.query(RecommendationItem).filter_by(request_id=first["request_id"]).count(), 80)
        response = self.client.get(url + "&cursor=" + first["next_cursor"], headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["items"]), 12)
        self.assertFalse({i["id"] for i in first["items"]} & {i["id"] for i in response.json()["items"]})
        with self.sessions() as db:
            saved = db.query(RecommendationItem).filter_by(request_id=first["request_id"]).all()
            self.assertEqual(len(saved), 12)
            self.assertEqual(db.query(UserEvent).filter_by(user_id=self.user_id).count(), 1)

    def test_unliked_item_does_not_keep_recent_gru_eligibility(self):
        session = str(uuid.uuid4())
        self._persist_recent_views(session, self.headers)
        receipt = self.client.post("/api/v1/events", headers=self.headers, json=dict(
            item_id="4", event_type="unlike", session_id=session, event_key=str(uuid.uuid4())))
        self.assertEqual(receipt.status_code, 200, receipt.text)
        response = self.client.get(f"/api/v1/recommendations/feed?session_id={session}", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["model_status"]["gru"], "not_applicable")

    def test_identified_guest_can_use_long_term_models_without_login(self):
        anonymous, session = str(uuid.uuid4()), str(uuid.uuid4())
        response = self.client.get(f"/api/v1/recommendations/feed?session_id={session}&anonymous_id={anonymous}")
        self.assertEqual(response.status_code, 200, response.text)
        with self.sessions() as db:
            for i in range(10):
                db.add(UserEvent(session_id=session, item_id=str(i), event_type="like",
                    created_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=14)))
            db.commit()
        original_run = subprocess.run
        with patch("backend.src.services.personalization_service.subprocess.run", wraps=original_run) as worker:
            response = self.client.get(f"/api/v1/recommendations/feed?session_id={uuid.uuid4()}&anonymous_id={anonymous}")
        self.assertEqual(response.status_code, 200, response.text)
        import json
        payload = json.loads(worker.call_args.kwargs["input"])
        self.assertIsNone(payload["user_id"])
        self.assertEqual(payload["segment"], "warm")
        self.assertTrue(payload["long_term_eligible"])
        from scripts.online_models import retrievers_for
        self.assertEqual(retrievers_for(payload), {"als", "twotower"})

    def test_new_activity_refreshes_only_next_page_and_retry_reuses_it(self):
        with patch("backend.src.services.personalization_service.SNAPSHOT_SIZE", 24), \
             patch("backend.src.services.recommendation_experiment.SNAPSHOT_SIZE", 24):
            session = str(uuid.uuid4())
            url = f"/api/v1/recommendations/feed?session_id={session}&limit=12"
            first = self.client.get(url, headers=self.headers).json()
            for item_id in ("2", "3", "4"):
                event = self.client.post("/api/v1/events", headers=self.headers, json=dict(
                    item_id=item_id, event_type="view", session_id=session, event_key=str(uuid.uuid4())))
                self.assertEqual(event.status_code, 200, event.text)
            response = self.client.get(url + "&cursor=" + first["next_cursor"], headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()
            self.assertNotEqual(data["request_id"], first["request_id"])
            self.assertEqual(sum(item["c1_name"] == "Phone" for item in data["items"]), 9)
            self.assertFalse({i["id"] for i in first["items"]} & {i["id"] for i in data["items"]})
            with patch("backend.src.services.personalization_service.subprocess.run", side_effect=AssertionError("must reuse refreshed block")):
                retry = self.client.get(url + "&cursor=" + first["next_cursor"], headers=self.headers)
            self.assertEqual(retry.status_code, 200, retry.text)
            self.assertEqual(retry.json()["items"], data["items"])
            with self.sessions() as db:
                old = db.query(RecommendationItem).filter_by(request_id=first["request_id"]).order_by(RecommendationItem.rank_position).limit(12).all()
                self.assertEqual([item.item_id for item in old], [i["id"] for i in first["items"]])

    def test_long_history_is_retained_when_recent_gru_history_is_selected(self):
        old_session = str(uuid.uuid4())
        initial = self.client.get(f"/api/v1/recommendations/feed?session_id={old_session}", headers=self.headers)
        self.assertEqual(initial.status_code, 200, initial.text)
        with self.sessions() as db:
            for i in range(40, 52):
                db.add(UserEvent(user_id=self.user_id, session_id=old_session, item_id=str(i), event_type="like",
                    created_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=14)))
            db.commit()
        self._persist_recent_views(old_session, self.headers)
        original_run = subprocess.run
        with patch("backend.src.services.personalization_service.subprocess.run", wraps=original_run) as worker:
            response = self.client.get(f"/api/v1/recommendations/feed?session_id={uuid.uuid4()}", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        import json
        payload = json.loads(worker.call_args.kwargs["input"])
        self.assertEqual(len(payload["history"]), 15)
        self.assertEqual(len(payload["recent_history"]), 3)
        self.assertTrue(payload["long_term_eligible"])
        from scripts.online_models import retrievers_for
        self.assertEqual(retrievers_for(payload), {"gru", "als", "twotower"})
        self.assertGreaterEqual(sum(item["c1_name"] == "Phone" for item in response.json()["items"][:12]), 9)

    def _persist_recent_views(self, session, headers=None):
        for index, item_id in enumerate(("2", "3", "4")):
            response = self.client.post("/api/v1/events", headers=headers or {}, json=dict(
                item_id=item_id, event_type="view", session_id=session, event_key=str(uuid.uuid4())))
            self.assertEqual(response.status_code, 200, response.text)
            with self.sessions() as db:
                event = db.get(UserEvent, response.json()["event_id"])
                event.created_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2, minutes=3-index)
                db.commit()

    def test_returning_account_uses_recent_gru_history_from_previous_session(self):
        old_session = str(uuid.uuid4())
        self._persist_recent_views(old_session, self.headers)
        new_session = str(uuid.uuid4())
        original_run = subprocess.run
        with patch("backend.src.services.personalization_service.subprocess.run", wraps=original_run) as worker:
            response = self.client.get(f"/api/v1/recommendations/feed?session_id={new_session}", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        import json
        payload = json.loads(worker.call_args.kwargs["input"])
        self.assertEqual(payload["session_distinct_count"], 0)
        self.assertEqual(payload["recent_distinct_count"], 3)
        self.assertEqual([e["item_id"] for e in payload["history"]], ["2", "3", "4"])
        self.assertEqual(response.json()["segment"], "session")
        from scripts.online_models import retrievers_for
        self.assertIn("gru", retrievers_for(payload))

    def test_returning_guest_reuses_only_own_browser_history(self):
        anonymous, old_session = str(uuid.uuid4()), str(uuid.uuid4())
        initial = self.client.get(f"/api/v1/recommendations/feed?session_id={old_session}&anonymous_id={anonymous}")
        self.assertEqual(initial.status_code, 200, initial.text)
        self._persist_recent_views(old_session)
        response = self.client.get(f"/api/v1/recommendations/feed?session_id={uuid.uuid4()}&anonymous_id={anonymous}")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["segment"], "session")
        other = self.client.get(f"/api/v1/recommendations/feed?session_id={uuid.uuid4()}&anonymous_id={uuid.uuid4()}")
        self.assertEqual(other.status_code, 200, other.text)
        self.assertEqual(other.json()["segment"], "cold")

    def test_stale_and_impression_only_history_do_not_activate_gru(self):
        old_session = str(uuid.uuid4())
        self._persist_recent_views(old_session, self.headers)
        with self.sessions() as db:
            for event in db.query(UserEvent).filter_by(user_id=self.user_id).all():
                event.created_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8)
            db.commit()
        response = self.client.get(f"/api/v1/recommendations/feed?session_id={uuid.uuid4()}", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["model_status"]["gru"], "not_applicable")
        data = response.json()
        for item in data["items"][:3]:
            impression = self.client.post("/api/v1/events", headers=self.headers, json=dict(
                item_id=item["id"], event_type="impression", recommendation_request_id=data["request_id"],
                position=item["position"], session_id=data.get("session_id"), event_key=str(uuid.uuid4())))
            self.assertEqual(impression.status_code, 200, impression.text)
        after = self.client.get(f"/api/v1/recommendations/feed?session_id={uuid.uuid4()}", headers=self.headers)
        self.assertEqual(after.status_code, 200, after.text)
        self.assertEqual(after.json()["model_status"]["gru"], "not_applicable")
        from scripts.online_models import retrievers_for
        self.assertNotIn("gru", retrievers_for({"recent_distinct_count": 0, "session_distinct_count": 3, "segment": "session"}))

    def test_home_discovers_other_categories_when_preferred_candidates_exhausted(self):
        self.client.put("/api/v1/profile/preferences", headers=self.headers, json={"categories": ["tech"]})
        excludes = ",".join(str(i) for i in range(40))
        response = self.client.get("/api/v1/recommendations/feed?exclude=" + excludes, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["items"])
        self.assertTrue(all(item["c0_name"] == "Beauty" for item in response.json()["items"]))

    def test_feed_retrieves_new_blocks_without_repeats_and_retries_persisted_block(self):
        with patch.dict(os.environ, {"MERREC_AB_ENABLED": "1"}), \
             patch("backend.src.services.personalization_service.SNAPSHOT_SIZE", 24), \
             patch("backend.src.services.recommendation_experiment.SNAPSHOT_SIZE", 24):
            url = f"/api/v1/recommendations/feed?session_id={uuid.uuid4()}&limit=12"
            first = self.client.get(url, headers=self.headers)
            self.assertEqual(first.status_code, 200, first.text)
            root = first.json()
            cursor = root["next_cursor"]
            seen = {item["id"] for item in root["items"]}
            request_ids = {root["request_id"]}
            continuation_cursor = None
            continuation = None
            for _ in range(12):
                if cursor.endswith(":24"):
                    with patch("backend.src.services.personalization_service.subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 40)):
                        failed = self.client.get(url + "&cursor=" + cursor, headers=self.headers)
                    self.assertEqual(failed.status_code, 503)
                response = self.client.get(url + "&cursor=" + cursor, headers=self.headers)
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                ids = {item["id"] for item in data["items"]}
                self.assertFalse(ids & seen)
                seen.update(ids)
                self.assertEqual(data["experiment"], root["experiment"])
                request_ids.add(data["request_id"])
                if data["items"] and data["request_id"] != root["request_id"] and continuation is None:
                    continuation_cursor, continuation = cursor, data
                if not data["has_more"]:
                    self.assertEqual(data["items"], [])
                    break
                cursor = data["next_cursor"]
            else:
                self.fail("fixture feed did not exhaust")
            self.assertEqual(len(seen), 80)
            self.assertGreater(len(request_ids), 2)
            with patch("backend.src.services.personalization_service.subprocess.run", side_effect=AssertionError("must reuse saved block")):
                retry = self.client.get(url + "&cursor=" + continuation_cursor, headers=self.headers)
            self.assertEqual(retry.status_code, 200, retry.text)
            for field in ("request_id", "items", "next_cursor", "experiment"):
                self.assertEqual(retry.json()[field], continuation[field])
            item = continuation["items"][0]
            event = self.client.post("/api/v1/events", headers=self.headers, json=dict(
                item_id=item["id"], event_type="impression", recommendation_request_id=continuation["request_id"],
                position=item["position"], event_key=str(uuid.uuid4())))
            self.assertEqual(event.status_code, 200, event.text)

    def test_real_rankers_pages_impressions_and_persisted_report(self):
        with patch.dict(os.environ, {"MERREC_AB_ENABLED": "1"}):
            for group, expected in (("A", "dcn"), ("B", "lightgbm")):
                while True:
                    user_id = str(uuid.uuid4())
                    if assignment(user_id)["variant"] == group:
                        break
                with self.sessions() as db:
                    db.add(User(id=user_id, email=user_id + "@example.com", is_active=True))
                    db.commit()
                headers = {"Authorization": "Bearer " + create_access_token(user_id)}
                session = str(uuid.uuid4())
                url = f"/api/v1/recommendations/feed?session_id={session}&limit=12"
                response = self.client.get(url, headers=headers)
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                self.assertEqual(data["experiment"]["variant"], group)
                self.assertEqual(data["ranker"], expected)
                self.assertEqual(data["model_status"][expected], "ready")
                self.assertTrue(data["has_more"])
                # Fresh API read uses PostgreSQL-shaped persisted rows, no worker or model rerun.
                with patch("backend.src.services.personalization_service.subprocess.run", side_effect=AssertionError("must not rerun")):
                    next_page = self.client.get(url + "&cursor=" + data["next_cursor"], headers=headers)
                self.assertEqual(next_page.status_code, 200, next_page.text)
                self.assertEqual(next_page.json()["request_id"], data["request_id"])
                self.assertFalse(set(i["id"] for i in data["items"]) & set(i["id"] for i in next_page.json()["items"]))
                item = next_page.json()["items"][0]
                payload = dict(item_id=item["id"], event_type="impression", session_id=session,
                    recommendation_request_id=data["request_id"], position=item["position"], event_key=str(uuid.uuid4()),
                    extra_data={"recommendation_experiment": {"variant": "forged"}})
                first = self.client.post("/api/v1/events", headers=headers, json=payload)
                self.assertEqual(first.status_code, 200, first.text)
                payload["event_key"] = str(uuid.uuid4())
                again = self.client.post("/api/v1/events", headers=headers, json=payload)
                self.assertEqual(first.json(), again.json())
                payload.update(event_type="click", event_key=str(uuid.uuid4()))
                self.assertEqual(self.client.post("/api/v1/events", headers=headers, json=payload).status_code, 200)
                with self.sessions() as db:
                    self.assertEqual(db.query(UserEvent).filter_by(recommendation_request_id=data["request_id"], event_type="impression").count(), 1)
                    saved = db.query(UserEvent).filter_by(recommendation_request_id=data["request_id"], event_type="impression").one()
                    self.assertEqual(saved.extra_data["recommendation_experiment"]["variant"], group)
                    # Impression must not make a cold user appear warm/few.
                    self.assertEqual(db.query(UserEvent).filter_by(user_id=user_id, event_type="view").count(), 0)
                    self.assertEqual(report(db, data["experiment"]["id"])["groups"][group]["clicked_impressions"], 1)
                payload["position"] = 2000
                payload["event_key"] = str(uuid.uuid4())
                self.assertEqual(self.client.post("/api/v1/events", headers=headers, json=payload).status_code, 422)
                self.assertEqual(self.client.get(url + "&cursor=" + data["next_cursor"], headers=self.headers).status_code, 403)

    def test_guest_assignment_survives_session_and_cursor_ownership(self):
        with patch.dict(os.environ, {"MERREC_AB_ENABLED": "1"}):
            anonymous = str(uuid.uuid4())
            sessions = [str(uuid.uuid4()), str(uuid.uuid4())]
            responses = [self.client.get(f"/api/v1/recommendations/feed?anonymous_id={anonymous}&session_id={s}&limit=3") for s in sessions]
            self.assertTrue(all(r.status_code == 200 for r in responses), [r.text for r in responses])
            self.assertEqual(responses[0].json()["experiment"], responses[1].json()["experiment"])
            cursor = responses[0].json()["next_cursor"]
            self.assertEqual(self.client.get(f"/api/v1/recommendations/feed?cursor={cursor}&session_id={sessions[1]}").status_code, 403)
            self.assertEqual(self.client.get("/api/v1/recommendations/feed?cursor=bad").status_code, 422)
            with self.sessions() as db:
                request = db.get(RecommendationRequest, responses[0].json()["request_id"])
                request.generated_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
                db.commit()
            self.assertEqual(self.client.get(f"/api/v1/recommendations/feed?cursor={cursor}&session_id={sessions[0]}").status_code, 410)

    def test_impression_without_delivered_recommendation_fails(self):
        response = self.client.post("/api/v1/events", headers=self.headers,
            json={"item_id": "1", "event_type": "impression"})
        self.assertEqual(response.status_code, 422)

    def test_empty_candidates_are_an_empty_feed_not_a_ranker_failure(self):
        with patch.dict(os.environ, {"MERREC_AB_ENABLED": "1"}):
            excludes = ",".join(str(i) for i in range(80))
            response = self.client.get("/api/v1/recommendations/feed?exclude=" + excludes, headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["items"], [])
            self.assertFalse(response.json()["has_more"])

    def test_missing_experiment_model_fails_safely_without_rules_fallback(self):
        with patch.dict(os.environ, {"MERREC_AB_ENABLED": "1", "MERREC_AB_DCN_PATH": "missing-ab-checkpoint.pt"}):
            while True:
                user_id = str(uuid.uuid4())
                if assignment(user_id)["variant"] == "A":
                    break
            with self.sessions() as db:
                db.add(User(id=user_id, email=user_id + "@example.com", is_active=True))
                db.commit()
            headers = {"Authorization": "Bearer " + create_access_token(user_id)}
            response = self.client.get("/api/v1/recommendations/feed", headers=headers)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("checkpoint", response.text)
            with self.sessions() as db:
                self.assertEqual(db.query(RecommendationRequest).filter_by(user_id=user_id).count(), 0)


if __name__ == "__main__":
    unittest.main()
