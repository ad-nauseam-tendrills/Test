from pydantic import BaseModel

from app.schemas.instagram import InstagramPostRead


class OverviewStats(BaseModel):
    total_posts: int
    avg_reach: float | None
    avg_engagement_rate: float | None
    avg_saves: float | None
    has_enough_data: bool
    message: str | None = None


class DayOfWeekStat(BaseModel):
    day: str  # "Monday", ...
    day_index: int  # 0=Monday
    post_count: int
    avg_engagement_rate: float | None


class HourOfDayStat(BaseModel):
    hour: int  # 0-23
    post_count: int
    avg_engagement_rate: float | None


class MediaTypeStat(BaseModel):
    media_type: str
    post_count: int
    avg_engagement_rate: float | None
    avg_reach: float | None


class DashboardResponse(BaseModel):
    overview: OverviewStats
    best_posts: list[InstagramPostRead]
    recent_posts: list[InstagramPostRead]
    by_day_of_week: list[DayOfWeekStat]
    by_hour_of_day: list[HourOfDayStat]
    by_media_type: list[MediaTypeStat]
    has_enough_data: bool
    insufficient_data_message: str | None = None
