"""Password hashing (argon2id) and the rules passwords must follow."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD_LENGTH = 12
# argon2 handles any length, but there's no reason to hash megabytes per request.
MAX_PASSWORD_LENGTH = 256

_hasher = PasswordHasher()

# Verified against when the username doesn't exist, so a login for an unknown
# user takes as long as one with a wrong password (no username enumeration).
_DUMMY_HASH = _hasher.hash("interax-dummy-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """True if `password` matches; always does the full amount of work."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and (
            password_hash is not None
        )
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True if the hash used older parameters and should be replaced on login."""
    return _hasher.check_needs_rehash(password_hash)


def password_problem(password: str) -> str | None:
    """Why the password isn't acceptable, or None if it is."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"password must be at least {MIN_PASSWORD_LENGTH} characters"
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"password must be at most {MAX_PASSWORD_LENGTH} characters"
    if password.strip() != password:
        return "password must not start or end with whitespace"
    return None
