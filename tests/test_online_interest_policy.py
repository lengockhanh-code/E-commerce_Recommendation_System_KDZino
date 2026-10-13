import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.personalized_recommendations import interest_profile, interest_affinity, interest_focus, rerank


class InterestPolicyTests(unittest.TestCase):
    def test_missing_metadata_is_not_a_fake_interest_category(self):
        metadata = {key: (key, "__UNK__", "__UNK__", "__UNK__", key, "__UNK__") for key in ("a", "b")}
        events = [dict(item_id=key, event_type="view", age_hours=0) for key in metadata]
        profile = interest_profile(events, metadata, 24)
        self.assertIsNone(interest_focus(profile))
        self.assertEqual(interest_affinity(self.phone, profile), 0)

    def test_known_subcategory_can_work_when_parent_metadata_is_missing(self):
        metadata = {key: (key, "__UNK__", "Phone", "__UNK__", key, "Mobile") for key in ("a", "b")}
        events = [dict(item_id=key, event_type="view", age_hours=0) for key in metadata]
        profile = interest_profile(events, metadata, 24)
        self.assertEqual(interest_focus(profile), dict(fields=("category1",), values=("Phone",)))
        self.assertGreater(interest_affinity(self.phone, profile), interest_affinity(self.beauty, profile))

    def test_new_user_history_query_changes_with_interest_and_honors_unlike(self):
        import faiss
        import numpy as np
        from scripts.online_models import history_item_query
        index = faiss.IndexFlatIP(2)
        index.add(np.asarray([[1, 0], [0, 1]], dtype=np.float32))
        mapping = {"a": 0, "b": 1}
        first = history_item_query(index, [dict(item_id="b", event_type="view", age_hours=720),
            dict(item_id="a", event_type="cart", age_hours=0)], mapping)
        second = history_item_query(index, [dict(item_id="a", event_type="view", age_hours=720),
            dict(item_id="b", event_type="cart", age_hours=0)], mapping)
        self.assertGreater(first[0], first[1])
        self.assertGreater(second[1], second[0])
        self.assertIsNone(history_item_query(index, [dict(item_id="unknown", event_type="view", age_hours=0)], mapping))
        self.assertIsNone(history_item_query(index, [dict(item_id="a", event_type="view", age_hours=1),
            dict(item_id="a", event_type="unlike", age_hours=0)], mapping))

    def test_ann_indices_are_mapped_to_ids_and_scoring_reuses_the_recall(self):
        import duckdb
        from scripts import online_models
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mapping = root / "TwoTower/mappings/train_item_map.parquet"
            mapping.parent.mkdir(parents=True)
            with duckdb.connect() as db:
                db.execute("COPY (SELECT 'a' item_id, 2 item_idx UNION ALL SELECT 'b', 7) TO ? (FORMAT PARQUET)", [str(mapping)])
            with patch.object(online_models, "ARTIFACTS", root), patch.object(online_models, "_twotower_ann", return_value=({7: .8, 2: .9}, "ready")) as ann:
                recalled, status = online_models.twotower_candidates({})
                self.assertEqual(recalled, {"a": .9, "b": .8})
                payload = dict(recent_distinct_count=3, history=[], twotower_recall_scores=recalled, twotower_recall_status=status)
                with patch.object(online_models, "twotower_scores", side_effect=AssertionError("must reuse ANN scores")), \
                     patch.object(online_models, "gru_scores", return_value=({}, "unmapped_history")):
                    scores, statuses = online_models.score_retrievers([dict(item_id="b")], payload)
                self.assertEqual(scores["twotower"], {"b": .8})
                self.assertEqual(statuses["twotower"], "ready")
                self.assertEqual(ann.call_count, 1)

    def setUp(self):
        self.metadata = {
            "phone1": ("phone1", "Electronics", "Phone", "Brand", "Phone", "Mobile"),
            "phone2": ("phone2", "Electronics", "Phone", "Brand", "Phone", "Mobile"),
            "beauty": ("beauty", "Beauty", "Skincare", "Brand", "Cream", "Face"),
        }
        self.phone = dict(category0="Electronics", category1="Phone", category2="Mobile", brand="Brand")
        self.beauty = dict(category0="Beauty", category1="Skincare", category2="Face", brand="Brand")

    def test_recent_interest_outweighs_old_interest_while_long_history_keeps_both(self):
        events = [dict(item_id="beauty", event_type="cart", age_hours=144),
                  dict(item_id="phone1", event_type="view", age_hours=1),
                  dict(item_id="phone2", event_type="like", age_hours=0)]
        recent = interest_profile(events, self.metadata, 24)
        long_term = interest_profile(events, self.metadata, 720)
        self.assertGreater(interest_affinity(self.phone, recent), interest_affinity(self.beauty, recent))
        self.assertGreater(interest_affinity(self.beauty, long_term), interest_affinity(self.beauty, recent))
        self.assertEqual(interest_focus(recent)["values"], ("Electronics", "Phone"))

    def test_repeated_view_and_click_on_one_item_do_not_create_false_focus(self):
        events = [dict(item_id="phone1", event_type=kind, age_hours=0) for kind in ("view", "click", "view", "click")]
        profile = interest_profile(events, self.metadata, 24)
        self.assertEqual(profile["distinct_items"], 1)
        self.assertIsNone(interest_focus(profile))

    def test_conflicting_interests_do_not_force_one_category(self):
        events = [dict(item_id=item, event_type="view", age_hours=0) for item in ("phone1", "beauty")]
        self.assertIsNone(interest_focus(interest_profile(events, self.metadata, 24)))

    def test_focused_pages_keep_recent_interest_and_a_small_exploration_share(self):
        rows = [dict(id=str(i), name=f"Unique phone {i}", category0="Electronics", category1="Phone", brand="Brand") for i in range(24)]
        rows += [dict(id=str(i+100), name=f"Cream {i}", category0="Beauty", category1="Skincare", brand="Other") for i in range(12)]
        selected = rerank(rows, [.2]*24 + [.99]*12, 24, dict(fields=("category0", "category1"), values=("Electronics", "Phone")))
        for start in (0, 12):
            self.assertEqual(sum(row["category1"] == "Phone" for row, _ in selected[start:start+12]), 9)
        self.assertEqual(len({row["id"] for row, _ in selected}), 24)

    def test_exhausted_focus_does_not_hide_available_products(self):
        rows = [dict(id=str(i), name=str(i), category0="Beauty", category1="Skincare", brand="Other") for i in range(15)]
        selected = rerank(rows, [.5]*15, 12, dict(fields=("category0",), values=("Electronics",)))
        self.assertEqual(len(selected), 12)


if __name__ == "__main__":
    unittest.main()
