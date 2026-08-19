import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, decode_access_token
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
from app.services.instagram.meta_provider import (
    MetaApiError,
    MetaCredentialsMissingError,
    MetaInstagramProvider,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/accounts", tags=["accounts"])

# The OAuth `state` parameter is a short-lived signed token carrying the
# id of the user who started the flow. Instagram's redirect back to us is
# a plain browser navigation with no Authorization header, so this is how
# the callback knows which account to attach -- and, because it is signed
# and short-lived, it also blocks a third party from forging a callback
# that would bind their Instagram account to someone else's login.
OAUTH_STATE_TTL_MINUTES = 15


@router.get("", response_model=list[InstagramAccountRead])
def list_accounts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(InstagramAccount)
        .filter(InstagramAccount.user_id == current_user.id)
        .order_by(InstagramAccount.created_at.desc())
        .all()
    )


def _upsert_account(db: Session, user: User, provider_name: str, provider_account) -> InstagramAccount:
    """Create or refresh the stored account record for a provider result."""
    existing = (
        db.query(InstagramAccount)
        .filter(
            InstagramAccount.user_id == user.id,
            InstagramAccount.ig_user_id == provider_account.ig_user_id,
        )
        .first()
    )
    if existing:
        existing.username = provider_account.username
        existing.profile_picture_url = provider_account.profile_picture_url
        existing.follower_count = provider_account.follower_count
        existing.access_token = provider_account.access_token
        existing.token_expires_at = provider_account.token_expires_at
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    account = InstagramAccount(
        user_id=user.id,
        provider=provider_name,
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


@router.post("/connect", response_model=InstagramAccountRead, status_code=status.HTTP_201_CREATED)
def connect_account(
    payload: ConnectAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Direct connect. Used by the mock provider, which needs no OAuth round
    trip. For the real Meta provider, use /accounts/meta/authorize-url and
    let the browser complete the OAuth flow instead.
    """
    provider = get_provider(payload.provider)
    try:
        provider_account = provider.authenticate(payload.authorization_code)
    except MetaCredentialsMissingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except MetaApiError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return _upsert_account(db, current_user, payload.provider, provider_account)


@router.get("/meta/authorize-url")
def meta_authorize_url(current_user: User = Depends(get_current_user)):
    """
    Start the real Instagram OAuth flow. Returns the URL the browser
    should be sent to; Instagram will redirect back to META_REDIRECT_URI
    (which must point at /accounts/meta/callback below).
    """
    provider = MetaInstagramProvider()
    state = create_access_token(subject=str(current_user.id), expires_minutes=OAUTH_STATE_TTL_MINUTES)
    try:
        return {"authorize_url": provider.build_authorization_url(state=state)}
    except MetaCredentialsMissingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/meta/callback")
def meta_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    OAuth redirect target. Exchanges the authorization code for a
    long-lived token, stores the account, and bounces the browser back to
    the frontend settings page with a status message.

    This endpoint is unauthenticated by necessity -- Instagram redirects
    the browser here with no Authorization header -- so the caller's
    identity comes solely from the signed `state` token issued above.
    """

    def _redirect(status_value: str, message: str) -> RedirectResponse:
        query = urlencode({"instagram": status_value, "message": message})
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/settings?{query}")

    if error:
        return _redirect("error", error_description or error)
    if not code or not state:
        return _redirect("error", "Instagram did not return an authorization code.")

    subject = decode_access_token(state)
    if subject is None:
        return _redirect("error", "This connection link has expired. Please try connecting again.")

    try:
        user = db.get(User, uuid.UUID(subject))
    except ValueError:
        user = None
    if user is None:
        return _redirect("error", "Could not identify the account to connect.")

    provider = MetaInstagramProvider()
    try:
        provider_account = provider.authenticate(code)
    except (MetaCredentialsMissingError, MetaApiError) as exc:
        logger.warning("Instagram OAuth callback failed: %s", exc)
        return _redirect("error", str(exc))

    account = _upsert_account(db, user, "meta", provider_account)
    return _redirect("connected", f"Connected @{account.username}.")


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

    try:
        media_items = provider.get_media(
            account.ig_user_id, limit=60, access_token=account.access_token
        )
    except MetaCredentialsMissingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except MetaApiError as exc:
        # A stale/expired long-lived token is the most common cause here;
        # tell the user to reconnect rather than leaking API internals.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not fetch posts from Instagram: {exc}. You may need to reconnect the account.",
        )

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
            views=media.insights.views,
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
