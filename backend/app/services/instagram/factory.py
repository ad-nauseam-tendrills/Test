from app.core.config import settings
from app.services.instagram.base import InstagramProvider
from app.services.instagram.meta_provider import MetaInstagramProvider
from app.services.instagram.mock_provider import MockInstagramProvider


def get_provider(name: str | None = None) -> InstagramProvider:
    """Resolve an InstagramProvider by name, defaulting to configured provider."""
    provider_name = (name or settings.INSTAGRAM_PROVIDER).lower()
    if provider_name == "meta":
        return MetaInstagramProvider()
    return MockInstagramProvider()
