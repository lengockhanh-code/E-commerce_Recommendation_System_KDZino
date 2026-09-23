# Product image persistence

`scripts/storefront_images.py` checks HTTPS image candidates with a bounded download
and image decoding before storing the successful URLs. The browser also preloads
images and omits thumbnails that cannot load.

Verified URLs are stored durably in `data/storefront/product_images.sqlite3`.
`verified_images` stores the URL, source, score, order and verification time;
`image_outbox` holds products awaiting PostgreSQL synchronization.

The PostgreSQL connection comes from `DATABASE_URL` in the project `.env`.
The destination tables are `products` and `product_images` from `schema.sql`.
Existing product records are preserved and duplicate image URLs are not inserted.
If PostgreSQL is unavailable, URLs remain available locally. Subsequent image API
requests retry synchronization, at most once per minute on the memory cache path.

To explicitly retry synchronization from the repository root on Windows:

```powershell
.venv/Scripts/python.exe scripts/storefront_catalog.py sync-images
```

This stores image URLs, not the remote image files themselves. Back up the SQLite
file while there are pending outbox records.
