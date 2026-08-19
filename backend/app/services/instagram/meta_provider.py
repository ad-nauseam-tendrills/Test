"""
Placeholder Meta (Instagram Graph API) provider.

This class is structured to match the official Meta Instagram Graph API
shape (Instagram professional account login, /me/media, insights edges,
etc.) but does NOT make network calls yet and does NOT require real
credentials to import or instantiate -- it raises a clear
NotImplementedError only when one of its methods is actually invoked.

--- Where real Meta credentials eventually go ---
Set these environment variables (see backend/.env.example):
  META_APP_ID
  META_APP_SECRET
  META_REDIRECT_URI
  META_GRAPH_API_VERSION

They are read via app.core.config.settings. NEVER commit real values --
.env is git-ignored; only .env.example (with placeholder values) is
checked in.

When implementing this for real:
  1. authenticate(): exchange the OAuth `code` for a short-lived user
     token via GET /oauth/access_token, then exchange for a long-lived
     token via GET /access_token?grant_type=fb_exchange_token.
  2. get_account(): GET /{ig-user-id}?fields=username,profile_picture_url,
     followers_count,account_type using the stored access token.
  3. get_media(): GET /{ig-user-id}/media?fields=...
  4. get_media_insights(): GET /{ig-media-id}/insights?metric=...
  5. get_account_insights(): GET /{ig-user-id}/insights?metric=...

All HTTP calls should go through a shared, timeout-bounded HTTP client
with retry/backoff and should never be made from request-handling code
directly -- keep them isolated here.
"""
from app.core.config import settings
from app.services.instagram.base import (
    InstagramProvider,
    ProviderAccount,
    ProviderMedia,
    ProviderMediaInsights,
)


class MetaCredentialsMissingError(RuntimeError):
    pass


class MetaInstagramProvider(InstagramProvider):
    """
    Real Meta Graph API integration. Not implemented in v0.1 -- calling
    any method raises MetaCredentialsMissingError/NotImplementedError so
    the rest of the app can select this provider without crashing at
    import time, and so the failure mode is explicit rather than silent.
    """

    GRAPH_BASE_URL = "https://graph.facebook.com"

    def __init__(self):
        self.app_id = settings.META_APP_ID
        self.app_secret = settings.META_APP_SECRET
        self.redirect_uri = settings.META_REDIRECT_URI
        self.api_version = settings.META_GRAPH_API_VERSION

    def _require_credentials(self) -> None:
        if not (self.app_id and self.app_secret and self.redirect_uri):
            raise MetaCredentialsMissingError(
                "Meta credentials are not configured. Set META_APP_ID, "
                "META_APP_SECRET and META_REDIRECT_URI to use the live "
                "Instagram integration, or use INSTAGRAM_PROVIDER=mock."
            )

    def authenticate(self, authorization_code: str | None = None) -> ProviderAccount:
        self._require_credentials()
        raise NotImplementedError(
            "MetaInstagramProvider.authenticate is a structural placeholder "
            "for the official Meta OAuth flow and is not implemented in this MVP."
        )

    def get_account(self, ig_user_id: str) -> ProviderAccount:
        self._require_credentials()
        raise NotImplementedError("MetaInstagramProvider.get_account is not implemented in this MVP.")

    def get_media(self, ig_user_id: str, limit: int = 50) -> list[ProviderMedia]:
        self._require_credentials()
        raise NotImplementedError("MetaInstagramProvider.get_media is not implemented in this MVP.")

    def get_media_insights(self, ig_media_id: str) -> ProviderMediaInsights:
        self._require_credentials()
        raise NotImplementedError("MetaInstagramProvider.get_media_insights is not implemented in this MVP.")

    def get_account_insights(self, ig_user_id: str) -> dict:
        self._require_credentials()
        raise NotImplementedError("MetaInstagramProvider.get_account_insights is not implemented in this MVP.")
