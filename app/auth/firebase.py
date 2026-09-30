import os
import json

import firebase_admin
from firebase_admin import credentials, auth


def initialize_firebase():
    # Prevent duplicate Firebase initialization
    if firebase_admin._apps:
        return firebase_admin.get_app()

    # 1. Production / Render:
    #    FIREBASE_SERVICE_ACCOUNT contains the complete JSON string or a file path
    firebase_config = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if firebase_config:
        firebase_config = firebase_config.strip()

    if firebase_config:
        # If it points to an existing file path, load it as a certificate file
        if os.path.exists(firebase_config):
            try:
                cred = credentials.Certificate(firebase_config)
                return firebase_admin.initialize_app(cred)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to load Firebase service account from '{firebase_config}': {e}"
                ) from e

        # Otherwise, parse as JSON string
        try:
            service_account_info = json.loads(firebase_config)
            cred = credentials.Certificate(service_account_info)
            return firebase_admin.initialize_app(cred)

        except json.JSONDecodeError as e:
            raise RuntimeError(
                "FIREBASE_SERVICE_ACCOUNT contains invalid JSON. "
                "Ensure it is a valid JSON string or file path, or remove it to use the local service account file."
            ) from e

        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize Firebase from environment variable: {e}"
            ) from e

    # 2. Local development:
    #    Use firebase-service-account.json (supports both FIREBASE_SERVICE_ACCOUNT_PATH and FIREBASE_CREDENTIALS_PATH)
    service_account_path = (
        os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
        or os.getenv("FIREBASE_CREDENTIALS_PATH")
        or "firebase-service-account.json"
    )

    if not os.path.exists(service_account_path):
        raise RuntimeError(
            "Firebase credentials not found. "
            "Set FIREBASE_SERVICE_ACCOUNT or provide "
            f"the service account file at: {service_account_path}"
        )

    try:
        cred = credentials.Certificate(service_account_path)

        return firebase_admin.initialize_app(cred)

    except Exception as e:
        raise RuntimeError(
            f"Failed to load Firebase service account: {e}"
        ) from e


firebase_app = initialize_firebase()


def verify_firebase_token(id_token: str):
    try:
        return auth.verify_id_token(id_token)
    except Exception:
        return None