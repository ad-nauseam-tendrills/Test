"""
Tests for the live Meta provider.

Every HTTP call is mocked with respx -- these tests never touch the
network and never require real Meta credentials.
"""
from urllib.parse import parse_qs

import httpx
import pytest
import respx

from app.core.config import settings
from app.services.instagram.meta_provider import (
    GRAPH_BASE_URL,
    TOKEN_EXCHANGE_URL,
    MetaApiError,
    MetaCredentialsMissingError,
    MetaInstagramProvider,
)


@pytest.fixture()
def configured_provider(monkeypatch):
    """A provider with credentials present (values are fake)."""
    monkeypatch.setattr(settings, "META_APP_ID", "test-ig-app-id")
    monkeypatch.setattr(settings, "META_APP_SECRET", "test-ig-app-secret")
    monkeypatch.setattr(settings, "META_REDIRECT_URI", "https://example.test/api/v1/accounts/meta/callback")
    monkeypatch.setattr(settings, "META_GRAPH_API_VERSION", "v23.0")
    return MetaInstagramProvider()


@pytest.fixture()
def unconfigured_provider(monkeypatch):
    monkeypatch.setattr(settings, "META_APP_ID", None)
    monkeypatch.setattr(settings, "META_APP_SECRET", None)
    monkeypatch.setattr(settings, "META_REDIRECT_URI", None)
    return MetaInstagramProvider()


# --- Credential handling -------------------------------------------------


def test_instantiating_without_credentials_does_not_raise(unconfigured_provider):
    # The app must boot with no Meta credentials configured.
    assert unconfigured_provider is not None


def test_calls_without_credentials_raise_clearly(unconfigured_provider):
    with pytest.raises(MetaCredentialsMissingError):
        unconfigured_provider.authenticate("some-code")
    with pytest.raises(MetaCredentialsMissingError):
        unconfigured_provider.get_account("me", access_token="tok")


def test_data_call_without_access_token_raises(configured_provider):
    with pytest.raises(MetaCredentialsMissingError):
        configured_provider.get_account("me", access_token=None)


# --- Authorization URL ---------------------------------------------------


def test_authorization_url_contains_required_scopes(configured_provider):
    url = configured_provider.build_authorization_url(state="signed-state")
    assert url.startswith("https://www.instagram.com/oauth/authorize?")
    assert "instagram_business_basic" in url
    assert "instagram_business_manage_insights" in url
    assert "client_id=test-ig-app-id" in url
    assert "state=signed-state" in url
    assert "response_type=code" in url


def test_authorization_url_requires_credentials(unconfigured_provider):
    with pytest.raises(MetaCredentialsMissingError):
        unconfigured_provider.build_authorization_url()


# --- OAuth token exchange ------------------------------------------------


@respx.mock
def test_authenticate_exchanges_code_for_long_lived_token(configured_provider):
    respx.post(TOKEN_EXCHANGE_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "short-token", "user_id": 178414})
    )
    respx.get(f"{GRAPH_BASE_URL}/access_token").mock(
        return_value=httpx.Response(
            200, json={"access_token": "long-token", "token_type": "bearer", "expires_in": 5183944}
        )
    )
    respx.get(f"{GRAPH_BASE_URL}/v23.0/me").mock(
        return_value=httpx.Response(
            200,
            json={
                "user_id": "178414",
                "username": "test_artist",
                "account_type": "BUSINESS",
                "followers_count": 4210,
                "profile_picture_url": "https://cdn.example/pic.jpg",
            },
        )
    )

    account = configured_provider.authenticate("auth-code-123")

    assert account.ig_user_id == "178414"
    assert account.username == "test_artist"
    assert account.follower_count == 4210
    # Must store the LONG-lived token, not the short-lived one.
    assert account.access_token == "long-token"
    assert account.token_expires_at is not None


@respx.mock
def test_authenticate_strips_instagram_fragment_from_code(configured_provider):
    route = respx.post(TOKEN_EXCHANGE_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "short-token"})
    )
    respx.get(f"{GRAPH_BASE_URL}/access_token").mock(
        return_value=httpx.Response(200, json={"access_token": "long-token", "expires_in": 100})
    )
    respx.get(f"{GRAPH_BASE_URL}/v23.0/me").mock(
        return_value=httpx.Response(200, json={"user_id": "1", "username": "a"})
    )

    configured_provider.authenticate("real-code#_")

    # Instagram appends "#_" to the code on redirect; sending it through
    # verbatim makes the exchange fail, so it must be stripped exactly.
    sent_body = parse_qs(route.calls[0].request.content.decode())
    assert sent_body["code"] == ["real-code"]


