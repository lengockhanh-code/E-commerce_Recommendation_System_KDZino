"""User Profile & Address Management Endpoints"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.src.database.connection import get_db
from backend.src.models.orm import User, UserAddress, generate_uuid
from backend.src.models.schemas import UserProfile, UserProfileUpdate, AddressCreate, AddressResponse, ChangePasswordRequest
from backend.src.security.dependencies import require_current_user

router = APIRouter(prefix="/profile", tags=["User Profile & Settings"])


from backend.src.models.schemas import PreferencesUpdate, PreferencesResponse
from backend.src.services.preferences_service import read_preferences, save_preferences


@router.get("/preferences", response_model=PreferencesResponse)
def get_preferences(db: Session = Depends(get_db), user: User = Depends(require_current_user)):
    return read_preferences(db, user.id)


@router.put("/preferences", response_model=PreferencesResponse)
def put_preferences(data: PreferencesUpdate, db: Session = Depends(get_db), user: User = Depends(require_current_user)):
    return save_preferences(db, user, data.categories)


@router.get("", response_model=UserProfile)
def get_profile(user: User = Depends(require_current_user)):
    """Lấy thông tin hồ sơ người dùng"""
    return UserProfile.model_validate(user)


@router.put("", response_model=UserProfile)
def update_profile(
    data: UserProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    """Cập nhật họ tên hoặc ảnh đại diện"""
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.avatar_url is not None:
        user.avatar_url = data.avatar_url
    
    db.commit()
    db.refresh(user)
    return UserProfile.model_validate(user)


@router.get("/addresses", response_model=List[AddressResponse])
def list_addresses(
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    """Lấy danh sách địa chỉ giao hàng của người dùng"""
    addresses = db.query(UserAddress).filter(UserAddress.user_id == str(user.id)).all()
    return [AddressResponse.model_validate(a) for a in addresses]


@router.post("/addresses", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
def add_address(
    data: AddressCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    """Thêm địa chỉ giao hàng mới"""
    if data.is_default:
        db.query(UserAddress).filter(UserAddress.user_id == str(user.id)).update({"is_default": False})

    addr = UserAddress(
        id=generate_uuid(),
        user_id=str(user.id),
        recipient_name=data.recipient_name,
        phone=data.phone,
        address_line=data.address_line,
        city=data.city,
        district=data.district,
        is_default=data.is_default
    )
    db.add(addr)
    db.commit()
    db.refresh(addr)
    return AddressResponse.model_validate(addr)


@router.delete("/addresses/{address_id}")
def delete_address(
    address_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    """Xóa địa chỉ giao hàng theo address_id"""
    addr = db.query(UserAddress).filter(UserAddress.id == address_id, UserAddress.user_id == str(user.id)).first()
    if not addr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Địa chỉ không tồn tại")
    db.delete(addr)
    db.commit()
    return {"status": "success", "message": "Xóa địa chỉ thành công"}


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    """Đổi mật khẩu người dùng đang đăng nhập"""
    from backend.src.services.auth_service import change_user_password
    return change_user_password(db, user, data.old_password, data.new_password)


@router.get("/history")
def get_activity_history(
    db: Session = Depends(get_db),
    user: User = Depends(require_current_user)
):
    """Lấy danh sách lịch sử tương tác thật từ PostgreSQL của người dùng đang đăng nhập"""
    from backend.src.services.event_service import get_user_activity_history
    return get_user_activity_history(db, str(user.id))
