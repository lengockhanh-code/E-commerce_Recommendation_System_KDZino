import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import storefront_images as images


class StorefrontImageTests(unittest.TestCase):
    def test_reference_fallback_is_labeled_and_never_saved_as_product_image(self):
        reference = [{"url": "https://example.com/handlebar.jpg", "reference": True}]
        with tempfile.TemporaryDirectory() as directory, patch.object(images, "DB_PATH", Path(directory) / "images.sqlite3"), patch.object(images, "read_postgres_images", return_value=None), patch.object(images, "reference_images", return_value=reference):
            result = images.resolve_images({"id": "reference-only"}, Mock(side_effect=TimeoutError))
            self.assertEqual(result, reference)
            self.assertIsNone(images.read_images("reference-only"))
            with images.connect() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM image_outbox").fetchone()[0], 0)

    def test_dns_failure_rejects_unverified_hosts(self):
        with patch.object(images.socket, "getaddrinfo", side_effect=OSError):
            self.assertFalse(images.public_url("https://example.com/image.jpg"))

    def test_saved_images_do_not_wait_for_database_recovery(self):
        saved = [{"url": "https://example.com/saved.jpg"}]
        with patch.object(images, "read_images", return_value=saved), patch.object(images, "sync_postgres") as sync:
            search = Mock()
            self.assertEqual(images.resolve_images({"id": "saved"}, search), saved)
            search.assert_not_called()
            sync.assert_not_called()

    def test_search_tries_second_provider_after_timeout(self):
        from scripts.storefront_catalog import search_images
        candidate = {"image": "https://example.com/handlebar.jpg", "title": "BMX chrome handlebars", "url": "https://example.com/product"}
        with patch("ddgs.DDGS") as ddgs:
            ddgs.return_value.images.side_effect = [TimeoutError(), [candidate]]
            result = search_images({"name": "BMX chrome handlebars", "brand": "Others Follow", "c1_name": "Outdoors"})
        self.assertEqual(result[0]["url"], candidate["image"])
        calls = ddgs.return_value.images.call_args_list
        self.assertEqual([c.kwargs["backend"] for c in calls], ["bing", "duckduckgo"])
        self.assertEqual(calls[1].args[0], "BMX chrome handlebars")

    def test_all_search_providers_failing_is_retryable(self):
        from scripts.storefront_catalog import search_images
        with patch("ddgs.DDGS") as ddgs:
            ddgs.return_value.images.side_effect = TimeoutError()
            with self.assertRaises(RuntimeError):
                search_images({"name": "BMX handlebars"})
            self.assertEqual(ddgs.return_value.images.call_count, 2)

    def test_only_two_valid_images_are_returned_saved_and_reused(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(images, "DB_PATH", Path(directory) / "images.sqlite3"), patch.object(images, "sync_postgres", return_value=False):
            item = {"id": "123", "name": "Product", "price": 9}
            candidates = [{"url": f"https://example.com/{i}.jpg", "title": str(i), "source": "", "score": 0.8} for i in range(5)]
            search = Mock(return_value=candidates)
            with patch.object(images, "valid_image", side_effect=lambda image: image["title"] in ("0", "3")):
                result = images.resolve_images(item, search)
            self.assertEqual([image["title"] for image in result], ["0", "3"])
            self.assertEqual(images.read_images("123"), result)
            with images.connect() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM image_outbox").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT count(*) FROM verified_images").fetchone()[0], 2)
            self.assertEqual(images.resolve_images(item, search), result)
            search.assert_called_once()

    def test_all_failed_images_are_not_persisted(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(images, "DB_PATH", Path(directory) / "images.sqlite3"), patch.object(images, "sync_postgres", return_value=False), patch.object(images, "valid_image", return_value=False):
            result = images.resolve_images({"id": "456"}, lambda _: [{"url": "https://example.com/broken.jpg"}])
            self.assertEqual(result, [])
            self.assertEqual(images.read_images("456"), [])

    def test_private_image_hosts_are_rejected(self):
        with patch.object(images.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            self.assertFalse(images.public_url("https://localhost/image.jpg"))
        self.assertFalse(images.valid_image({"url": "file:///secret"}))

    def test_empty_result_expires_and_success_replaces_marker(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(images, "DB_PATH", Path(directory) / "images.sqlite3"), patch.object(images, "read_postgres_images", return_value=None), patch.object(images, "sync_postgres", return_value=False):
            item = {"id": "retry", "name": "Product", "price": 1}
            with patch.object(images.time, "time", return_value=100):
                images.save_images(item, [])
                self.assertEqual(images.read_images(item["id"]), [])
            candidate = {"url": "https://example.com/good.jpg", "title": "Product", "source": "", "score": 1}
            with patch.object(images.time, "time", return_value=100 + images.EMPTY_RESULT_TTL_SECONDS), patch.object(images, "valid_image", return_value=True):
                self.assertIsNone(images.read_images(item["id"]))
                self.assertEqual(images.resolve_images(item, lambda _: [candidate]), [candidate])
            self.assertEqual(images.read_images(item["id"]), [candidate])
            with images.connect() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM verified_images WHERE url='EMPTY_NO_IMAGE'").fetchone()[0], 0)

    def test_search_failure_is_retryable_without_saving_empty_result(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(images, "DB_PATH", Path(directory) / "images.sqlite3"), patch.object(images, "read_postgres_images", return_value=None):
            with self.assertRaises(RuntimeError):
                images.resolve_images({"id": "offline"}, Mock(side_effect=TimeoutError))
            self.assertIsNone(images.read_images("offline"))


if __name__ == "__main__":
    unittest.main()
