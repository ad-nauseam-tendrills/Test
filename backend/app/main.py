import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings
from app.core.storage import ensure_storage_dirs


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_storage_dirs()
    if settings.SINGLE_USER_MODE:
        # Loud on purpose: this is the difference between "personal tool"
        # and "anyone who finds the URL is me".
        logger.warning(
            "SINGLE_USER_MODE is ON -- authentication is bypassed and every "
            "request runs as the owner account. Restrict network access to "
            "this deployment."
        )
    yield


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
