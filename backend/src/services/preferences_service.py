"""Account-scoped onboarding preferences; database errors must reach the caller."""

from backend.src.models.orm import UserPreference

CATEGORIES = {
    "tech": ("Electronics",),
    "fashion": ("Women", "Men"),
    "home": ("Home",),
    "beauty": ("Beauty",),
    "baby": ("Kids", "Toys & Collectibles"),
    "sports": ("Sports & outdoors",),
    "books": ("Books",),
    "other": ("Vintage & collectibles", "Handmade", "Other"),
}


def read_preferences(db, user_id):
    row = db.get(UserPreference, str(user_id))
    return {
        "categories": row.categories if row else [],
        "completed": row is not None,
    }


def save_preferences(db, user, categories):
    # Serialize concurrent updates, including the first insert for this account.
    from backend.src.models.orm import User
    db.query(User).filter(User.id == str(user.id)).with_for_update().one()
    row = db.get(UserPreference, str(user.id))
    if row is None:
        row = UserPreference(user_id=str(user.id), categories=categories)
        db.add(row)
    else:
        row.categories = categories
    db.commit()
    return read_preferences(db, user.id)
