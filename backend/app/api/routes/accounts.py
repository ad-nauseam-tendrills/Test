from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.instagram_account import InstagramAccount
from app.models.instagram_post import InstagramPost
from app.models.instagram_post_metric import InstagramPostMetric
from app.models.user import User
from app.schemas.instagram import (
    ConnectAccountRequest,
    ImportPostsResponse,
    InstagramAccountRead,
)
from app.services.instagram.factory import get_provider

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[InstagramAccountRead])
def list_accounts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(InstagramAccount)
        .filter(InstagramAccount.user_id == current_user.id)
        .order_by(InstagramAccount.created_at.desc())
        .all()
    )


@router.post("/connect", response_model=InstagramAccountRead, status_code=status.HTTP_201_CREATED)
def connect_account(
    payload: ConnectAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    provider = get_provider(payload.provider)
    provider_account = provider.authenticate(payload.authorization_code)

    existing = (
        db.query(InstagramAccount)
        .filter(
            InstagramAccount.user_id == current_user.id,
            InstagramAccount.ig_user_id == provider_account.ig_user_id,
        )
        .first()
    )
    if existing:
        existing.username = provider_account.username
        existing.follower_count = provider_account.follower_count
        existing.access_token = provider_account.access_token
        existing.token_expires_at = provider_account.token_expires_at
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    account = InstagramAccount(
        user_id=current_user.id,
        provider=payload.provider,
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
    return account


@router.post("/{account_id}/disconnect", response_model=InstagramAccountRead)
def disconnect_account(
    account_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    account = _get_owned_account(db, account_id, current_user)
    account.is_active = False
    db.commit()
    db.refresh(account)
    return account


@router.post("/{account_id}/import", response_model=ImportPostsResponse)
def import_posts(
    account_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    account = _get_owned_account(db, account_id, current_user)
    provider = get_provider(account.provider)

    media_items = provider.get_media(account.ig_user_id, limit=60)

    imported, skipped = 0, 0
    for media in media_items:
        existing = (
            db.query(InstagramPost)
            .filter(InstagramPost.account_id == account.id, InstagramPost.ig_media_id == media.ig_media_id)
            .first()
        )
        if existing:
            skipped += 1
            continue

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

        metric = InstagramPostMetric(
            post_id=post.id,
            likes=media.insights.likes,
            comments=media.insights.comments,
            saves=media.insights.saves,
            shares=media.insights.shares,
            reach=media.insights.reach,
            impressions=media.insights.impressions,
            profile_visits=media.insights.profile_visits,
        )
        db.add(metric)
        imported += 1

    account.last_synced_at = datetime.now(timezone.utc)
    db.commit()

    return ImportPostsResponse(imported_count=imported, skipped_count=skipped)


def _get_owned_account(db: Session, account_id: str, user: User) -> InstagramAccount:
    account = db.get(InstagramAccount, account_id)
    if not account or account.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instagram account not found")
    return account
