import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import storefront_images as images


class StorefrontImageTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
