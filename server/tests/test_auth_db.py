"""End-to-end auth and upload flows against a real database (TEST_DATABASE_URL)."""

import time
import uuid

import pytest
from app.auth import CSRF_HEADER, SESSION_COOKIE
from app.config import settings
from app.main import app
from app.migrations import migrate
from app.users import create_user, delete_user
from fastapi.testclient import TestClient
from psycopg import Connection
from psycopg.rows import DictRow, dict_row

pytestmark = pytest.mark.db

PASSWORD = "a long test password"
CSRF = {CSRF_HEADER: "interax"}


@pytest.fixture
def conn():
    with Connection[DictRow].connect(
        settings.database_url, autocommit=True, row_factory=dict_row
    ) as conn:
        migrate(conn)
        yield conn


@pytest.fixture
def username(conn):
    name = f"test-{uuid.uuid4().hex[:12]}"
    create_user(conn, name, PASSWORD, "clinician")
    yield name
    delete_user(conn, name)


@pytest.fixture
def client():
    with TestClient(app) as client:
        deadline = time.monotonic() + 30
        while not app.state.schema.ready.is_set():
            assert time.monotonic() < deadline, "schema never became ready"
            time.sleep(0.1)
        yield client


def login(client: TestClient, username: str, password: str = PASSWORD):
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
        headers=CSRF,
    )


def test_login_me_logout(client, username):
    res = login(client, username.upper())  # usernames are case-insensitive
    assert res.status_code == 200
    assert res.json() == {"username": username, "role": "clinician"}
    set_cookie = res.headers["set-cookie"]
    assert SESSION_COOKIE in set_cookie
    assert "HttpOnly" in set_cookie
    assert "samesite=lax" in set_cookie.lower()

    assert client.get("/api/auth/me").json()["username"] == username

    assert client.post("/api/auth/logout", headers=CSRF).status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_logged_out_token_is_dead(client, username):
    login(client, username)
    token = client.cookies.get(SESSION_COOKIE)
    client.post("/api/auth/logout", headers=CSRF)

    client.cookies.set(SESSION_COOKIE, token)
    assert client.get("/api/auth/me").status_code == 401


def test_wrong_password_and_unknown_user_look_the_same(client, username):
    wrong = login(client, username, "not the password at all")
    unknown = login(client, f"nobody-{uuid.uuid4().hex[:8]}", PASSWORD)
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert SESSION_COOKIE not in client.cookies


def test_repeated_failures_are_throttled(client, username):
    statuses = [
        login(client, username, "wrong password!").status_code for _ in range(11)
    ]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    # Even the right password is refused while throttled.
    res = login(client, username)
    assert res.status_code == 429
    assert int(res.headers["retry-after"]) > 0


def test_deleting_user_ends_sessions(client, conn):
    name = f"test-{uuid.uuid4().hex[:12]}"
    create_user(conn, name, PASSWORD, "admin")
    login(client, name)
    assert client.get("/api/auth/me").status_code == 200
    delete_user(conn, name)
    assert client.get("/api/auth/me").status_code == 401


def test_upload_flow(client, username):
    created = client.post("/api/uploads", json={"prescriptions": []})
    assert created.status_code == 201
    upload = created.json()
    code, token = upload["id"], upload["revoke_token"]
    assert upload["expires_at"] > upload["uploaded_at"]

    # Patients can't read uploads back...
    assert client.get(f"/api/uploads/{code}").status_code == 401
    # ...clinicians can.
    login(client, username)
    got = client.get(f"/api/uploads/{code}").json()
    assert got["data"] == {"prescriptions": []}
    # No consent given: sharing defaults to off.
    assert got["share"] is False
    client.post("/api/auth/logout", headers=CSRF)

    # Revoking needs the token from the upload.
    assert client.delete(f"/api/uploads/{code}").status_code == 404
    assert (
        client.delete(
            f"/api/uploads/{code}", headers={"X-Revoke-Token": "guess"}
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/uploads/{code}", headers={"X-Revoke-Token": token}
        ).status_code
        == 204
    )


def test_upload_share_consent_is_stored(client, username):
    created = client.post("/api/uploads?share=true", json={"prescriptions": []})
    assert created.status_code == 201
    upload = created.json()

    login(client, username)
    assert client.get(f"/api/uploads/{upload['id']}").json()["share"] is True
    client.delete(f"/api/uploads/{upload['id']}", headers=CSRF)
