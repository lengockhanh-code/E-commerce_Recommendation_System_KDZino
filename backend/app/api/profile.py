"""User Profile, Addresses & Wishlist API Router"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.models import User, UserAddress, Favorite, UserPreference, AuthAccount, Product
from app.model.schemas import (
    UserOut, UserUpdate, ChangePasswordRequest, AddressOut, AddressCreate,
    ProductOut, UserPreferencesUpdate
)
from app.services.auth_service import require_current_user, hash_password, verify_password
from app.services.product_service import format_product_dict

router = APIRouter(prefix="/profile", tags=["User Profile & Settings"])


@router.get("", response_model=UserOut)
def get_profile(current_user: User = Depends(require_current_user)):
    """Lấy thông tin trang cá nhân của người dùng"""
    return current_user


@router.put("", response_model=UserOut)
def update_profile(
    data: UserUpdate,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Cập nhật thông tin cá nhân (họ tên, ảnh đại diện)"""
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.avatar_url is not None:
        current_user.avatar_url = data.avatar_url
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Đổi mật khẩu người dùng"""
    auth_acc = db.query(AuthAccount).filter(
        AuthAccount.user_id == current_user.id,
        AuthAccount.provider == "local"
    ).first()

    if not auth_acc or not auth_acc.password_hash or not verify_password(data.old_password, auth_acc.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu cũ không chính xác"
        )

    auth_acc.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "Đổi mật khẩu thành công"}


@router.get("/addresses", response_model=List[AddressOut])
def get_addresses(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Lấy danh sách địa chỉ nhận hàng của người dùng"""
    return db.query(UserAddress).filter(UserAddress.user_id == current_user.id).all()


@router.post("/addresses", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
def create_address(
    data: AddressCreate,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Thêm địa chỉ nhận hàng mới"""
    if data.is_default:
        db.query(UserAddress).filter(UserAddress.user_id == current_user.id).update({"is_default": False})

    addr = UserAddress(
        user_id=current_user.id,
        receiver_name=data.receiver_name,
        phone=data.phone,
        province=data.province,
        district=data.district,
        ward=data.ward,
        address_line=data.address_line,
        is_default=data.is_default
    )
    db.add(addr)
    db.commit()
    db.refresh(addr)
    return addr


@router.get("/favorites", response_model=List[ProductOut])
def get_favorites(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Lấy danh sách sản phẩm yêu thích (Wishlist) của người dùng"""
    favs = db.query(Favorite).filter(Favorite.user_id == current_user.id).all()
    item_ids = [f.item_id for f in favs]
    if not item_ids:
        return []
    products = db.query(Product).filter(Product.item_id.in_(item_ids)).all()
    return [format_product_dict(p) for p in products]


@router.post("/favorites/{item_id}")
def toggle_favorite(
    item_id: str,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Thêm hoặc bỏ sản phẩm khỏi danh sách yêu thích"""
    fav = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.item_id == str(item_id)
    ).first()

    if fav:
        db.delete(fav)
        db.commit()
        return {"status": "removed", "item_id": item_id}
    else:
        new_fav = Favorite(user_id=current_user.id, item_id=str(item_id))
        db.add(new_fav)
        db.commit()
        return {"status": "added", "item_id": item_id}


@router.get("/preferences")
def get_user_preferences_route(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Lấy thông tin onboarding / sở thích cá nhân"""
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not pref:
        return {"onboarding_completed": False, "min_price": None, "max_price": None}
    return {
        "onboarding_completed": pref.onboarding_completed,
        "min_price": pref.min_price,
        "max_price": pref.max_price
    }


@router.post("/preferences")
def save_user_preferences_route(
    data: UserPreferencesUpdate,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Lưu sở thích cá nhân (onboarding)"""
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserPreference(user_id=current_user.id)
        db.add(pref)

    pref.min_price = data.min_price
    pref.max_price = data.max_price
    pref.onboarding_completed = data.onboarding_completed
    db.commit()
    return {"message": "Đã cập nhật sở thích thành công"}
