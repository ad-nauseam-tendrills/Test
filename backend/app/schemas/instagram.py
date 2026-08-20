import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InstagramAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    ig_user_id: str
    username: str
    account_type: str
    profile_picture_url: str | None
    follower_count: int | None
    is_active: bool
    last_synced_at: datetime | None
    demographics_synced_at: datetime | None = None


class ConnectAccountRequest(BaseModel):
    provider: str = "mock"
    # For the placeholder Meta provider this would be the OAuth
    # authorization code returned by Meta's login dialog. Ignored by the
    # mock provider.
    authorization_code: str | None = None


class ImportPostsResponse(BaseModel):
    imported_count: int
    skipped_count: int


class PostMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    likes: int | None
    comments: int | None
    saves: int | None
    shares: int | None
    reach: int | None
    impressions: int | None
    views: int | None
    profile_visits: int | None


class InstagramPostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ig_media_id: str
    media_type: str
    caption: str | None
    media_url: str | None
    permalink: str | None
    thumbnail_url: str | None
    posted_at: datetime
    follower_count_at_posting: int | None
    metrics: PostMetricRead | None

    # Derived, normalized fields computed at read time.
    engagement_rate: float | None = None
    performance_index: float | None = None