def test_authenticate_without_code_raises(configured_provider):
    with pytest.raises(MetaApiError):
        configured_provider.authenticate(None)


@respx.mock
def test_api_error_is_wrapped(configured_provider):
    respx.post(TOKEN_EXCHANGE_URL).mock(
        return_value=httpx.Response(
            400, json={"error": {"message": "Invalid platform app", "code": 191}}
        )
    )
    with pytest.raises(MetaApiError) as exc:
        configured_provider.authenticate("bad-code")
    assert "Invalid platform app" in str(exc.value)


@respx.mock
def test_network_failure_is_wrapped(configured_provider):
    respx.post(TOKEN_EXCHANGE_URL).mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(MetaApiError):
        configured_provider.authenticate("code")


@respx.mock
def test_refresh_long_lived_token(configured_provider):
    respx.get(f"{GRAPH_BASE_URL}/refresh_access_token").mock(
        return_value=httpx.Response(200, json={"access_token": "refreshed", "expires_in": 5183944})
    )
    token, expires_at = configured_provider.refresh_long_lived_token("old-token")
    assert token == "refreshed"
    assert expires_at is not None


# --- Media + insights ----------------------------------------------------


def _mock_account_route(followers=1000):
    respx.get(f"{GRAPH_BASE_URL}/v23.0/me").mock(
        return_value=httpx.Response(
            200,
            json={"user_id": "1", "username": "artist", "account_type": "BUSINESS", "followers_count": followers},
        )
    )


@respx.mock
def test_get_media_parses_posts_and_insights(configured_provider):
    _mock_account_route(followers=2500)
    respx.get(f"{GRAPH_BASE_URL}/v23.0/me/media").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "media-1",
                        "caption": "A quiet study",
                        "media_type": "IMAGE",
                        "media_url": "https://cdn.example/1.jpg",
                        "permalink": "https://instagram.com/p/abc",
                        "timestamp": "2026-05-01T12:34:56+0000",
                        "like_count": 120,
                        "comments_count": 8,
                    }
                ]
            },
        )
    )
    respx.get(f"{GRAPH_BASE_URL}/v23.0/media-1/insights").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"name": "reach", "values": [{"value": 1800}]},
                    {"name": "saved", "values": [{"value": 45}]},
                    {"name": "shares", "values": [{"value": 12}]},
                    {"name": "views", "values": [{"value": 2400}]},
                ]
            },
        )
    )

    media = configured_provider.get_media("me", limit=10, access_token="tok")

    assert len(media) == 1
    post = media[0]
    assert post.ig_media_id == "media-1"
    assert post.media_type == "IMAGE"
    assert post.caption == "A quiet study"
    assert post.posted_at.year == 2026
    assert post.posted_at.month == 5
    # like_count/comments_count from the media edge win over insights.
    assert post.insights.likes == 120
    assert post.insights.comments == 8
    assert post.insights.reach == 1800
    assert post.insights.saves == 45
    assert post.insights.shares == 12
    assert post.insights.views == 2400
    # profile_visits is account-level in Meta's API, never per-media.
    assert post.insights.profile_visits is None
    # Meta exposes no historical follower count, so posts get the current one.
    assert post.follower_count_at_posting == 2500


@respx.mock
def test_get_media_follows_pagination_cursor(configured_provider):
    """Media spread across pages is collected by following `paging.next`."""
    _mock_account_route()
    respx.get(url__regex=rf"{GRAPH_BASE_URL}/v23\.0/\w+/insights").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    page_two_url = f"{GRAPH_BASE_URL}/v23.0/me/media?after=cursor2"
    respx.get(page_two_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": "m2", "media_type": "IMAGE", "timestamp": "2026-04-01T00:00:00+0000"},
                    {"id": "m3", "media_type": "IMAGE", "timestamp": "2026-03-01T00:00:00+0000"},
                ]
            },
        )
    )
    respx.get(f"{GRAPH_BASE_URL}/v23.0/me/media").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": "m0", "media_type": "IMAGE", "timestamp": "2026-06-01T00:00:00+0000"},
                    {"id": "m1", "media_type": "IMAGE", "timestamp": "2026-05-01T00:00:00+0000"},
                ],
                "paging": {"next": page_two_url},
            },
        )
    )

    media = configured_provider.get_media("me", limit=10, access_token="tok")

    # Both pages collected, in order.
    assert [m.ig_media_id for m in media] == ["m0", "m1", "m2", "m3"]


