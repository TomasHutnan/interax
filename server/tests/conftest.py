"""Test configuration; must run before `app` is imported (settings read env at import).

Unit tests need no database. Tests marked `db` run against TEST_DATABASE_URL
(e.g. the compose db: postgresql://interax:<password>@localhost:<port>/interax)
and are skipped without it. They only touch their own uniquely named users and
uploads.
"""

import os

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

# Set before app.config loads the repo-root .env, which never overrides
# variables that already exist (even empty ones).
os.environ["DATABASE_URL"] = (
    TEST_DATABASE_URL or "postgresql://unused:unused@127.0.0.1:1/unused"
)
# The test client talks plain http, which would drop Secure cookies.
os.environ["SESSION_COOKIE_SECURE"] = "false"
os.environ["BOOTSTRAP_ADMIN_USERNAME"] = ""
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = ""
os.environ["SEED_DEV_USERS"] = "false"

import pytest  # noqa: E402  (must come after the environment setup above)


def pytest_configure(config):
    config.addinivalue_line("markers", "db: needs a real database (TEST_DATABASE_URL)")


def pytest_collection_modifyitems(config, items):
    if TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL not set")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)
