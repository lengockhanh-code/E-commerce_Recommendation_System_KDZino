"""Recommendation Service: Bridge to Machine Learning & Serving Engine"""

import sys
from pathlib import Path
from typing import Optional, List
from sqlalchemy.orm import Session

from backend.src.models.orm import Product
from backend.src.models.schemas import ProductSummary, RecommendationResponse
from backend.src.services.product_service import product_to_summary

# Add repository root to path for recommendation engine script
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def get_recommendations(
    db: Session,
    context: str = "home",
    item_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 10
) -> RecommendationResponse:
    item_ids: List[str] = []
    algorithm_name = "content_based_v1" if context in ("product_detail", "cart") else "overall_popular_v1"

    try:
        from scripts.recommendation_engine import get_recommendations as engine_get_recs
        rec_res = engine_get_recs(context=context, trigger_item_id=item_id, user_id=user_id, limit=limit)
        
        if isinstance(rec_res, dict):
            algorithm_name = rec_res.get("model_name", algorithm_name)
            items_list = rec_res.get("items", [])
            item_ids = [str(it["id"]) for it in items_list if isinstance(it, dict) and "id" in it]
        elif isinstance(rec_res, list):
            item_ids = [str(it["id"]) if isinstance(it, dict) else str(it) for it in rec_res]
    except Exception as e:
        print(f"Error in recommendation_service execution: {e}", file=sys.stderr)
        item_ids = []

    products_by_id = {}
    if item_ids:
        db_products = db.query(Product).filter(Product.item_id.in_(item_ids)).all()
        products_by_id = {p.item_id: product_to_summary(p) for p in db_products}

    ordered_products: List[ProductSummary] = []
    for iid in item_ids:
        if iid in products_by_id:
            ordered_products.append(products_by_id[iid])

    # If recommendation engine returns fewer products than limit, fill up with PostgreSQL catalog
    if len(ordered_products) < limit:
        needed = limit - len(ordered_products)
        existing_ids = set(p.item_id for p in ordered_products)
        if item_id:
            existing_ids.add(str(item_id))

        fallback_query = db.query(Product)
        if existing_ids:
            fallback_query = fallback_query.filter(~Product.item_id.in_(existing_ids))

        fallback_products = fallback_query.limit(needed).all()
        for fp in fallback_products:
            ordered_products.append(product_to_summary(fp))

    return RecommendationResponse(
        recommendations=ordered_products[:limit],
        source="postgres_catalog",
        algorithm=algorithm_name
    )
