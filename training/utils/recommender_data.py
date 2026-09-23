
from pathlib import Path
import json

from .paths import MODEL_SPECIFIC_DIR, CF_TRAIN, CATALOG_TRAIN
from .common import connect_duckdb, valid_parquet, atomic_json

ACTIVE_ITEMS = MODEL_SPECIFIC_DIR / "active_items.parquet"
ACTIVE_USERS = MODEL_SPECIFIC_DIR / "active_users.parquet"
CF_ACTIVE = MODEL_SPECIFIC_DIR / "cf_active.parquet"
ITEM_FEATURES = MODEL_SPECIFIC_DIR / "item_features.parquet"
SHARED_STATS = MODEL_SPECIFIC_DIR / "shared_stats.json"

def prepare_active_universe(
    target_interaction_coverage=0.95,
    min_item_events=2,
    min_user_items=2,
    force=False
):
    """
    Không cắt cứng N item.
    Chọn số item tối thiểu để đạt target interaction coverage trên TRAIN.
    """
    con = connect_duckdb()

    if force:
        for p in [ACTIVE_ITEMS, ACTIVE_USERS, CF_ACTIVE, ITEM_FEATURES, SHARED_STATS]:
            if p.exists():
                p.unlink()

    if not valid_parquet(ACTIVE_ITEMS, con):
        con.execute(f"""
        COPY (
            WITH item_stats AS (
                SELECT
                    item_id,
                    SUM(interactions) AS interactions,
                    COUNT(*) AS user_pairs,
                    SUM(purchases) AS purchases
                FROM read_parquet('{CF_TRAIN.as_posix()}')
                GROUP BY item_id
                HAVING SUM(interactions) >= {min_item_events}
            ),
            ranked AS (
                SELECT
                    *,
                    SUM(interactions) OVER () AS total_interactions,
                    SUM(interactions) OVER (
                        ORDER BY interactions DESC, item_id
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) AS cumulative_interactions
                FROM item_stats
            ),
            selected AS (
                SELECT *
                FROM ranked
                WHERE (cumulative_interactions - interactions)
                      < total_interactions * {target_interaction_coverage}
            )
            SELECT
                item_id,
                ROW_NUMBER() OVER (
                    ORDER BY interactions DESC, item_id
                ) - 1 AS item_idx,
                interactions,
                user_pairs,
                purchases,
                cumulative_interactions / total_interactions AS cumulative_coverage
            FROM selected
            ORDER BY item_idx
        )
        TO '{ACTIVE_ITEMS.as_posix()}'
        (FORMAT PARQUET, COMPRESSION ZSTD)
        """)

    if not valid_parquet(ACTIVE_USERS, con):
        con.execute(f"""
        COPY (
            WITH users AS (
                SELECT
                    c.user_id,
                    SUM(c.interactions) AS interactions,
                    COUNT(*) AS item_pairs,
                    SUM(c.purchases) AS purchases
                FROM read_parquet('{CF_TRAIN.as_posix()}') c
                INNER JOIN read_parquet('{ACTIVE_ITEMS.as_posix()}') i USING(item_id)
                GROUP BY c.user_id
                HAVING COUNT(*) >= {min_user_items}
            )
            SELECT
                user_id,
                ROW_NUMBER() OVER (
                    ORDER BY interactions DESC, user_id
                ) - 1 AS user_idx,
                interactions,
                item_pairs,
                purchases
            FROM users
        )
        TO '{ACTIVE_USERS.as_posix()}'
        (FORMAT PARQUET, COMPRESSION ZSTD)
        """)

    if not valid_parquet(CF_ACTIVE, con):
        con.execute(f"""
        COPY (
            SELECT
                u.user_idx,
                i.item_idx,
                c.user_id,
                c.item_id,
                c.implicit_score,
                c.interactions,
                c.views,
                c.likes,
                c.carts,
                c.offers,
                c.buy_starts,
                c.purchases,
                c.last_ts
            FROM read_parquet('{CF_TRAIN.as_posix()}') c
            INNER JOIN read_parquet('{ACTIVE_USERS.as_posix()}') u USING(user_id)
            INNER JOIN read_parquet('{ACTIVE_ITEMS.as_posix()}') i USING(item_id)
        )
        TO '{CF_ACTIVE.as_posix()}'
        (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 250000)
        """)

    if not valid_parquet(ITEM_FEATURES, con):
        con.execute(f"""
        COPY (
            SELECT
                i.item_idx,
                i.item_id,
                i.interactions,
                i.user_pairs,
                i.purchases,
                c.product_id,
                COALESCE(c.name, '') AS name,
                COALESCE(c.price, 0) AS price,
                COALESCE(c.category0, '__UNK__') AS category0,
                COALESCE(c.category1, '__UNK__') AS category1,
                COALESCE(c.category2, '__UNK__') AS category2,
                COALESCE(c.brand, '__UNK__') AS brand,
                COALESCE(c.condition, '__UNK__') AS condition,
                COALESCE(c.shipper, '__UNK__') AS shipper
            FROM read_parquet('{ACTIVE_ITEMS.as_posix()}') i
            LEFT JOIN read_parquet('{CATALOG_TRAIN.as_posix()}') c USING(item_id)
            ORDER BY item_idx
        )
        TO '{ITEM_FEATURES.as_posix()}'
        (FORMAT PARQUET, COMPRESSION ZSTD)
        """)

    if not SHARED_STATS.exists():
        row = con.execute(f"""
            SELECT
                COUNT(*) AS pairs,
                MAX(user_idx)+1 AS users,
                MAX(item_idx)+1 AS items
            FROM read_parquet('{CF_ACTIVE.as_posix()}')
        """).fetchone()

        coverage = con.execute(f"""
            SELECT
                COUNT(*) AS active_items,
                MAX(cumulative_coverage) AS coverage
            FROM read_parquet('{ACTIVE_ITEMS.as_posix()}')
        """).fetchone()

        atomic_json({
            "pairs": int(row[0]),
            "users": int(row[1]),
            "items": int(row[2]),
            "active_items": int(coverage[0]),
            "interaction_coverage": float(coverage[1]),
        }, SHARED_STATS)

    con.close()
    return {
        "active_items": ACTIVE_ITEMS,
        "active_users": ACTIVE_USERS,
        "cf_active": CF_ACTIVE,
        "item_features": ITEM_FEATURES,
        "stats": SHARED_STATS,
    }

def load_shared_stats():
    if not SHARED_STATS.exists():
        prepare_active_universe()
    return json.loads(SHARED_STATS.read_text(encoding="utf-8"))
