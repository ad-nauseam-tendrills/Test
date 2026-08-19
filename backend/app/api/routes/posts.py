from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.instagram_account import InstagramAccount
from app.models.instagram_post import InstagramPost
from app.models.user import User
from app.schemas.instagram import InstagramPostRead
from app.services.analytics.dashboard import annotate_post

router = APIRouter(prefix="/posts", tags=["posts"])


def _account_ids_for_user(db: Session, user: User) -> list:
    return [a.id for a in db.query(InstagramAccount).filter(InstagramAccount.user_id == user.id).all()]


@router.get("", response_model=list[InstagramPostRead])
def list_posts(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account_ids = _account_ids_for_user(db, current_user)
    if not account_ids:
        return []

    posts = (
        db.query(InstagramPost)
        .options(joinedload(InstagramPost.metrics))
        .filter(InstagramPost.account_id.in_(account_ids))
        .order_by(InstagramPost.posted_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    all_rates = []
    results = []
    for p in posts:
        extra = annotate_post(p, [])
        if extra["engagement_rate"] is not None:
            all_rates.append(extra["engagement_rate"])
        results.append((p, extra))

    output = []
    for p, extra in results:
        extra["performance_index"] = None  # computed against full history in dashboard endpoint
        item = InstagramPostRead.model_validate(p)
        item.engagement_rate = extra["engagement_rate"]
        output.append(item)
    return output


@router.get("/{post_id}", response_model=InstagramPostRead)
def get_post(post_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    account_ids = _account_ids_for_user(db, current_user)
    post = (
        db.query(InstagramPost)
        .options(joinedload(InstagramPost.metrics))
        .filter(InstagramPost.id == post_id)
        .first()
    )
    if not post or post.account_id not in account_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    extra = annotate_post(post, [])
    item = InstagramPostRead.model_validate(post)
    item.engagement_rate = extra["engagement_rate"]
    return item
