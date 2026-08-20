import io

import numpy as np
from PIL import Image


def _auth_headers(client, email="artist@example.com", password="testpass123"):
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_and_login(client):
    headers = _auth_headers(client, "user1@example.com")
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "user1@example.com"

    login = client.post(
        "/api/v1/auth/login", json={"email": "user1@example.com", "password": "testpass123"}
    )
    assert login.status_code == 200


def test_register_duplicate_email_fails(client):
    _auth_headers(client, "dup@example.com")
    resp = client.post(
        "/api/v1/auth/register", json={"email": "dup@example.com", "password": "testpass123"}
    )
    assert resp.status_code == 400


def test_unauthenticated_request_rejected(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_connect_mock_account_and_import_posts(client):
    headers = _auth_headers(client, "importer@example.com")

    connect = client.post("/api/v1/accounts/connect", json={"provider": "mock"}, headers=headers)
    assert connect.status_code == 201
    account = connect.json()
    assert account["provider"] == "mock"
    assert account["follower_count"] > 0

    imported = client.post(f"/api/v1/accounts/{account['id']}/import", headers=headers)
    assert imported.status_code == 200
    body = imported.json()
    assert body["imported_count"] >= 30

    # Re-importing should skip already-imported posts.
    reimported = client.post(f"/api/v1/accounts/{account['id']}/import", headers=headers)
    assert reimported.json()["imported_count"] == 0
    assert reimported.json()["skipped_count"] == body["imported_count"]


def test_dashboard_without_account_reports_no_data(client):
    headers = _auth_headers(client, "nodashboard@example.com")
    resp = client.get("/api/v1/analytics/dashboard", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["overview"]["total_posts"] == 0
    assert body["has_enough_data"] is False


def test_dashboard_with_imported_posts(client):
    headers = _auth_headers(client, "dashboarduser@example.com")
    connect = client.post("/api/v1/accounts/connect", json={"provider": "mock"}, headers=headers)
    account = connect.json()
    client.post(f"/api/v1/accounts/{account['id']}/import", headers=headers)

    resp = client.get("/api/v1/analytics/dashboard", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["overview"]["total_posts"] >= 30
    assert body["has_enough_data"] is True
    assert len(body["by_day_of_week"]) == 7
    assert len(body["by_hour_of_day"]) == 24
    assert len(body["best_posts"]) > 0


def _sample_jpeg_bytes(width=1600, height=1200, fill=(60, 60, 60)) -> bytes:
    arr = np.full((height, width, 3), fill, dtype=np.uint8)
    rng = np.random.default_rng(1)
    arr = np.clip(arr.astype(int) + rng.integers(0, 20, size=arr.shape), 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


def test_upload_rejects_non_image_file(client):
    headers = _auth_headers(client, "badupload@example.com")
    resp = client.post(
        "/api/v1/images/upload",
        headers=headers,
        files={"file": ("not_an_image.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 415


def test_upload_analyze_and_generate_variant_flow(client):
    headers = _auth_headers(client, "fullflow@example.com")

    # Connect + import so historical-similarity/timing scores have data to work with.
    connect = client.post("/api/v1/accounts/connect", json={"provider": "mock"}, headers=headers)
    account = connect.json()
    client.post(f"/api/v1/accounts/{account['id']}/import", headers=headers)

    upload = client.post(
        "/api/v1/images/upload",
        headers=headers,
        files={"file": ("test.jpg", _sample_jpeg_bytes(), "image/jpeg")},
    )
    assert upload.status_code == 201
    image = upload.json()
    assert image["width"] == 1600
    assert image["height"] == 1200

    analyze = client.post(f"/api/v1/images/{image['id']}/analyze", headers=headers)
    assert analyze.status_code == 200
    body = analyze.json()
    assert 0 <= body["scores"]["overall_readiness"]["score"] <= 100
    assert "not a prediction" in body["scores"]["overall_readiness"]["explanation"].lower()
    assert isinstance(body["recommendations"], list)

    variant = client.post(
        f"/api/v1/images/{image['id']}/generate-variant",
        headers=headers,
        json={"artwork_integrity_mode": True},
    )
    assert variant.status_code == 200
    variant_body = variant.json()
    assert variant_body["artwork_integrity_mode"] is True
    assert variant_body["adjustments"]["exposure"] is not None

    detail = client.get(f"/api/v1/images/{image['id']}", headers=headers)
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["analysis"] is not None
    assert len(detail_body["variants"]) == 1

    file_resp = client.get(variant_body["url"])
    assert file_resp.status_code == 200
    assert file_resp.headers["content-type"] == "image/jpeg"


def test_generate_variant_requires_analysis_first(client):
    headers = _auth_headers(client, "novariant@example.com")
    upload = client.post(
        "/api/v1/images/upload",
        headers=headers,
        files={"file": ("test.jpg", _sample_jpeg_bytes(), "image/jpeg")},
    )
    image = upload.json()

    resp = client.post(
        f"/api/v1/images/{image['id']}/generate-variant",
        headers=headers,
        json={"artwork_integrity_mode": True},
    )
    assert resp.status_code == 400


def test_artwork_integrity_setting_toggle(client):
    headers = _auth_headers(client, "settingsuser@example.com")
    resp = client.get("/api/v1/settings", headers=headers)
    assert resp.json()["artwork_integrity_enabled"] is True

    update = client.put(
        "/api/v1/settings", headers=headers, json={"artwork_integrity_enabled": False}
    )
    assert update.status_code == 200
    assert update.json()["artwork_integrity_enabled"] is False


# --- Meta OAuth endpoints ------------------------------------------------


def test_meta_authorize_url_requires_authentication(client):
    resp = client.get("/api/v1/accounts/meta/authorize-url")
    assert resp.status_code == 401


def test_meta_authorize_url_without_credentials_returns_clear_error(client):
    headers = _auth_headers(client, "nometa@example.com")
    resp = client.get("/api/v1/accounts/meta/authorize-url", headers=headers)
    # No Meta credentials are configured in the test environment, so this
    # must fail with an explanatory 400 rather than a 500.
    assert resp.status_code == 400
    assert "META_APP_ID" in resp.json()["detail"]


def test_meta_authorize_url_with_credentials(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "META_APP_ID", "ig-app-id")
    monkeypatch.setattr(settings, "META_APP_SECRET", "ig-secret")
    monkeypatch.setattr(settings, "META_REDIRECT_URI", "https://example.test/cb")

    headers = _auth_headers(client, "withmeta@example.com")
    resp = client.get("/api/v1/accounts/meta/authorize-url", headers=headers)
    assert resp.status_code == 200
    url = resp.json()["authorize_url"]
    assert url.startswith("https://www.instagram.com/oauth/authorize?")
    assert "state=" in url


def test_meta_callback_rejects_missing_state(client):
    resp = client.get(
        "/api/v1/accounts/meta/callback?code=abc", follow_redirects=False
    )
    assert resp.status_code == 307
    assert "instagram=error" in resp.headers["location"]


def test_meta_callback_rejects_forged_state(client):
    """A state token we did not sign must never bind an account."""
    resp = client.get(
        "/api/v1/accounts/meta/callback?code=abc&state=not-a-real-token",
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "instagram=error" in resp.headers["location"]
    assert "expired" in resp.headers["location"]


def test_meta_callback_surfaces_user_denial(client):
    """User clicking 'Cancel' on Instagram's consent screen."""
    resp = client.get(
        "/api/v1/accounts/meta/callback?error=access_denied"
        "&error_description=User+denied+the+request",
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "instagram=error" in resp.headers["location"]


# --- Hashtags & captions -------------------------------------------------


def test_hashtags_without_account(client):
    headers = _auth_headers(client, "notags@example.com")
    resp = client.get("/api/v1/analytics/hashtags", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_enough_data"] is False
    assert body["hashtags"] == []
    assert body["caveat"]


def test_hashtags_with_imported_posts(client):
    headers = _auth_headers(client, "tagsuser@example.com")
    connect = client.post("/api/v1/accounts/connect", json={"provider": "mock"}, headers=headers)
    account = connect.json()
    client.post(f"/api/v1/accounts/{account['id']}/import", headers=headers)

    resp = client.get("/api/v1/analytics/hashtags", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_enough_data"] is True
    assert len(body["hashtags"]) > 0
    assert body["caveat"]

    # Tags are stored bare; the leading "#" is display formatting the UI adds.
    for tag in body["hashtags"]:
        assert not tag["tag"].startswith("#")
        # Well-sampled tags get an average; thin ones are reported without one.
        if tag["post_count"] < 3:
            assert tag["avg_engagement_rate"] is None


def test_hashtags_requires_authentication(client):
    assert client.get("/api/v1/analytics/hashtags").status_code == 401


def test_captions_without_api_key_returns_clear_error(client):
    headers = _auth_headers(client, "nocaptions@example.com")
    upload = client.post(
        "/api/v1/images/upload",
        headers=headers,
        files={"file": ("test.jpg", _sample_jpeg_bytes(), "image/jpeg")},
    )
    image = upload.json()

    resp = client.post(f"/api/v1/images/{image['id']}/captions", headers=headers)
    assert resp.status_code == 400
    assert "ANTHROPIC_API_KEY" in resp.json()["detail"]


def test_captions_endpoint_persists_suggestions(client, monkeypatch):
    from app.services.captions.generator import CaptionOption

    monkeypatch.setattr(
        "app.api.routes.images.generate_captions",
        lambda ctx: [
            CaptionOption(text="A quiet study.", approach="observation"),
            CaptionOption(text="Three weeks of work.", approach="process note"),
        ],
    )

    headers = _auth_headers(client, "captionuser@example.com")
    upload = client.post(
        "/api/v1/images/upload",
        headers=headers,
        files={"file": ("test.jpg", _sample_jpeg_bytes(), "image/jpeg")},
    )
    image = upload.json()

    resp = client.post(f"/api/v1/images/{image['id']}/captions", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert [c["caption_text"] for c in body["captions"]] == [
        "A quiet study.",
        "Three weeks of work.",
    ]
    assert body["captions"][1]["approach"] == "process note"
    # The disclaimer must travel with the suggestions.
    assert "not a prediction" in body["note"].lower()


def test_captions_rejects_another_users_image(client, monkeypatch):
    from app.services.captions.generator import CaptionOption

    monkeypatch.setattr(
        "app.api.routes.images.generate_captions",
        lambda ctx: [CaptionOption(text="x", approach="y")],
    )

    owner = _auth_headers(client, "owner@example.com")
    upload = client.post(
        "/api/v1/images/upload",
        headers=owner,
        files={"file": ("test.jpg", _sample_jpeg_bytes(), "image/jpeg")},
    )
    image = upload.json()

    intruder = _auth_headers(client, "intruder@example.com")
    resp = client.post(f"/api/v1/images/{image['id']}/captions", headers=intruder)
    assert resp.status_code == 404


# --- Audience & caption features -----------------------------------------


def test_audience_without_account(client):
    headers = _auth_headers(client, "noaudience@example.com")
    resp = client.get("/api/v1/analytics/audience", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_enough_data"] is False
    assert body["caveat"]


def test_import_populates_demographics_and_audience(client):
    headers = _auth_headers(client, "audienceuser@example.com")
    connect = client.post("/api/v1/accounts/connect", json={"provider": "mock"}, headers=headers)
    account = connect.json()
    client.post(f"/api/v1/accounts/{account['id']}/import", headers=headers)

    resp = client.get("/api/v1/analytics/audience", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_enough_data"] is True
    assert len(body["hours"]) == 24
    assert len(body["top_countries"]) > 0
    assert 0 < body["coverage"] <= 1
    # Awake fraction must actually vary across the day for a real audience.
    fractions = {h["awake_fraction"] for h in body["hours"]}
    assert len(fractions) > 1


def test_audience_local_hours_respect_utc_offset(client):
    headers = _auth_headers(client, "offsetuser@example.com")
    connect = client.post("/api/v1/accounts/connect", json={"provider": "mock"}, headers=headers)
    client.post(f"/api/v1/accounts/{connect.json()['id']}/import", headers=headers)

    resp = client.get("/api/v1/analytics/audience?utc_offset=-5", headers=headers)
    hours = {h["hour_utc"]: h["hour_local"] for h in resp.json()["hours"]}
    assert hours[12] == 7


def test_sync_demographics_endpoint(client):
    headers = _auth_headers(client, "syncdemo@example.com")
    connect = client.post("/api/v1/accounts/connect", json={"provider": "mock"}, headers=headers)
    account = connect.json()

    resp = client.post(f"/api/v1/accounts/{account['id']}/sync-demographics", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["demographics_synced_at"] is not None


def test_sync_demographics_rejects_another_users_account(client):
    owner = _auth_headers(client, "demoowner@example.com")
    account = client.post(
        "/api/v1/accounts/connect", json={"provider": "mock"}, headers=owner
    ).json()

    intruder = _auth_headers(client, "demointruder@example.com")
    resp = client.post(f"/api/v1/accounts/{account['id']}/sync-demographics", headers=intruder)
    assert resp.status_code == 404


def test_caption_features_with_imported_posts(client):
    headers = _auth_headers(client, "capfeatures@example.com")
    connect = client.post("/api/v1/accounts/connect", json={"provider": "mock"}, headers=headers)
    client.post(f"/api/v1/accounts/{connect.json()['id']}/import", headers=headers)

    resp = client.get("/api/v1/analytics/caption-features", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["caveat"]
    for row in body["features"]:
        assert row["post_count"] >= 4
        assert row["feature"] and row["group"]


def test_caption_features_requires_authentication(client):
    assert client.get("/api/v1/analytics/caption-features").status_code == 401
