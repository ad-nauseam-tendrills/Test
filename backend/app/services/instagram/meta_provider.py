"""
Meta (Instagram) provider -- real Graph API integration.

This implements the **Instagram API with Instagram Login** flow, which
authenticates directly against an Instagram professional account and does
not require the account to be linked to a Facebook Page.

--- Credentials ---
Set these in backend/.env (git-ignored -- never commit real values):

  META_APP_ID          Instagram App ID     (NOT the Facebook App ID)
  META_APP_SECRET      Instagram App Secret (NOT the Facebook App Secret)
  META_REDIRECT_URI    HTTPS OAuth redirect URI registered on the app
  META_GRAPH_API_VERSION  e.g. v23.0

Both IDs live under the app's Instagram product ("API setup with
Instagram login"), and are distinct from the Facebook app credentials on
the main app settings page. Using the Facebook App ID here produces an
opaque "Invalid platform app" error, so the mismatch is worth checking
first when authentication fails.

--- OAuth flow ---
1. Send the user to `build_authorization_url()`.
2. Instagram redirects back to META_REDIRECT_URI with `?code=...`.
3. `authenticate(code)` exchanges that code for a short-lived token, then
   immediately upgrades it to a long-lived (~60 day) token.
4. `refresh_long_lived_token()` extends an unexpired long-lived token.

The redirect URI must be HTTPS; plain http://localhost is rejected. For
local development, expose the backend through a tunnel (e.g.
`cloudflared tunnel --url http://localhost:8000`) and register that HTTPS
URL as the redirect URI.

--- Testing without App Review ---
While the Meta app is in development mode, the Instagram accounts you add
to it get full permissions without App Review or Business Verification.
Review is only required to serve accounts you do not control.

Instagram is never scraped -- every call here is an official, documented
Graph API endpoint.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.services.instagram.base import (
    InstagramProvider,
    ProviderAccount,
    ProviderMedia,
    ProviderMediaInsights,
)

logger = logging.getLogger(__name__)

# Scopes required for reading profile data and post-level insights.
#
# instagram_business_manage_insights must be added to the app manually in
# the Meta console under "Permissions and features" -- the console's "Add
# all required permissions" button covers only basic/comments/messages.
# Without it the OAuth flow still succeeds and media still imports, but
# every insights call fails and posts land with no metrics at all.
#
# Comments and messaging scopes are deliberately not requested: this app
# reads performance data and never touches DMs, so asking for them would
# be requesting access it has no use for.
REQUIRED_SCOPES = ["instagram_business_basic", "instagram_business_manage_insights"]

AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_EXCHANGE_URL = "https://api.instagram.com/oauth/access_token"
GRAPH_BASE_URL = "https://graph.instagram.com"

MEDIA_FIELDS = "id,caption,media_type,media_url,permalink,thumbnail_url,timestamp,like_count,comments_count"
ACCOUNT_FIELDS = "user_id,username,account_type,profile_picture_url,followers_count,media_count"

# Insight metrics differ by media type. Meta rejects the whole request if
# any single metric is invalid for that media type, so these are grouped
# conservatively and requested per-type.
MEDIA_INSIGHT_METRICS = {
    "IMAGE": ["reach", "saved", "shares", "likes", "comments", "views"],
    "VIDEO": ["reach", "saved", "shares", "likes", "comments", "views"],
    "CAROUSEL_ALBUM": ["reach", "saved", "shares", "likes", "comments", "views"],
}

REQUEST_TIMEOUT_SECONDS = 20.0


class MetaCredentialsMissingError(RuntimeError):
    """Raised when the Meta integration is used without configured credentials."""


class MetaApiError(RuntimeError):
    """Raised when the Graph API returns an error response."""

    def __init__(self, message: str, status_code: int | None = None, payload: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


class MetaInstagramProvider(InstagramProvider):
    """Live Instagram Graph API integration (Instagram Login flow)."""

    def __init__(self, client: httpx.Client | None = None):
        self.app_id = settings.META_APP_ID
        self.app_secret = settings.META_APP_SECRET
        self.redirect_uri = settings.META_REDIRECT_URI
        self.api_version = settings.META_GRAPH_API_VERSION
        # Injectable for tests; no network calls are made at construction
        # time so the app still boots with no credentials configured.
        self._client = client

    # ------------------------------------------------------------------
    # Infrastructure
    # ------------------------------------------------------------------

    def _require_credentials(self) -> None:
        if not (self.app_id and self.app_secret and self.redirect_uri):
            raise MetaCredentialsMissingError(
                "Meta credentials are not configured. Set META_APP_ID, "
                "META_APP_SECRET and META_REDIRECT_URI to use the live "
                "Instagram integration, or use INSTAGRAM_PROVIDER=mock."
            )

    def _http(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS)

    def _request(self, method: str, url: str, **kwargs) -> dict:
        """Issue one Graph API call and normalize error handling."""
        client = self._http()
        owns_client = self._client is None
        try:
            response = client.request(method, url, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
        except httpx.HTTPError as exc:
            raise MetaApiError(f"Network error calling Instagram API: {exc}") from exc
        finally:
            if owns_client:
                client.close()

        try:
            payload = response.json()
        except ValueError:
            raise MetaApiError(
                f"Instagram API returned a non-JSON response (HTTP {response.status_code})",
                status_code=response.status_code,
            )

        if response.status_code >= 400 or "error" in payload:
            error = payload.get("error", {})
            # Never log or surface the access token itself.
            message = error.get("message") or f"HTTP {response.status_code}"
            raise MetaApiError(
                f"Instagram API error: {message}",
                status_code=response.status_code,
                payload=error,
            )
        return payload

    def _graph_url(self, path: str) -> str:
        return f"{GRAPH_BASE_URL}/{self.api_version}/{path.lstrip('/')}"

    @staticmethod
    def _token(access_token: str | None) -> str:
        if not access_token:
            raise MetaCredentialsMissingError(
                "An account access token is required for this call. Reconnect "
                "the Instagram account to obtain one."
            )
        return access_token

    # ------------------------------------------------------------------
    # OAuth
    # ------------------------------------------------------------------

    def build_authorization_url(self, state: str | None = None) -> str:
        """URL to send the user to in order to grant access."""
        self._require_credentials()
        params = {
            "client_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": ",".join(REQUIRED_SCOPES),
        }
        if state:
            params["state"] = state
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    def authenticate(self, authorization_code: str | None = None) -> ProviderAccount:
        self._require_credentials()
        if not authorization_code:
            raise MetaApiError("An authorization code is required to connect an Instagram account.")

        # Instagram appends "#_" to the code on redirect; it must be stripped.
        code = authorization_code.split("#")[0]

        short_lived = self._request(
            "POST",
            TOKEN_EXCHANGE_URL,
            data={
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
                "code": code,
            },
        )
        short_token = short_lived.get("access_token")
        if not short_token:
            raise MetaApiError("Instagram did not return an access token for this authorization code.")

        long_lived = self._request(
            "GET",
            f"{GRAPH_BASE_URL}/access_token",
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": self.app_secret,
                "access_token": short_token,
            },
        )
        access_token = long_lived.get("access_token", short_token)
        expires_in = long_lived.get("expires_in")
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)) if expires_in else None
        )

        account = self.get_account(ig_user_id="me", access_token=access_token)
        account.access_token = access_token
        account.token_expires_at = expires_at
        return account

    def refresh_long_lived_token(self, access_token: str) -> tuple[str, datetime | None]:
        """
        Extend an unexpired long-lived token by another ~60 days. Tokens
        must be refreshed before expiry; an expired token requires the
        user to reconnect through the full OAuth flow.
        """
        self._require_credentials()
        payload = self._request(
            "GET",
            f"{GRAPH_BASE_URL}/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": self._token(access_token)},
        )
        new_token = payload.get("access_token", access_token)
        expires_in = payload.get("expires_in")
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)) if expires_in else None
        )
        return new_token, expires_at

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def get_account(self, ig_user_id: str, access_token: str | None = None) -> ProviderAccount:
        self._require_credentials()
        token = self._token(access_token)
        target = ig_user_id or "me"
        payload = self._request(
            "GET",
            self._graph_url(target),
            params={"fields": ACCOUNT_FIELDS, "access_token": token},
        )
        return ProviderAccount(
            ig_user_id=str(payload.get("user_id") or payload.get("id") or target),
            username=payload.get("username", ""),
            account_type=payload.get("account_type", "BUSINESS"),
            profile_picture_url=payload.get("profile_picture_url"),
            follower_count=payload.get("followers_count"),
        )

    def get_media(
        self, ig_user_id: str, limit: int = 50, access_token: str | None = None
    ) -> list[ProviderMedia]:
        self._require_credentials()
        token = self._token(access_token)

        # Meta does not expose a historical follower count per post, so
        # every imported post is stamped with the CURRENT follower count.
        # Normalized comparisons across a long history are therefore
        # approximate for back-dated posts -- see README limitations.
        current_followers = self.get_account(ig_user_id, access_token=token).follower_count

        media: list[ProviderMedia] = []
        url = self._graph_url(f"{ig_user_id or 'me'}/media")
        params: dict | None = {
            "fields": MEDIA_FIELDS,
            "limit": min(limit, 100),
            "access_token": token,
        }

        while url and len(media) < limit:
            payload = self._request("GET", url, params=params)
            for item in payload.get("data", []):
                if len(media) >= limit:
                    break
                media.append(self._parse_media(item, token, current_followers))
            # Cursor-paginated: the `next` URL already carries all params.
            url = payload.get("paging", {}).get("next")
            params = None

        return media

    def _parse_media(self, item: dict, token: str, current_followers: int | None) -> ProviderMedia:
        media_id = str(item["id"])
        media_type = item.get("media_type", "IMAGE")

        insights = self.get_media_insights(media_id, access_token=token, media_type=media_type)
        # like_count/comments_count come back on the media edge itself and
        # are more reliably present than the insights equivalents.
        if item.get("like_count") is not None:
            insights.likes = item["like_count"]
        if item.get("comments_count") is not None:
            insights.comments = item["comments_count"]

        return ProviderMedia(
            ig_media_id=media_id,
            media_type=media_type,
            caption=item.get("caption"),
            media_url=item.get("media_url"),
            permalink=item.get("permalink"),
            thumbnail_url=item.get("thumbnail_url") or item.get("media_url"),
            posted_at=_parse_timestamp(item.get("timestamp")),
            follower_count_at_posting=current_followers,
            insights=insights,
        )

    def get_media_insights(
        self, ig_media_id: str, access_token: str | None = None, media_type: str = "IMAGE"
    ) -> ProviderMediaInsights:
        self._require_credentials()
        token = self._token(access_token)
        metrics = MEDIA_INSIGHT_METRICS.get(media_type, MEDIA_INSIGHT_METRICS["IMAGE"])

        try:
            payload = self._request(
                "GET",
                self._graph_url(f"{ig_media_id}/insights"),
                params={"metric": ",".join(metrics), "access_token": token},
            )
        except MetaApiError as exc:
            # Insights are unavailable for some media (e.g. posts older
            # than the insights window, or media published before the
            # account became professional). A post without insights is
            # still worth importing, so degrade rather than fail the
            # whole import.
            logger.warning("Insights unavailable for media %s: %s", ig_media_id, exc)
            return ProviderMediaInsights()

        values: dict[str, int] = {}
        for entry in payload.get("data", []):
            name = entry.get("name")
            series = entry.get("values") or []
            if name and series:
                values[name] = series[0].get("value")

        return ProviderMediaInsights(
            likes=values.get("likes"),
            comments=values.get("comments"),
            saves=values.get("saved"),
            shares=values.get("shares"),
            reach=values.get("reach"),
            views=values.get("views"),
            impressions=values.get("impressions"),
            profile_visits=None,  # account-level metric only
        )

    def get_account_insights(self, ig_user_id: str, access_token: str | None = None) -> dict:
        self._require_credentials()
        token = self._token(access_token)
        try:
            payload = self._request(
                "GET",
                self._graph_url(f"{ig_user_id or 'me'}/insights"),
                params={
                    # `profile_views` and `impressions` were deprecated in
                    # Graph API v22.0; `views` replaces impressions and
                    # profile_views has no direct successor. Requesting a
                    # deprecated metric fails the whole call, so only
                    # currently-supported metrics belong here.
                    "metric": "reach,views",
                    "period": "day",
                    "metric_type": "total_value",
                    "access_token": token,
                },
            )
        except MetaApiError as exc:
            logger.warning("Account insights unavailable for %s: %s", ig_user_id, exc)
            return {}

        result: dict[str, int | None] = {}
        for entry in payload.get("data", []):
            name = entry.get("name")
            total = entry.get("total_value", {}).get("value")
            if name:
                result[name] = total
        return result


    def get_follower_demographics(
        self, ig_user_id: str, access_token: str | None = None
    ) -> dict[str, int]:
        """
        Follower counts by country, via the follower_demographics insight.

        Meta withholds this below 100 followers and caps it at the top
        audience segments, so a small or missing result is normal and is
        returned as {} rather than raised.
        """
        self._require_credentials()
        token = self._token(access_token)
        try:
            payload = self._request(
                "GET",
                self._graph_url(f"{ig_user_id or 'me'}/insights"),
                params={
                    "metric": "follower_demographics",
                    "period": "lifetime",
                    "metric_type": "total_value",
                    "breakdown": "country",
                    "access_token": token,
                },
            )
        except MetaApiError as exc:
            logger.warning("Follower demographics unavailable for %s: %s", ig_user_id, exc)
            return {}

        return _parse_country_breakdown(payload)


def _parse_country_breakdown(payload: dict) -> dict[str, int]:
    """
    Pull {country_code: follower_count} out of a follower_demographics
    response. The breakdown nests several levels deep and Meta has
    reshaped it before, so every level is accessed defensively -- a shape
    we don't recognise yields {} rather than an exception.
    """
    result: dict[str, int] = {}
    for entry in payload.get("data", []):
        total_value = entry.get("total_value") or {}
        for breakdown in total_value.get("breakdowns", []) or []:
            for row in breakdown.get("results", []) or []:
                values = row.get("dimension_values") or []
                count = row.get("value")
                if values and isinstance(count, int):
                    result[str(values[0]).upper()] = count
    return result


def _parse_timestamp(value: str | None) -> datetime:
    """Parse Meta's ISO-8601 timestamps (e.g. 2024-05-01T12:34:56+0000)."""
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("+0000", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)
