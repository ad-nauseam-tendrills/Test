"""
Tests for connecting, deleting, and guarding Instagram accounts.

The mock-provider guard matters more than it looks: the mock provider
fabricates 60 posts, and a deployment that lets them in shows the owner a
dashboard full of work they never made, with every recommendation derived
from it.
"""
from app.core.config import settings
from app.models.instagram_post import InstagramPost


def _auth_headers(client, email, password="testpass123"):
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_mock_provider_refused_when_disabled(client, monkeypatch):
    # conftest enables the mock provider for the suite; this is the
    # production default.
    monkeypatch.setattr(settings, "ENABLE_MOCK_PROVIDER", False)
    headers = _auth_headers(client, "nomock@example.com")

    resp = client.post("/api/v1/accounts/connect", json={"provider": "mock"}, headers=headers)
    assert resp.status_code == 400
    assert "mock provider is disabled" in resp.json()["detail"]

    # Nothing was created.
    assert client.get("/api/v1/accounts", headers=headers).json() == []


def test_mock_provider_default_payload_also_refused_when_disabled(client, monkeypatch):
    # ConnectAccountRequest.provider defaults to "mock", so an empty body
    # must hit the same guard rather than sneaking past it.
    monkeypatch.setattr(settings, "ENABLE_MOCK_PROVIDER", False)
    headers = _auth_headers(client, "nomockdefault@example.com")

    resp = client.post("/api/v1/accounts/connect", json={}, headers=headers)
    assert resp.status_code == 400


def test_delete_account_removes_its_posts(client, db_session):
    headers = _auth_headers(client, "purger@example.com")
    account = client.post(
        "/api/v1/accounts/connect", json={"provider": "mock"}, headers=headers
    ).json()
    client.post(f"/api/v1/accounts/{account['id']}/import", headers=headers)
    assert db_session.query(InstagramPost).count() > 0

    resp = client.delete(f"/api/v1/accounts/{account['id']}", headers=headers)
    assert resp.status_code == 204

    assert client.get("/api/v1/accounts", headers=headers).json() == []
    # Posts go with the account -- otherwise the dashboard keeps reporting
    # data the user just deleted.
    assert db_session.query(InstagramPost).count() == 0

    dashboard = client.get("/api/v1/analytics/dashboard", headers=headers).json()
    assert dashboard["overview"]["total_posts"] == 0


def test_cannot_delete_another_users_account(client):
    owner = _auth_headers(client, "owner-of-account@example.com")
    account = client.post(
        "/api/v1/accounts/connect", json={"provider": "mock"}, headers=owner
    ).json()

    intruder = _auth_headers(client, "intruder@example.com")
    resp = client.delete(f"/api/v1/accounts/{account['id']}", headers=intruder)
    assert resp.status_code == 404

    # Still there for its actual owner.
    assert len(client.get("/api/v1/accounts", headers=owner).json()) == 1


def test_delete_requires_authentication(client):
    headers = _auth_headers(client, "unauthdelete@example.com")
    account = client.post(
        "/api/v1/accounts/connect", json={"provider": "mock"}, headers=headers
    ).json()

    assert client.delete(f"/api/v1/accounts/{account['id']}").status_code == 401
