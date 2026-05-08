from itsdangerous import BadSignature, URLSafeSerializer
import bcrypt

from backend.config import settings

serializer = URLSafeSerializer(settings.secret_key, salt="homeschool-session")

PASSWORD_METHOD = "password"
PIN_METHOD = "pin"

def _hash_value(value: str) -> str:
    return bcrypt.hashpw(value.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_value(value: str, hashed: str) -> bool:
    return bcrypt.checkpw(value.encode("utf-8"), hashed.encode("utf-8"))


_password_hash = settings.family_password_hash or _hash_value(settings.family_password)
_pin_hash = settings.family_pin_hash or _hash_value(settings.family_pin)


def authenticate(method: str, credential: str) -> bool:
    if method == PASSWORD_METHOD:
        return _verify_value(credential, _password_hash)
    if method == PIN_METHOD:
        return _verify_value(credential, _pin_hash)
    return False


def create_session_token(method: str) -> str:
    return serializer.dumps({"method": method})


def verify_session_token(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        data = serializer.loads(token)
    except BadSignature:
        return None
    if data.get("method") not in {PASSWORD_METHOD, PIN_METHOD}:
        return None
    return data
