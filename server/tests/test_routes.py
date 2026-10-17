"""Which routes need a session, and the CSRF guard. No database needed: the
session cookie is never valid here, and db access is stubbed."""

import pytest
from app.auth import CSRF_HEADER, SESSION_COOKIE, optional_user
from app.db import get_conn
from app.main import app
from app.upload_expiry import get_upload_expiry
from fastapi.testclient import TestClient


class _Result:
    rowcount = 0

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class FakeConn:
    def execute(self, *args, **kwargs):
        return _Result()

    def commit(self):
        pass


@pytest.fixture
def client():
    app.dependency_overrides[get_conn] = lambda: FakeConn()
    app.dependency_overrides[get_upload_expiry] = lambda: None
    # No `with`: the lifespan (db pool, background threads) isn't started.
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("GET", "/api/auth/me", {}),
        ("GET", "/api/uploads/123456", {}),
        ("GET", "/api/regimens/find", {}),
        ("GET", "/api/regimens/components?name=FOLFOX", {}),
        ("GET", "/api/medications/substances?name=ibalgin", {}),
        ("POST", "/api/interactions", {"json": {"substances": ["a", "b"]}}),
        ("POST", "/api/repo", {"json": {"meds": [], "interactions": []}}),
    ],
)
def test_clinician_routes_need_a_session(client, method, path, kwargs):
    assert client.request(method, path, **kwargs).status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [("POST", "/api/scan"), ("POST", "/api/dictate"), ("POST", "/api/uploads")],
)
def test_patient_routes_are_open(client, method, path):
    # No body, so validation fails, but it isn't rejected for lack of a login.
    assert client.request(method, path).status_code == 422


def test_old_unprefixed_routes_are_gone(client):
    for path in ("/scan", "/dictate", "/regimens/find", "/medications/substances"):
        assert client.get(path).status_code == 404


def test_revoke_without_token_or_session_is_404(client):
    assert client.delete("/api/uploads/123456").status_code == 404


def test_login_requires_csrf_header(client):
    res = client.post("/api/auth/login", json={"username": "a", "password": "b"})
    assert res.status_code == 403


def test_cookie_writes_require_csrf_header(client):
    client.cookies.set(SESSION_COOKIE, "forged")
    assert client.post("/api/auth/logout").status_code == 403
    assert client.post("/api/interactions", json={"substances": []}).status_code == 403


def test_invalid_cookie_is_401_with_header(client):
    # A cookie that matches no session; the db lookup itself is stubbed out.
    app.dependency_overrides[optional_user] = lambda: None
    client.cookies.set(SESSION_COOKIE, "forged")
    res = client.get("/api/regimens/find", headers={CSRF_HEADER: "interax"})
    assert res.status_code == 401


def test_api_responses_are_not_cached(client):
    assert client.get("/api/auth/me").headers["cache-control"] == "no-store"
