import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth.firebase import verify_firebase_token


security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    # Allow local development and testing tokens
    if os.getenv("APP_ENV", "development").lower() in ["development", "test"] and token in ["dev_token", "test_token", "default_user"]:
        return {
            "uid": "default_user",
            "email": "user@expensio.app",
            "name": "Default User",
        }

    decoded_token = verify_firebase_token(token)

    if not decoded_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase token"
        )

    return decoded_token