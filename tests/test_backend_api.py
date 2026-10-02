import os
import sys
import uuid
import unittest
from pathlib import Path

# Force SQLite in-memory database for unit tests
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from backend.src.main import app

client = TestClient(app)


class BackendApiTests(unittest.TestCase):
    def test_root_health_check(self):
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

        root_res = client.get("/")
        self.assertEqual(root_res.status_code, 200)
        self.assertIn("message", root_res.json())

    def test_products_list_api(self):
        response = client.get("/api/v1/products?page_size=5")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("products", data)
        self.assertIn("total", data)

    def test_product_detail_api(self):
        sample_id = "86680698"
        response = client.get(f"/api/v1/products/{sample_id}")
        if response.status_code == 200:
            p = response.json()
            self.assertEqual(p["item_id"], sample_id)

    def test_categories_and_brands_api(self):
        res = client.get("/api/v1/products/meta/categories-and-brands")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("categories", data)
        self.assertIn("brands", data)

    def test_recommendations_api(self):
        response = client.get("/api/v1/recommendations?context=home&limit=6")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("recommendations", data)
        self.assertIn("algorithm", data)

    def test_events_tracking_api(self):
        payload = {
            "item_id": "86680698",
            "event_type": "view_item",
            "session_id": "test_session_123"
        }
        response = client.post("/api/v1/events", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

    def test_orders_creation_api(self):
        payload = {
            "full_name": "Test Customer",
            "email": "customer@example.com",
            "phone": "0912345678",
            "address": "123 Test Street",
            "payment_method": "cod",
            "shipping_fee": 15.0,
            "items": [
                {
                    "item_id": "86680698",
                    "product_name": "Kwik Sew Pattern",
                    "quantity": 1,
                    "unit_price": 25.5
                }
            ]
        }
        response = client.post("/api/v1/orders", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["total_amount"], 40.5)

    def test_local_registration_and_login(self):
        unique_email = f"test_user_{uuid.uuid4().hex[:8]}@example.com"
        reg_payload = {
            "full_name": "Test Suite User",
            "email": unique_email,
            "password": "Password123!"
        }
        reg_res = client.post("/api/v1/auth/register", json=reg_payload)
        self.assertEqual(reg_res.status_code, 201)

        login_payload = {
            "email": unique_email,
            "password": "Password123!"
        }
        login_res = client.post("/api/v1/auth/login", json=login_payload)
        self.assertEqual(login_res.status_code, 200)
        token_data = login_res.json()
        self.assertIn("access_token", token_data)

    def test_google_oauth_endpoint(self):
        google_payload = {
            "email": f"google_user_{uuid.uuid4().hex[:8]}@gmail.com",
            "full_name": "Google Test User",
            "google_id": f"google-{uuid.uuid4().hex[:8]}"
        }
        res = client.post("/api/v1/auth/google", json=google_payload)
        self.assertEqual(res.status_code, 200)
        self.assertIn("access_token", res.json())

    def test_google_oauth_callback_endpoint(self):
        res = client.get("/auth/google/callback?code=mock-authorization-code-123", follow_redirects=False)
        self.assertIn(res.status_code, (302, 307))
        self.assertIn("/login?token=", res.headers["location"])

    def test_admin_dashboard_stats_api(self):
        res = client.get("/api/v1/admin/stats")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_revenue", data)
        self.assertIn("total_orders", data)


if __name__ == "__main__":
    unittest.main()
