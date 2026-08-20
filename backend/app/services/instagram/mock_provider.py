"""
Mock Instagram provider.

Generates realistic-looking historical post data so the application can be
developed, demoed, and tested end-to-end without any real Meta credentials.
No network calls are made and no Instagram data is ever scraped -- this is
entirely synthetic data generated locally.
"""
import hashlib
import random
from datetime import datetime, timedelta, timezone

from app.services.instagram.base import (
    InstagramProvider,
    ProviderAccount,
    ProviderMedia,
    ProviderMediaInsights,
)

MEDIA_TYPES = ["IMAGE", "IMAGE", "IMAGE", "CAROUSEL_ALBUM", "CAROUSEL_ALBUM", "VIDEO"]

CAPTION_SNIPPETS = [
    "New piece finished after three weeks of work. Swipe to see the detail shots.",
    "Studio light this morning was too good not to shoot.",
    "Experimenting with a new color palette for this series.",
    "Behind the scenes from this week's shoot.",
    "This one almost didn't happen -- glad I kept going.",
    "A quiet study in contrast and negative space.",
    "Back to film for this series. No regrets.",
    "Detail shot from the piece I'm showing next month.",
    "Some days the light does all the work for you.",
    "Process shot -- more of these coming if people want them.",
]

# Hashtag sets an artist might habitually reach for. A few appear often
# and a few rarely, so the hashtag analytics have both well-sampled and
# thin tags to distinguish -- which is the interesting case to demo.
HASHTAG_POOL = [
    ["#studiopractice", "#worksonpaper"],
    ["#filmphotography", "#35mm"],
    ["#studiopractice"],
    ["#contemporaryart", "#abstractpainting"],
    ["#filmphotography"],
    ["#naturalight"],
    [],
    ["#studiopractice", "#contemporaryart"],
]

def _compose_caption(rng: random.Random) -> str:
    """A caption plus the artist's habitual hashtags, as a real post would carry."""
    body = rng.choice(CAPTION_SNIPPETS)
    tags = rng.choice(HASHTAG_POOL)
    return f"{body} {' '.join(tags)}".strip() if tags else body


# Deterministic placeholder image URLs (picsum supports fixed seeds).
def _placeholder_url(seed: str, width: int = 1080, height: int = 1350) -> str:
    return f"https://picsum.photos/seed/{seed}/{width}/{height}"


class MockInstagramProvider(InstagramProvider):
    """
    Deterministic-per-account mock provider. The same ig_user_id always
    generates the same synthetic history, which keeps demos and tests
    reproducible.
    """

    def __init__(self, seed: str | None = None):
        self._seed = seed

    def _rng(self, key: str) -> random.Random:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return random.Random(int(digest[:16], 16))

    def authenticate(self, authorization_code: str | None = None) -> ProviderAccount:
        # In a real OAuth flow this would exchange a code for a token.
        # The mock provider fabricates a stable demo account instead.
        ig_user_id = "mock_" + hashlib.sha1(
            (authorization_code or "demo-artist").encode()
        ).hexdigest()[:12]
        return self.get_account(ig_user_id)

    def get_account(self, ig_user_id: str, access_token: str | None = None) -> ProviderAccount:
        rng = self._rng(ig_user_id)
        return ProviderAccount(
            ig_user_id=ig_user_id,
            username="studio_" + ig_user_id[-6:],
            account_type="BUSINESS",
            profile_picture_url=_placeholder_url(ig_user_id + "-avatar", 200, 200),
            follower_count=rng.randint(1800, 42000),
            access_token="mock-access-token",
            token_expires_at=datetime.now(timezone.utc) + timedelta(days=60),
        )

    def get_media(
        self, ig_user_id: str, limit: int = 50, access_token: str | None = None
    ) -> list[ProviderMedia]:
        rng = self._rng(ig_user_id)
        base_followers = rng.randint(1800, 42000)
        # Simulate gradual follower growth over the history window.
        growth_per_post = rng.uniform(0.5, 4.0)

        count = max(30, min(limit, 60))
        now = datetime.now(timezone.utc)
        media: list[ProviderMedia] = []

        for i in range(count):
            days_ago = (count - i) * rng.uniform(2.5, 5.5)
            posted_at = now - timedelta(days=days_ago)
            media_type = rng.choice(MEDIA_TYPES)
            followers_at_posting = max(50, int(base_followers - (count - i) * growth_per_post * 10))

            ig_media_id = f"{ig_user_id}_media_{i:03d}"
            media.append(
                ProviderMedia(
                    ig_media_id=ig_media_id,
                    media_type=media_type,
                    caption=_compose_caption(rng),
                    media_url=_placeholder_url(ig_media_id),
                    permalink=f"https://instagram.com/p/{ig_media_id}",
                    thumbnail_url=_placeholder_url(ig_media_id, 320, 400),
                    posted_at=posted_at,
                    follower_count_at_posting=followers_at_posting,
                    insights=self._generate_insights(rng, followers_at_posting, media_type, posted_at),
                )
            )
        return media

    def _generate_insights(
        self,
        rng: random.Random,
        followers: int,
        media_type: str,
        posted_at: datetime,
    ) -> ProviderMediaInsights:
        # Base engagement rate varies with a random "post quality" factor,
        # posting hour, and media type, to produce realistic patterns for
        # the analytics layer to detect (e.g. certain hours/days perform
        # better; carousels slightly outperform singles).
        quality = rng.uniform(0.5, 1.6)
        hour_factor = 1.25 if 17 <= posted_at.hour <= 21 else (0.85 if posted_at.hour < 8 else 1.0)
        weekday_factor = 1.15 if posted_at.weekday() in (2, 5, 6) else 1.0
        type_factor = {"IMAGE": 1.0, "CAROUSEL_ALBUM": 1.2, "VIDEO": 1.1}[media_type]

        base_rate = 0.03 * quality * hour_factor * weekday_factor * type_factor
        reach = int(followers * rng.uniform(0.35, 0.95))
        impressions = int(reach * rng.uniform(1.05, 1.6))
        likes = max(1, int(reach * base_rate * rng.uniform(0.8, 1.2)))
        comments = max(0, int(likes * rng.uniform(0.02, 0.08)))
        saves = max(0, int(likes * rng.uniform(0.05, 0.25) * (1.3 if media_type == "CAROUSEL_ALBUM" else 1.0)))
        shares = max(0, int(likes * rng.uniform(0.01, 0.06)))
        profile_visits = max(0, int(reach * rng.uniform(0.01, 0.05)))

        return ProviderMediaInsights(
            likes=likes,
            comments=comments,
            saves=saves,
            shares=shares,
            reach=reach,
            impressions=impressions,
            profile_visits=profile_visits,
        )

    def get_media_insights(
        self, ig_media_id: str, access_token: str | None = None
    ) -> ProviderMediaInsights:
        rng = self._rng(ig_media_id)
        followers = rng.randint(1800, 42000)
        return self._generate_insights(rng, followers, rng.choice(MEDIA_TYPES), datetime.now(timezone.utc))

    def get_account_insights(self, ig_user_id: str, access_token: str | None = None) -> dict:
        account = self.get_account(ig_user_id)
        return {
            "follower_count": account.follower_count,
            "note": "Mock provider: account-level insight history is not tracked beyond current follower_count.",
        }
