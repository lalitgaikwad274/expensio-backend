import json
import os
import firebase_admin
from firebase_admin import credentials, auth


def initialize_firebase():
    if firebase_admin._apps:
        return firebase_admin.get_app()

    firebase_config = os.getenv("FIREBASE_SERVICE_ACCOUNT")

    # service_account_path = os.getenv(
    #     "FIREBASE_SERVICE_ACCOUNT_PATH",
    #     "firebase-service-account.json",
    # )

    try:
        service_account_path = json.loads(firebase_config)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            "FIREBASE_SERVICE_ACCOUNT contains invalid JSON"
        ) from e


    if not os.path.exists(service_account_path):
        raise RuntimeError(
            f"Firebase service account file not found: {service_account_path}"
        )

    try:
        cred = credentials.Certificate(service_account_path)
    except Exception as e:
        raise RuntimeError(
            f"Failed to load Firebase service account: {e}"
        ) from e

    return firebase_admin.initialize_app(cred)


firebase_app = initialize_firebase()


def verify_firebase_token(id_token: str):
    try:
        return auth.verify_id_token(id_token)
    except Exception:
        return None