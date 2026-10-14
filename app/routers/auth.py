from app.models import User
from app.schemas import UserCreate
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post("/login", status_code=200)
def login(
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    firebase_uid = firebase_user["uid"]

    email = firebase_user.get("email")

    name = (
        firebase_user.get("name")
        or firebase_user.get("display_name")
        or "User"
    )

    phone_number = (
        firebase_user.get("phone_number")
        or firebase_user.get("phone")
    )

    user = (
        db.query(User)
        .filter(User.firebase_uid == firebase_uid)
        .first()
    )

    if not user:
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            name=name,
            phone_number=phone_number,
        )

        db.add(user)
        db.commit()
        db.refresh(user)
    elif phone_number and not user.phone_number:
        user.phone_number = phone_number
        db.commit()
        db.refresh(user)

    return {
        "status": "success",
        "message": "Login successful",
        "user": {
            "id": user.id,
            "firebase_uid": user.firebase_uid,
            "name": user.name,
            "email": user.email,
            "phone_number": user.phone_number,
        }
    }


@router.post("/register", status_code=201)
def register(
    user: UserCreate,
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    firebase_uid = user.firebase_uid or firebase_user.get("uid")
    email = user.email or firebase_user.get("email")
    name = (
        user.name
        or firebase_user.get("name")
        or firebase_user.get("display_name")
        or "User"
    )
    phone_number = (
        user.phone_number
        or firebase_user.get("phone_number")
        or firebase_user.get("phone")
    )

    if phone_number:
        existing_user = (
            db.query(User)
            .filter(User.phone_number == phone_number)
            .first()
        )
        if existing_user:
            return {
                "status": "error",
                "message": "User with this phone number already exists"
            }

    if firebase_uid:
        existing_uid = (
            db.query(User)
            .filter(User.firebase_uid == firebase_uid)
            .first()
        )
        if existing_uid:
            return {
                "status": "error",
                "message": "User already exists"
            }

    new_user = User(
        firebase_uid=firebase_uid,
        email=email,
        name=name,
        phone_number=phone_number,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "status": "success",
        "message": "Registration successful",
        "user": {
            "id": new_user.id,
            "firebase_uid": new_user.firebase_uid,
            "name": new_user.name,
            "email": new_user.email,
            "phone_number": new_user.phone_number,
        }
    }


@router.get("/user", status_code=200)
def get_user(
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    firebase_uid = firebase_user["uid"]
    user = (
        db.query(User)
        .filter(User.firebase_uid == firebase_uid)
        .first()
    )
    return {
        "status": "success",
        "user": {
            "id": user.id,
            "firebase_uid": user.firebase_uid,
            "name": user.name,
            "email": user.email,
            "phone_number": user.phone_number,
        }
    }