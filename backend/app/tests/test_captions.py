"""
Caption generator tests.

Both vendor clients are stubbed throughout -- these tests never make a
network call and never need a real API key.
"""
import io
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from app.core.config import settings
from app.services.captions.generator import (
    MAX_IMAGE_EDGE,
    CaptionContext,
    CaptionOption,
    CaptionProviderError,
    CaptionsNotConfiguredError,
    CaptionSuggestions,
    _build_openai_input,
    _build_user_content,
    _encode_image,
    active_caption_model,
    generate_captions,
)


@pytest.fixture()
def sample_image(tmp_path):
    arr = np.random.default_rng(0).integers(0, 255, (900, 1400, 3), dtype=np.uint8)
    path = tmp_path / "art.jpg"
    Image.fromarray(arr).save(path)
    return str(path)


# --- Configuration guard -------------------------------------------------


def test_raises_clearly_without_api_key(monkeypatch, sample_image):
    monkeypatch.setattr(settings, "CAPTION_PROVIDER", "anthropic")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    with pytest.raises(CaptionsNotConfiguredError) as exc:
        generate_captions(CaptionContext(image_path=sample_image))
    assert "ANTHROPIC_API_KEY" in str(exc.value)


# --- Image encoding ------------------------------------------------------


def test_encode_image_downscales_large_images(tmp_path):
    arr = np.zeros((3000, 4000, 3), dtype=np.uint8)
    path = tmp_path / "big.jpg"
    Image.fromarray(arr).save(path)

    media_type, encoded = _encode_image(str(path))

    assert media_type == "image/jpeg"
    import base64

    with Image.open(io.BytesIO(base64.b64decode(encoded))) as im:
        assert max(im.size) <= MAX_IMAGE_EDGE


def test_encode_image_converts_png_to_jpeg(tmp_path):
    path = tmp_path / "art.png"
    Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8)).save(path)
    media_type, _ = _encode_image(str(path))
    assert media_type == "image/jpeg"


# --- Prompt construction -------------------------------------------------


def test_user_content_includes_image_and_text(sample_image):
    content = _build_user_content(CaptionContext(image_path=sample_image))
    assert content[0]["type"] == "image"
    assert content[0]["source"]["type"] == "base64"
    assert content[1]["type"] == "text"


def test_past_captions_are_included_for_voice(sample_image):
    context = CaptionContext(
        image_path=sample_image,
        past_captions=["Studio light this morning.", "Back to film for this series."],
    )
    text = _build_user_content(context)[1]["text"]
    assert "Studio light this morning." in text
    assert "voice reference" in text


def test_absent_past_captions_are_handled(sample_image):
    text = _build_user_content(CaptionContext(image_path=sample_image))[1]["text"]
    assert "No past captions are available" in text


def test_measured_properties_are_described(sample_image):
    context = CaptionContext(
        image_path=sample_image, brightness=40.0, dominant_colors=["#111111", "#222222"], face_count=2
    )
    text = _build_user_content(context)[1]["text"]
    assert "dark" in text
    assert "#111111" in text
    assert "2 face(s)" in text


def test_past_captions_are_capped(sample_image):
    context = CaptionContext(
        image_path=sample_image, past_captions=[f"caption number {i}" for i in range(50)]
    )
    text = _build_user_content(context)[1]["text"]
    # Only the sample window is sent, not the whole history.
    assert text.count("caption number") <= 8


# --- Generation ----------------------------------------------------------


class _StubMessages:
    def __init__(self, response):
        self._response = response
        self.captured = {}

    def parse(self, **kwargs):
        self.captured.update(kwargs)
        return self._response


class _StubClient:
    def __init__(self, response):
        self.messages = _StubMessages(response)


def _stub_response(options, stop_reason="end_turn"):
    return SimpleNamespace(
        parsed_output=CaptionSuggestions(options=options),
        stop_reason=stop_reason,
        stop_details=None,
    )


def _install_stub(monkeypatch, response):
    stub = _StubClient(response)
    monkeypatch.setattr(settings, "CAPTION_PROVIDER", "anthropic")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    # The generator imports the SDK lazily, so patch the module attribute
    # it looks up rather than a name bound at import time.
    monkeypatch.setattr("anthropic.Anthropic", lambda **_: stub)
    return stub


def test_generate_captions_returns_options(monkeypatch, sample_image):
    stub = _install_stub(
        monkeypatch,
        _stub_response(
            [
                CaptionOption(text="A quiet study in grey.", approach="quiet observation"),
                CaptionOption(text="Three weeks on this one.", approach="process note"),
            ]
        ),
    )

    options = generate_captions(CaptionContext(image_path=sample_image))

    assert [o.text for o in options] == ["A quiet study in grey.", "Three weeks on this one."]
    assert options[0].approach == "quiet observation"


def test_generate_captions_uses_configured_model(monkeypatch, sample_image):
    stub = _install_stub(monkeypatch, _stub_response([CaptionOption(text="x", approach="y")]))
    generate_captions(CaptionContext(image_path=sample_image))
    assert stub.messages.captured["model"] == settings.CAPTION_MODEL
    assert stub.messages.captured["output_format"] is CaptionSuggestions


def test_refusal_is_surfaced_not_swallowed(monkeypatch, sample_image):
    _install_stub(monkeypatch, _stub_response([], stop_reason="refusal"))
    with pytest.raises(CaptionsNotConfiguredError):
        generate_captions(CaptionContext(image_path=sample_image))


