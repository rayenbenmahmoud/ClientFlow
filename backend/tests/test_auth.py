import pytest

from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def test_login_returns_tokens_and_user(anon, rep):
    r = anon.post("/api/auth/login/", {"username": "rep", "password": PASSWORD}, format="json")
    assert r.status_code == 200
    body = r.json()
    assert body["access"] and body["refresh"]
    assert body["user"]["username"] == "rep" and body["user"]["role"] == "sales_rep"
    assert "password" not in body["user"]


def test_login_rejects_bad_password(anon, rep):
    r = anon.post("/api/auth/login/", {"username": "rep", "password": "wrong"}, format="json")
    assert r.status_code == 401


def test_inactive_user_cannot_login(anon, rep):
    rep.is_active = False
    rep.save()
    r = anon.post("/api/auth/login/", {"username": "rep", "password": PASSWORD}, format="json")
    assert r.status_code == 401


def test_me_requires_authentication(anon, rep_api):
    assert anon.get("/api/auth/me/").status_code == 401
    r = rep_api.get("/api/auth/me/")
    assert r.status_code == 200 and r.json()["username"] == "rep"


@pytest.mark.parametrize(
    "path", ["companies", "contacts", "leads", "deals", "tasks", "interactions", "notifications", "tags", "users"]
)
def test_endpoints_require_authentication(anon, path):
    assert anon.get(f"/api/{path}/").status_code == 401


def test_dashboard_requires_authentication(anon):
    assert anon.get("/api/dashboard/").status_code == 401


def test_refresh_and_logout_blacklists_token(anon, rep):
    login = anon.post("/api/auth/login/", {"username": "rep", "password": PASSWORD}, format="json").json()
    refreshed = anon.post("/api/auth/refresh/", {"refresh": login["refresh"]}, format="json")
    assert refreshed.status_code == 200
    new_refresh = refreshed.json()["refresh"]

    assert anon.post("/api/auth/logout/", {"refresh": new_refresh}, format="json").status_code == 204
    again = anon.post("/api/auth/refresh/", {"refresh": new_refresh}, format="json")
    assert again.status_code == 401


def test_jwt_bearer_header_grants_access(anon, rep):
    login = anon.post("/api/auth/login/", {"username": "rep", "password": PASSWORD}, format="json").json()
    anon.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    assert anon.get("/api/auth/me/").status_code == 200


def test_login_is_rate_limited(anon, rep, settings):
    from rest_framework.throttling import ScopedRateThrottle

    ScopedRateThrottle.THROTTLE_RATES = {"login": "3/min"}
    from django.core.cache import cache

    cache.clear()
    try:
        codes = [
            anon.post("/api/auth/login/", {"username": "rep", "password": "bad"}, format="json").status_code
            for _ in range(5)
        ]
    finally:
        ScopedRateThrottle.THROTTLE_RATES = {"login": "1000/min"}
        cache.clear()
    assert codes[:3] == [401, 401, 401] and 429 in codes[3:]
