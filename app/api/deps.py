from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models.models import User, UserRole, Staff

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user account")
    return user

def require_roles(allowed_roles: List[UserRole]):
    """Decorator / dependency to enforce Role-Based Access Control (RBAC)"""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Allowed roles: {[r.value for r in allowed_roles]}, current: {current_user.role.value}"
            )
        return current_user
    return role_checker

def get_current_staff(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Staff:
    """Ensure current user is staff and has active facility profile"""
    staff = db.query(Staff).filter(Staff.user_id == current_user.id).first()
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not affiliated with a hospital staff profile"
        )
    if not staff.active_status:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff profile is deactivated"
        )
    return staff