def test_empty_parse_result_yields_empty_list(monkeypatch, sample_image):
    response = SimpleNamespace(parsed_output=None, stop_reason="end_turn", stop_details=None)
    _install_stub(monkeypatch, response)
    assert generate_captions(CaptionContext(image_path=sample_image)) == []


def test_system_prompt_forbids_engagement_claims():
    from app.services.captions.generator import SYSTEM_PROMPT

    lowered = SYSTEM_PROMPT.lower()
    assert "never promise or imply reach, likes, or follower growth" in lowered
    assert "no engagement bait" in lowered


# --- OpenAI provider -----------------------------------------------------
#
# The point of these is that swapping CAPTION_PROVIDER changes only which
# API is called -- the prompt, the schema, and the returned options stay
# identical, so the rest of the app cannot tell the difference.


class _StubResponses:
    def __init__(self, response):
        self._response = response
        self.captured = {}

    def parse(self, **kwargs):
        self.captured.update(kwargs)
        return self._response


class _StubOpenAIClient:
    def __init__(self, response):
        self.responses = _StubResponses(response)


def _openai_response(options, refusal=None):
    output = []
    if refusal is not None:
        output = [SimpleNamespace(content=[SimpleNamespace(type="refusal", refusal=refusal)])]
    return SimpleNamespace(
        output_parsed=CaptionSuggestions(options=options) if options is not None else None,
        output=output,
    )


def _install_openai_stub(monkeypatch, response):
    stub = _StubOpenAIClient(response)
    monkeypatch.setattr(settings, "CAPTION_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("openai.OpenAI", lambda **_: stub)
    return stub


def test_openai_provider_returns_the_same_option_shape(monkeypatch, sample_image):
    _install_openai_stub(
        monkeypatch,
        _openai_response(
            [
                CaptionOption(text="Low light, long wait.", approach="quiet observation"),
                CaptionOption(text="Fourth attempt at this frame.", approach="process note"),
            ]
        ),
    )

    options = generate_captions(CaptionContext(image_path=sample_image))

    assert [o.text for o in options] == ["Low light, long wait.", "Fourth attempt at this frame."]
    assert options[0].approach == "quiet observation"


def test_openai_request_carries_the_image_schema_and_model(monkeypatch, sample_image):
    monkeypatch.setattr(settings, "OPENAI_CAPTION_MODEL", "test-vision-model")
    stub = _install_openai_stub(monkeypatch, _openai_response([CaptionOption(text="x", approach="y")]))

    generate_captions(CaptionContext(image_path=sample_image))

    captured = stub.responses.captured
    assert captured["model"] == "test-vision-model"
    assert captured["text_format"] is CaptionSuggestions
    # The same schema and system prompt as the Anthropic path.
    assert "Never promise or imply reach" in captured["instructions"]
    parts = captured["input"][0]["content"]
    assert parts[0]["type"] == "input_image"
    assert parts[0]["image_url"].startswith("data:image/jpeg;base64,")
    assert parts[1]["type"] == "input_text"


def test_openai_missing_key_is_reported_clearly(monkeypatch, sample_image):
    monkeypatch.setattr(settings, "CAPTION_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    with pytest.raises(CaptionsNotConfiguredError) as exc:
        generate_captions(CaptionContext(image_path=sample_image))
    assert "OPENAI_API_KEY" in str(exc.value)


def test_openai_refusal_is_not_reported_as_empty(monkeypatch, sample_image):
    """
    OpenAI returns a refusal as a content part with output_parsed=None.
    Reporting that as "no captions" would hide why nothing came back.
    """
    _install_openai_stub(monkeypatch, _openai_response(None, refusal="I can't help with that."))
    with pytest.raises(CaptionsNotConfiguredError) as exc:
        generate_captions(CaptionContext(image_path=sample_image))
    assert "declined" in str(exc.value)


def test_openai_api_error_becomes_provider_error(monkeypatch, sample_image):
    """Vendor SDK errors must not escape into the route layer."""
    import openai

    class _Failing:
        def parse(self, **_):
            raise openai.APIConnectionError(request=None)

    monkeypatch.setattr(settings, "CAPTION_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "openai.OpenAI", lambda **_: SimpleNamespace(responses=_Failing())
    )

    with pytest.raises(CaptionProviderError) as exc:
        generate_captions(CaptionContext(image_path=sample_image))
    assert "OpenAI" in str(exc.value)


def test_unknown_provider_is_rejected(monkeypatch, sample_image):
    monkeypatch.setattr(settings, "CAPTION_PROVIDER", "gemini")
    with pytest.raises(CaptionsNotConfiguredError) as exc:
        generate_captions(CaptionContext(image_path=sample_image))
    assert "gemini" in str(exc.value)


def test_active_caption_model_follows_the_provider(monkeypatch):
    monkeypatch.setattr(settings, "CAPTION_MODEL", "claude-test")
    monkeypatch.setattr(settings, "OPENAI_CAPTION_MODEL", "openai-test")

    monkeypatch.setattr(settings, "CAPTION_PROVIDER", "anthropic")
    assert active_caption_model() == "claude-test"
    monkeypatch.setattr(settings, "CAPTION_PROVIDER", "openai")
    assert active_caption_model() == "openai-test"


def test_both_providers_send_identical_prompt_text(sample_image):
    context = CaptionContext(image_path=sample_image, past_captions=["a quiet one"])
    anthropic_text = _build_user_content(context)[1]["text"]
    openai_text = _build_openai_input(context)[0]["content"][1]["text"]
    assert anthropic_text == openai_text
