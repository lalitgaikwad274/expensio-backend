import os
import json

import firebase_admin
from firebase_admin import credentials, auth


def initialize_firebase():
    if firebase_admin._apps:
        return firebase_admin.get_app()

    firebase_config = os.getenv("FIREBASE_SERVICE_ACCOUNT")

    if not firebase_config:
        raise RuntimeError(
            "FIREBASE_SERVICE_ACCOUNT environment variable is not configured"
        )

    try:
        service_account_info = json.loads(firebase_config)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            "FIREBASE_SERVICE_ACCOUNT contains invalid JSON"
        ) from e

    cred = credentials.Certificate(service_account_info)

    return firebase_admin.initialize_app(cred)


firebase_app = initialize_firebase()



def verify_firebase_token(id_token: str):
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token

    except Exception:
        return None