from app.models import User
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

    user = (
        db.query(User)
        .filter(User.firebase_uid == firebase_uid)
        .first()
    )

    if not user:

        user = User(
            firebase_uid=firebase_uid,
            email=email,
            name=name
        )

        db.add(user)
        db.commit()
        db.refresh(user)

    return {
        "status": "success",
        "message": "Login successful",
        "user": {
            "id": user.id,
            "firebase_uid": user.firebase_uid,
            "name": user.name,
            "email": user.email
        }
    }


@router.post("/register", status_code=201)
def register(
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

    user = (
        db.query(User)
        .filter(User.firebase_uid == firebase_uid)
        .first()
    )

    if user:
        return {
            "status": "error",
            "message": "User already exists"
        }

    user = User(
        firebase_uid=firebase_uid,
        email=email,
        name=name
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "status": "success",
        "message": "Registration successful",
        "user": {
            "id": user.id,
            "firebase_uid": user.firebase_uid,
            "name": user.name,
            "email": user.email
        }
    }


