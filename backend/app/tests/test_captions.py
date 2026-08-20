"""
Caption generator tests.

The Anthropic client is stubbed throughout -- these tests never make a
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
    CaptionsNotConfiguredError,
    CaptionSuggestions,
    _build_user_content,
    _encode_image,
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
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr("app.services.captions.generator.anthropic.Anthropic", lambda **_: stub)
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
