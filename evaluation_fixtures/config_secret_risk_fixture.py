"""EVALUATION FIXTURE ONLY — do not use in production."""

import os

SECRET_KEY = "default-dev-key-12345"
DEBUG = True
CORS_ORIGINS = ["*"]

def handle_error(e):
    return {"error": str(e), "trace": repr(e)}, 500

def check_api_key(key):
    return key == SECRET_KEY

class AppConfig:
    def __init__(self):
        self.debug = True
        self.secret = os.getenv("APP_SECRET", "fallback-dev-secret")
        self.admin_password = "admin123"
