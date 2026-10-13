"""Conservative detail-page retrieval from authoritative catalog metadata."""
import os
import re
from pathlib import Path

MODEL_NAME = "catalog_similar_v2"
STOP_WORDS = set("a an and the for with from this that new used vintage old original authentic small medium large black white blue red green pink size set lot pack bundle sale free shipping brand unisex men women mens womens".split())
UNKNOWN = {"", "__unk__", "nan", "none", "null", "other", "others"}
# Category leaves such as Biking Equipment still contain distinct product types.
TYPE_PATTERNS = (
    r"\bhandle\s?bars?\b", r"\b(?:tires?|tyres?)\b", r"\bhelmets?\b",
    r"\bpedals?\b", r"\b(?:rackets?|racquets?)\b", r"\bsleeping\s+(?:pads?|mats?)\b",
    r"\bbackpacks?\b", r"\b(?:sneakers?|trainers?)\b", r"\bboots?\b",
)


def normalized(value):
    value = str(value or "").strip().lower()
    return "" if value in UNKNOWN else value


def title_tokens(name, brand):
    ignored = STOP_WORDS | set(re.findall(r"\w+", normalized(brand)))
    return sorted({word for word in re.findall(r"\w+", normalized(name))
                   if len(word) > 2 and not word.isdigit() and word not in ignored})


def are_titles_too_similar(name1, name2):
    if not name1 or not name2:
        return False
    w1 = set(re.findall(r"\b[a-z0-9]{3,}\b", name1.lower())) - STOP_WORDS
    w2 = set(re.findall(r"\b[a-z0-9]{3,}\b", name2.lower())) - STOP_WORDS
    if not w1 or not w2:
        return False
    inter = len(w1 & w2)
    union = len(w1 | w2)
    jaccard = inter / union
    containment = inter / min(len(w1), len(w2))
    return jaccard >= 0.5 or (containment >= 0.75 and inter >= 2)


def fetch_similar(trigger_item_id, limit=12, catalog_path=None):
    import duckdb
    if not trigger_item_id or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("Invalid similar product request")
    path = catalog_path or os.environ.get("MERREC_CATALOG_PATH") or (
        Path(__file__).resolve().parents[1] /
        "data/processed/recommender/serving/item_catalog_full.parquet")
    with duckdb.connect(config={"threads": 2}) as con:
        con.read_parquet(str(path)).create_view("catalog")
        cursor = con.execute("SELECT * FROM catalog WHERE CAST(item_id AS VARCHAR) = ? LIMIT 1", [str(trigger_item_id)])
        row = cursor.fetchone()
        if row is None:
            return []
        target = dict(zip([col[0] for col in cursor.description], row))
        tokens = title_tokens(target.get("name"), target.get("brand"))
        categories = [normalized(target.get(f"category{i}")) for i in range(3)]
        # Missing or generic leaf categories do not establish a product type.
        if not tokens or not categories[0] or not categories[2] or categories[2].startswith("other"):
            return []
        c2_where = "lower(trim(category2)) = ?"

        patterns = [r"(^|[^\w])" + re.escape(t[:-1] if t.endswith("s") and len(t) > 4 else t) + r"s?([^\w]|$)" for t in tokens]
        types = [pattern for pattern in TYPE_PATTERNS
                 if re.search(pattern, normalized(target.get("name")))]
        type_filter = "".join(" AND regexp_matches(lower(coalesce(name, '')), ?)" for _ in types)
        # A stem/grip advertised for handlebars is an accessory, not a handlebar.
        accessory = r"\b(?:stems?|grips?|tape|mounts?|covers?)\b"
        exclude_accessories = (TYPE_PATTERNS[0] in types
                               and not re.search(accessory, normalized(target.get("name"))))
        if exclude_accessories:
            type_filter += " AND NOT regexp_matches(lower(coalesce(name, '')), ?)"
        score = " + ".join("CASE WHEN regexp_matches(lower(coalesce(name, '')), ?) THEN 1 ELSE 0 END" for _ in patterns)
        candidate_pool_limit = max(limit * 6, 60)
        query = f"""WITH candidates AS (
            SELECT *, ({score}) AS title_matches
            FROM catalog
            WHERE lower(trim(category0)) = ? AND lower(trim(category1)) = ?
              AND {c2_where} AND CAST(item_id AS VARCHAR) != ? {type_filter}
        ) SELECT * FROM candidates WHERE title_matches > 0
          ORDER BY title_matches DESC,
            CASE WHEN lower(trim(brand)) = ? AND ? != '' THEN 1 ELSE 0 END DESC,
            abs(coalesce(price, 0) - ?) ASC, CAST(item_id AS VARCHAR)
          LIMIT ?"""
        cat_params = [categories[0], categories[1], categories[2]]
        cursor = con.execute(query, [*patterns, *cat_params, str(trigger_item_id), *types,
                                    *([accessory] if exclude_accessories else []),
                                    normalized(target.get("brand")), normalized(target.get("brand")),
                                    float(target.get("price") or 0), candidate_pool_limit])
        columns = [col[0] for col in cursor.description]
        raw_candidates = [dict(zip(columns, r)) for r in cursor.fetchall()]

        # Deduplicate titles so the user doesn't see 10+ identical listings of the same item
        selected = []
        for cand in raw_candidates:
            if len(selected) >= limit:
                break
            sim_count = sum(1 for sel in selected if are_titles_too_similar(cand.get("name"), sel.get("name")))
            if sim_count >= 1:
                continue
            selected.append(cand)

        # If candidates are exhausted but slots remain, allow at most 2 duplicates
        if len(selected) < limit:
            for cand in raw_candidates:
                if len(selected) >= limit:
                    break
                if any(cand["item_id"] == sel["item_id"] for sel in selected):
                    continue
                sim_count = sum(1 for sel in selected if are_titles_too_similar(cand.get("name"), sel.get("name")))
                if sim_count < 2:
                    selected.append(cand)

        return selected
