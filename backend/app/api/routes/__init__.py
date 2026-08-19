from fastapi import APIRouter

from app.api.routes import accounts, analytics, auth, images, posts, settings

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(accounts.router)
api_router.include_router(posts.router)
api_router.include_router(analytics.router)
api_router.include_router(images.router)
api_router.include_router(settings.router)
