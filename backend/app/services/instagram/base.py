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
    impressions: int | None = None
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
    """Abstract Instagram integration surface."""

    @abstractmethod
    def authenticate(self, authorization_code: str | None = None) -> ProviderAccount:
        """
        Exchange an OAuth authorization code (or, for mock providers,
        a synthetic identifier) for an authenticated account handle.
        """
        raise NotImplementedError

    @abstractmethod
    def get_account(self, ig_user_id: str) -> ProviderAccount:
        """Fetch current profile info for a connected account."""
        raise NotImplementedError

    @abstractmethod
    def get_media(self, ig_user_id: str, limit: int = 50) -> list[ProviderMedia]:
        """Fetch historical media (posts) for an account, without insights."""
        raise NotImplementedError

    @abstractmethod
    def get_media_insights(self, ig_media_id: str) -> ProviderMediaInsights:
        """Fetch engagement insights for a single media item."""
        raise NotImplementedError

    @abstractmethod
    def get_account_insights(self, ig_user_id: str) -> dict:
        """Fetch account-level insights (e.g. follower count history)."""
        raise NotImplementedError
