from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.instagram_account import InstagramAccount
from app.models.user import User
from app.schemas.analytics import (
    AudienceReport,
    CaptionFeatureReport,
    DashboardResponse,
    DayOfWeekStat,
    HashtagReport,
    HashtagStatRead,
    HourOfDayStat,
    FeatureGroupRead,
    HourAudienceRead,
    MediaTypeStat,
    OverviewStats,
    TopCountryRead,
)
from app.schemas.instagram import InstagramPostRead
from app.services.analytics.dashboard import build_dashboard
from app.services.analytics.audience import CAVEAT as AUDIENCE_CAVEAT, analyze_audience_hours
from app.services.analytics.caption_features import (
    CAVEAT as CAPTION_FEATURE_CAVEAT,
    CaptionedPost,
    analyze_caption_features,
)
from app.services.analytics.hashtags import CAVEAT as HASHTAG_CAVEAT, TaggedPost, analyze_hashtags

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    account = (
        db.query(InstagramAccount)
        .filter(InstagramAccount.user_id == current_user.id, InstagramAccount.is_active.is_(True))
        .first()
    )
    if not account:
        empty_overview = OverviewStats(
            total_posts=0, avg_reach=None, avg_engagement_rate=None, avg_saves=None,
            has_enough_data=False, message="Connect an Instagram account to see your dashboard.",
        )
        return DashboardResponse(
            overview=empty_overview, best_posts=[], recent_posts=[], by_day_of_week=[],
            by_hour_of_day=[], by_media_type=[], has_enough_data=False,
            insufficient_data_message="Connect an Instagram account to see your dashboard.",
        )

    data = build_dashboard(db, account.id)

    def _post_to_schema(pair):
        post, extra = pair
        item = InstagramPostRead.model_validate(post)
        item.engagement_rate = extra["engagement_rate"]
        item.performance_index = extra["performance_index"]
        return item

    return DashboardResponse(
        overview=OverviewStats(**data["overview"]),
        best_posts=[_post_to_schema(p) for p in data["best_posts"]],
        recent_posts=[_post_to_schema(p) for p in data["recent_posts"]],
        by_day_of_week=[DayOfWeekStat(**d) for d in data["by_day_of_week"]],
        by_hour_of_day=[HourOfDayStat(**h) for h in data["by_hour_of_day"]],
        by_media_type=[MediaTypeStat(**m) for m in data["by_media_type"]],
        has_enough_data=data["has_enough_data"],
        insufficient_data_message=data["insufficient_data_message"],
    )


@router.get("/hashtags", response_model=HashtagReport)
def get_hashtags(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Hashtag usage and performance across this account's own history.

    Descriptive only -- see services/analytics/hashtags.py for why these
    numbers must not be presented as a causal growth lever.
    """
    account = (
        db.query(InstagramAccount)
        .filter(InstagramAccount.user_id == current_user.id, InstagramAccount.is_active.is_(True))
        .first()
    )
    if not account:
        return HashtagReport(
            has_enough_data=False,
            message="Connect an Instagram account to see hashtag insights.",
            hashtags=[],
            caveat=HASHTAG_CAVEAT,
        )

    data = build_dashboard(db, account.id)
    tagged = [
        TaggedPost(caption=post.caption, engagement_rate=extra["engagement_rate"])
        for post, extra in data["all_posts"]
    ]

    report = analyze_hashtags(tagged)
    return HashtagReport(
        has_enough_data=report["has_enough_data"],
        message=report["message"],
        hashtags=[HashtagStatRead(**vars(s)) for s in report["hashtags"]],
        caveat=report["caveat"],
    )


@router.get("/audience", response_model=AudienceReport)
def get_audience(
    utc_offset: float = Query(0.0, ge=-12, le=14, description="Viewer's UTC offset in hours"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Follower timezone spread, and what fraction of the audience is awake
    at each posting hour. Uses the cached demographics on the account --
    refresh them with POST /accounts/{id}/sync-demographics.
    """
    account = (
        db.query(InstagramAccount)
        .filter(InstagramAccount.user_id == current_user.id, InstagramAccount.is_active.is_(True))
        .first()
    )
    if not account:
        return AudienceReport(
            has_enough_data=False,
            message="Connect an Instagram account to see audience timing.",
            hours=[], top_countries=[], coverage=0.0, caveat=AUDIENCE_CAVEAT,
        )

    report = analyze_audience_hours(account.audience_countries or {}, viewer_utc_offset=utc_offset)
    return AudienceReport(
        has_enough_data=report["has_enough_data"],
        message=report["message"],
        hours=[HourAudienceRead(**vars(h)) for h in report["hours"]],
        top_countries=[TopCountryRead(**c) for c in report["top_countries"]],
        coverage=report["coverage"],
        caveat=report["caveat"],
    )


@router.get("/caption-features", response_model=CaptionFeatureReport)
def get_caption_features(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """How this account's own caption habits line up with its own engagement."""
    account = (
        db.query(InstagramAccount)
        .filter(InstagramAccount.user_id == current_user.id, InstagramAccount.is_active.is_(True))
        .first()
    )
    if not account:
        return CaptionFeatureReport(
            has_enough_data=False,
            message="Connect an Instagram account to see caption insights.",
            features=[], caveat=CAPTION_FEATURE_CAVEAT,
        )

    data = build_dashboard(db, account.id)
    captioned = [
        CaptionedPost(caption=post.caption, engagement_rate=extra["engagement_rate"])
        for post, extra in data["all_posts"]
    ]

    report = analyze_caption_features(captioned)
    return CaptionFeatureReport(
        has_enough_data=report["has_enough_data"],
        message=report["message"],
        features=[FeatureGroupRead(**vars(f)) for f in report["features"]],
        caveat=report["caveat"],
    )
