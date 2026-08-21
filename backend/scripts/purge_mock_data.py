"""
Delete every mock/demo Instagram account and the posts imported from it.

Undoes scripts/seed_mock_data.py. Use this on a deployment that was seeded
with demo data before it had a real Instagram account connected -- the
dashboard reads whatever is in the database, so synthetic posts skew every
recommendation until they are gone.

Real accounts (provider="meta") are never touched.

Usage (from backend/):
    python -m scripts.purge_mock_data            # accounts + their posts
    python -m scripts.purge_mock_data --user     # also delete the demo user
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Imported for its side effect: it registers every model, so SQLAlchemy can
# resolve the string-named relationships between them. Without it, the
# first query fails to locate InstagramPostMetric.
import app.db.all_models  # noqa: F401
from app.db.session import SessionLocal
from app.models.instagram_account import InstagramAccount
from app.models.instagram_post import InstagramPost
from app.models.user import User

DEMO_EMAIL = "demo@artstudio.example"


def run(drop_user: bool = False):
    db = SessionLocal()
    try:
        accounts = db.query(InstagramAccount).filter(InstagramAccount.provider == "mock").all()
        if not accounts:
            print("No mock accounts found -- nothing to purge.")
        for account in accounts:
            post_count = (
                db.query(InstagramPost).filter(InstagramPost.account_id == account.id).count()
            )
            # Posts and their metrics go with the account via cascade.
            db.delete(account)
            print(f"Deleted mock account @{account.username} and {post_count} posts.")
        db.commit()

        if drop_user:
            user = db.query(User).filter(User.email == DEMO_EMAIL).first()
            if user is None:
                print(f"No demo user {DEMO_EMAIL} to delete.")
            elif user.instagram_accounts:
                # Only mock accounts were removed above, so anything left is
                # real -- deleting the user would take it with them.
                print(
                    f"Refusing to delete {DEMO_EMAIL}: it still owns "
                    f"{len(user.instagram_accounts)} connected account(s)."
                )
            else:
                db.delete(user)
                db.commit()
                print(f"Deleted demo user {DEMO_EMAIL}.")
    finally:
        db.close()


if __name__ == "__main__":
    run(drop_user="--user" in sys.argv[1:])
