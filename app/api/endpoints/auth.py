from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.models import User, UserRole, Patient, Staff
from app.schemas.schemas import UserRegister, UserLogin, Token, UserResponse
from app.services.audit import log_audit_event
import random

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse)
def register_user(user_in: UserRegister, db: Session = Depends(get_db)):
    # Check if email exists
    if user_in.email:
        existing_email = db.query(User).filter(User.email == user_in.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists"
            )
    if user_in.phone:
        existing_phone = db.query(User).filter(User.phone == user_in.phone).first()
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this phone number already exists"
            )

    new_user = User(
        email=user_in.email,
        phone=user_in.phone,
        password_hash=get_password_hash(user_in.password),
        role=user_in.role,
        full_name=user_in.full_name,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # If registered as patient, automatically initialize a patient profile if details exist
    if user_in.role == UserRole.PATIENT:
        p_num = f"VIT-2026-{random.randint(1000, 9999)}"
        names = user_in.full_name.split(" ", 1)
        first_name = names[0]
        last_name = names[1] if len(names) > 1 else ""
        patient = Patient(
            user_id=new_user.id,
            patient_number=p_num,
            first_name=first_name,
            last_name=last_name,
            gender="unspecified",
            dob="2000-01-01",
            phone=user_in.phone
        )
        db.add(patient)
        db.commit()

    log_audit_event(
        db,
        action="USER_REGISTERED",
        resource_type="user",
        resource_id=new_user.id,
        actor_id=new_user.id
    )

    return new_user

@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    ident = login_data.identifier.strip()
    user = db.query(User).filter(
        (User.email == ident) | (User.phone == ident)
    ).first()

    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email/phone or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is deactivated"
        )

    staff_profile = db.query(Staff).filter(Staff.user_id == user.id).first()
    facility_id = staff_profile.facility_id if staff_profile else None
    department = staff_profile.department if staff_profile else None

    token_data = {
        "sub": user.id,
        "role": user.role.value,
        "facility_id": facility_id,
        "department": department
    }
    access_token = create_access_token(data=token_data)

    log_audit_event(
        db,
        action="USER_LOGIN",
        resource_type="user",
        resource_id=user.id,
        actor_id=user.id
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role.value,
        user_id=user.id,
        full_name=user.full_name,
        facility_id=facility_id,
        department=department
    )