@respx.mock
def test_get_media_stops_at_limit_mid_page(configured_provider):
    """The caller's limit is respected even when a page overshoots it."""
    _mock_account_route()
    respx.get(url__regex=rf"{GRAPH_BASE_URL}/v23\.0/\w+/insights").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get(f"{GRAPH_BASE_URL}/v23.0/me/media").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": f"m{i}", "media_type": "IMAGE", "timestamp": "2026-05-01T00:00:00+0000"}
                    for i in range(5)
                ],
                "paging": {"next": f"{GRAPH_BASE_URL}/v23.0/me/media?after=cursor2"},
            },
        )
    )

    media = configured_provider.get_media("me", limit=3, access_token="tok")
    assert len(media) == 3


@respx.mock
def test_missing_insights_degrade_instead_of_failing_import(configured_provider):
    """A post whose insights are unavailable should still import."""
    _mock_account_route()
    respx.get(f"{GRAPH_BASE_URL}/v23.0/me/media").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "old-media",
                        "media_type": "IMAGE",
                        "timestamp": "2020-01-01T00:00:00+0000",
                        "like_count": 5,
                    }
                ]
            },
        )
    )
    respx.get(f"{GRAPH_BASE_URL}/v23.0/old-media/insights").mock(
        return_value=httpx.Response(
            400, json={"error": {"message": "Insights not available for this media"}}
        )
    )

    media = configured_provider.get_media("me", limit=5, access_token="tok")

    assert len(media) == 1
    assert media[0].insights.reach is None
    assert media[0].insights.likes == 5  # still captured from the media edge


@respx.mock
def test_account_insights_returns_empty_on_error(configured_provider):
    respx.get(f"{GRAPH_BASE_URL}/v23.0/me/insights").mock(
        return_value=httpx.Response(400, json={"error": {"message": "no data"}})
    )
    assert configured_provider.get_account_insights("me", access_token="tok") == {}


@respx.mock
def test_account_insights_parses_total_values(configured_provider):
    respx.get(f"{GRAPH_BASE_URL}/v23.0/me/insights").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"name": "reach", "total_value": {"value": 9000}},
                    {"name": "views", "total_value": {"value": 320}},
                ]
            },
        )
    )
    result = configured_provider.get_account_insights("me", access_token="tok")
    assert result == {"reach": 9000, "views": 320}


@respx.mock
def test_account_insights_requests_no_deprecated_metrics(configured_provider):
    """profile_views/impressions were removed in v22.0 and 400 the whole call."""
    route = respx.get(f"{GRAPH_BASE_URL}/v23.0/me/insights").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    configured_provider.get_account_insights("me", access_token="tok")

    requested = route.calls[0].request.url.params["metric"]
    assert "profile_views" not in requested
    assert "impressions" not in requested


# --- Follower demographics -----------------------------------------------


@respx.mock
def test_follower_demographics_parses_country_breakdown(configured_provider):
    respx.get(f"{GRAPH_BASE_URL}/v23.0/me/insights").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "name": "follower_demographics",
                        "total_value": {
                            "breakdowns": [
                                {
                                    "dimension_keys": ["country"],
                                    "results": [
                                        {"dimension_values": ["US"], "value": 1200},
                                        {"dimension_values": ["GB"], "value": 300},
                                    ],
                                }
                            ]
                        },
                    }
                ]
            },
        )
    )
    result = configured_provider.get_follower_demographics("me", access_token="tok")
    assert result == {"US": 1200, "GB": 300}


@respx.mock
def test_follower_demographics_returns_empty_when_withheld(configured_provider):
    """Meta withholds this below 100 followers -- normal, not an error."""
    respx.get(f"{GRAPH_BASE_URL}/v23.0/me/insights").mock(
        return_value=httpx.Response(
            400, json={"error": {"message": "Not enough followers to show demographics"}}
        )
    )
    assert configured_provider.get_follower_demographics("me", access_token="tok") == {}


@respx.mock
def test_follower_demographics_tolerates_unexpected_shape(configured_provider):
    respx.get(f"{GRAPH_BASE_URL}/v23.0/me/insights").mock(
        return_value=httpx.Response(200, json={"data": [{"name": "follower_demographics"}]})
    )
    assert configured_provider.get_follower_demographics("me", access_token="tok") == {}


def test_mock_provider_demographics_are_deterministic_and_varied():
    from app.services.instagram.mock_provider import MockInstagramProvider

    provider = MockInstagramProvider()
    a = provider.get_follower_demographics("mock_user_1")
    b = provider.get_follower_demographics("mock_user_1")
    assert a == b
    assert len(a) > 1
    assert all(isinstance(v, int) and v > 0 for v in a.values())
