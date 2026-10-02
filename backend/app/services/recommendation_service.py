"""Recommendation Service for Home, Product Detail, and Cart Contexts"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def get_recommendations_service(
    db: Session,
    context: str = "home",
    trigger_item_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 12
) -> Dict[str, Any]:
    from recommendation_engine import get_recommendations
    return get_recommendations(
        context=context,
        trigger_item_id=trigger_item_id,
        user_id=user_id,
        limit=limit
    )
