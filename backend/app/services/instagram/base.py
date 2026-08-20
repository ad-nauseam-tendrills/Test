"""
Instagram provider abstraction.

Every concrete provider (mock, Meta Graph API, ...) implements this
interface so the rest of the application never talks to a specific
integration directly. This keeps the mock/demo path and the real Meta
integration interchangeable and testable in isolation.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ProviderAccount:
    ig_user_id: str
    username: str
    account_type: str
    profile_picture_url: str | None
    follower_count: int | None
    access_token: str | None = None
    token_expires_at: datetime | None = None


@dataclass
class ProviderMediaInsights:
    likes: int | None = None
    comments: int | None = None
    saves: int | None = None
    shares: int | None = None
    reach: int | None = None
    # `impressions` is deprecated by Meta for media created after
    # 2024-07-02 and replaced by `views`. Both are kept so older imported
    # media retains its impressions value while newer media populates
    # views; analytics treats either as a valid denominator.
    impressions: int | None = None
    views: int | None = None
    # Account-level in Meta's API, not per-media -- the real provider
    # leaves this None and it is only populated by the mock provider.
    profile_visits: int | None = None


@dataclass
class ProviderMedia:
    ig_media_id: str
    media_type: str  # IMAGE, VIDEO, CAROUSEL_ALBUM
    caption: str | None
    media_url: str | None
    permalink: str | None
    thumbnail_url: str | None
    posted_at: datetime
    follower_count_at_posting: int | None = None
    insights: ProviderMediaInsights = field(default_factory=ProviderMediaInsights)


class InstagramProvider(ABC):
    """
    Abstract Instagram integration surface.

    `access_token` is accepted by every data-fetching method because real
    providers need per-account credentials to make requests. The mock
    provider ignores it. Tokens are always passed in explicitly rather
    than held as provider state, so a single provider instance can never
    accidentally serve one account's data using another's credentials.
    """

    @abstractmethod
    def authenticate(self, authorization_code: str | None = None) -> ProviderAccount:
        """
        Exchange an OAuth authorization code (or, for mock providers,
        a synthetic identifier) for an authenticated account handle.
        """
        raise NotImplementedError

    @abstractmethod
    def get_account(self, ig_user_id: str, access_token: str | None = None) -> ProviderAccount:
        """Fetch current profile info for a connected account."""
        raise NotImplementedError

    @abstractmethod
    def get_media(
        self, ig_user_id: str, limit: int = 50, access_token: str | None = None
    ) -> list[ProviderMedia]:
        """Fetch historical media (posts) for an account, with insights attached."""
        raise NotImplementedError

    @abstractmethod
    def get_media_insights(
        self, ig_media_id: str, access_token: str | None = None
    ) -> ProviderMediaInsights:
        """Fetch engagement insights for a single media item."""
        raise NotImplementedError

    @abstractmethod
    def get_account_insights(self, ig_user_id: str, access_token: str | None = None) -> dict:
        """Fetch account-level insights (e.g. reach, views)."""
        raise NotImplementedError

    @abstractmethod
    def get_follower_demographics(
        self, ig_user_id: str, access_token: str | None = None
    ) -> dict[str, int]:
        """
        Follower counts keyed by ISO-3166 alpha-2 country code.

        Returns an empty dict when the breakdown is unavailable -- Meta
        withholds it below 100 followers, and callers must treat that as
        "unknown" rather than "no followers abroad".
        """
        raise NotImplementedError
