from datetime import UTC, datetime, timedelta

import jwt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config import config


PASSWORD_RESET_MAX_AGE_SECONDS = 60 * 30


class TokenManager:
    def __init__(self):
        self.serializer = URLSafeTimedSerializer(config.secret_key)

    def create_token(self, user_id, role):
        now = datetime.now(UTC)
        payload = {
            "user_id": user_id,
            "role": role,
            "iat": now,
            "exp": now + timedelta(hours=max(1, config.jwt_expiration_hours)),
        }
        return jwt.encode(payload, config.jwt_secret, algorithm=config.jwt_algorithm)

    def verify_token(self, token):
        try:
            data = jwt.decode(
                token,
                config.jwt_secret,
                algorithms=[config.jwt_algorithm],
            )
            return True, data
        except jwt.ExpiredSignatureError:
            return False, "Session expired. Please log in again."
        except jwt.InvalidTokenError:
            return False, "Invalid session token."

    def create_password_reset_token(self, email, role):
        return self.serializer.dumps({"email": email, "role": role}, salt="smart-library-password-reset")

    def verify_password_reset_token(self, token):
        try:
            data = self.serializer.loads(
                token,
                salt="smart-library-password-reset",
                max_age=PASSWORD_RESET_MAX_AGE_SECONDS,
            )
            return True, data
        except SignatureExpired:
            return False, "Reset session expired. Please request a new password reset."
        except BadSignature:
            return False, "Invalid password reset token."


token_manager = TokenManager()
