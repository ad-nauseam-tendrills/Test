import pytest

from app.services.instagram.factory import get_provider
from app.services.instagram.meta_provider import MetaCredentialsMissingError, MetaInstagramProvider
from app.services.instagram.mock_provider import MockInstagramProvider


def test_mock_provider_authenticate_returns_account():
    provider = MockInstagramProvider()
    account = provider.authenticate("some-user")
    assert account.ig_user_id.startswith("mock_")
    assert account.username
    assert account.follower_count > 0
    assert account.access_token is not None


def test_mock_provider_is_deterministic_per_seed():
    provider = MockInstagramProvider()
    account_a = provider.authenticate("consistent-user")
    account_b = provider.authenticate("consistent-user")
    assert account_a.ig_user_id == account_b.ig_user_id
    assert account_a.follower_count == account_b.follower_count


def test_mock_provider_generates_at_least_30_posts():
    provider = MockInstagramProvider()
    account = provider.authenticate("history-user")
    media = provider.get_media(account.ig_user_id, limit=60)
    assert len(media) >= 30


def test_mock_provider_media_has_full_insight_fields():
    provider = MockInstagramProvider()
    account = provider.authenticate("insights-user")
    media = provider.get_media(account.ig_user_id, limit=30)
    for item in media:
        assert item.media_type in ("IMAGE", "CAROUSEL_ALBUM", "VIDEO")
        assert item.posted_at is not None
        assert item.insights.likes is not None
        assert item.insights.reach is not None
        assert item.insights.impressions is not None
        assert item.follower_count_at_posting is not None


def test_mock_provider_media_types_are_varied():
    provider = MockInstagramProvider()
    account = provider.authenticate("variety-user")
    media = provider.get_media(account.ig_user_id, limit=60)
    media_types = {m.media_type for m in media}
    assert len(media_types) > 1


def test_get_provider_factory_defaults_to_mock():
    provider = get_provider(None)
    assert isinstance(provider, MockInstagramProvider)


def test_get_provider_factory_returns_meta():
    provider = get_provider("meta")
    assert isinstance(provider, MetaInstagramProvider)


def test_meta_provider_raises_without_credentials():
    provider = MetaInstagramProvider()
    with pytest.raises(MetaCredentialsMissingError):
        provider.authenticate("some-code")


def test_meta_provider_does_not_require_credentials_to_instantiate():
    # Must not raise -- the MVP should run without any Meta credentials configured.
    provider = MetaInstagramProvider()
    assert provider is not None
