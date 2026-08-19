"""
Seed the database with a demo user, a connected mock Instagram account, and
60 historical posts (well above the 30-post minimum requested for a
meaningful dashboard).

Usage (from backend/):
    python -m scripts.seed_mock_data
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import hash_password
from app.db.all_models import Base
from app.db.session import SessionLocal, engine
from app.models.instagram_account import InstagramAccount
from app.models.instagram_post import InstagramPost
from app.models.instagram_post_metric import InstagramPostMetric
from app.models.user import User
from app.services.instagram.mock_provider import MockInstagramProvider

DEMO_EMAIL = "demo@artstudio.example"
DEMO_PASSWORD = "demo12345"


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if not user:
            user = User(
                email=DEMO_EMAIL,
                hashed_password=hash_password(DEMO_PASSWORD),
                full_name="Demo Artist",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Created demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        else:
            print(f"Demo user already exists: {DEMO_EMAIL}")

        provider = MockInstagramProvider()
        provider_account = provider.authenticate("demo-artist-seed")

        account = (
            db.query(InstagramAccount)
            .filter(InstagramAccount.user_id == user.id, InstagramAccount.ig_user_id == provider_account.ig_user_id)
            .first()
        )
        if not account:
            account = InstagramAccount(
                user_id=user.id,
                provider="mock",
                ig_user_id=provider_account.ig_user_id,
                username=provider_account.username,
                account_type=provider_account.account_type,
                profile_picture_url=provider_account.profile_picture_url,
                follower_count=provider_account.follower_count,
                access_token=provider_account.access_token,
                token_expires_at=provider_account.token_expires_at,
                is_active=True,
            )
            db.add(account)
            db.commit()
            db.refresh(account)
            print(f"Connected mock Instagram account: @{account.username}")
        else:
            print(f"Mock account already connected: @{account.username}")

        existing_count = db.query(InstagramPost).filter(InstagramPost.account_id == account.id).count()
        if existing_count > 0:
            print(f"Account already has {existing_count} imported posts, skipping import.")
            return

        media_items = provider.get_media(account.ig_user_id, limit=60)
        for media in media_items:
            post = InstagramPost(
                account_id=account.id,
                ig_media_id=media.ig_media_id,
                media_type=media.media_type,
                caption=media.caption,
                media_url=media.media_url,
                permalink=media.permalink,
                thumbnail_url=media.thumbnail_url,
                posted_at=media.posted_at,
                follower_count_at_posting=media.follower_count_at_posting,
            )
            db.add(post)
            db.flush()
            db.add(
                InstagramPostMetric(
                    post_id=post.id,
                    likes=media.insights.likes,
                    comments=media.insights.comments,
                    saves=media.insights.saves,
                    shares=media.insights.shares,
                    reach=media.insights.reach,
                    impressions=media.insights.impressions,
                    profile_visits=media.insights.profile_visits,
                )
            )
        db.commit()
        print(f"Imported {len(media_items)} historical posts for @{account.username}.")
        print("\nDemo login:")
        print(f"  email:    {DEMO_EMAIL}")
        print(f"  password: {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
