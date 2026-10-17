from datetime import timedelta

from app.auth import Throttle, hash_token, new_token
from app.passwords import (
    MIN_PASSWORD_LENGTH,
    hash_password,
    needs_rehash,
    password_problem,
    verify_password,
)
from app.users import normalize_username, username_problem


def test_password_roundtrip():
    hashed = hash_password("correct horse battery")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "correct horse battery")
    assert not verify_password(hashed, "correct horse batterY")
    assert not needs_rehash(hashed)


def test_unknown_user_never_verifies():
    # The dummy hash is used for timing only; it must not accept its own password.
    assert not verify_password(None, "interax-dummy-password")
    assert not verify_password(None, "anything at all")


def test_garbage_hash_is_rejected_not_raised():
    assert not verify_password("not-a-hash", "whatever password")


def test_password_rules():
    assert password_problem("x" * (MIN_PASSWORD_LENGTH - 1))
    assert password_problem(" padded password ")
    assert password_problem("x" * 1000)
    assert password_problem("long enough password") is None


def test_usernames():
    assert normalize_username("  Dr.House ") == "dr.house"
    assert username_problem("dr.house") is None
    assert username_problem("ab")
    assert username_problem("dr house")
    assert username_problem("DrHouse")  # must be normalized first


def test_tokens_are_unique_and_hashed():
    a, b = new_token(), new_token()
    assert a != b
    assert len(a) >= 40
    assert hash_token(a) == hash_token(a)
    assert hash_token(a) != hash_token(b)
    assert len(hash_token(a)) == 32


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_throttle_blocks_after_max_failures_and_recovers():
    clock = FakeClock()
    throttle = Throttle(max_failures=3, window=timedelta(seconds=60), clock=clock)

    for _ in range(3):
        assert throttle.retry_after("alice") == 0
        throttle.fail("alice")
        clock.now += 1

    wait = throttle.retry_after("alice")
    assert 0 < wait <= 60
    assert throttle.retry_after("bob") == 0

    clock.now += wait
    assert throttle.retry_after("alice") == 0


def test_throttle_reset():
    clock = FakeClock()
    throttle = Throttle(max_failures=1, window=timedelta(minutes=5), clock=clock)
    throttle.fail("alice")
    assert throttle.retry_after("alice") > 0
    throttle.reset("alice")
    assert throttle.retry_after("alice") == 0
