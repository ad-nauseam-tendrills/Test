import secrets
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token, hash_password
from app.db.session import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def resolve_single_user(db: Session) -> User:
    """
    The account every request runs as when SINGLE_USER_MODE is on.

    Prefers SINGLE_USER_EMAIL when set, otherwise the oldest account in
    the database -- so switching an existing deployment into single-user
    mode keeps whoever already registered, along with their connected
    Instagram account and imported history, rather than stranding it
    behind a new empty user.
    """
    if settings.SINGLE_USER_EMAIL:
        user = db.query(User).filter(User.email == settings.SINGLE_USER_EMAIL).first()
        if user:
            return user
        email = settings.SINGLE_USER_EMAIL
    else:
        user = db.query(User).order_by(User.created_at.asc()).first()
        if user:
            return user
        # UserRead validates this as an EmailStr, so the placeholder has
        # to pass a real email validator. "owner@localhost" fails (no
        # dot) and reserved TLDs like .local and .invalid are rejected
        # outright, so example.com -- reserved for documentation by
        # RFC 2606 and never deliverable -- is the safe choice.
        email = "owner@example.com"

    # Nobody to adopt -- create the owner. The password is random and
    # never shown: in single-user mode there is no login form to type it
    # into, and leaving it guessable would matter the moment the flag is
    # turned back off.
    user = User(
        email=email,
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        full_name="Owner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    # SINGLE_USER_MODE removes the login screen for a personal deployment
    # by resolving every request to one owner account. It does NOT make
    # the app private: any request that reaches it is that owner. Keep
    # the deployment behind network-level access control (a firewall,
    # HTTP basic auth at the proxy, a VPN) if the URL is reachable from
    # the internet.
    if settings.SINGLE_USER_MODE:
        return resolve_single_user(db)

    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    subject = decode_access_token(credentials.credentials)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
