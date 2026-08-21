"""
Caption suggestions, generated from the image itself plus the artist's
own past captions.

Two model providers are supported and produce the same result shape:
Anthropic (Claude) and OpenAI, selected with CAPTION_PROVIDER. The rest
of the app talks only to `generate_captions()` and the two provider-
neutral exceptions below, so neither vendor SDK leaks into the routes.

Design constraints, matching the rest of the product:
  * Captions are a creative starting point, never a performance claim.
    The model is instructed not to promise reach or ask for engagement.
  * The artist's voice comes from their own strongest past captions, so
    suggestions read like them rather than like generic marketing copy.
  * The feature degrades cleanly when the selected provider's API key is
    unset -- the endpoint returns a clear "not configured" error rather
    than failing at import time or crashing the request.
"""
from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass

from PIL import Image
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

# Both providers downscale large images server-side anyway, so shrinking
# first saves upload time and tokens for no quality loss.
MAX_IMAGE_EDGE = 1200

# Captions are short by design, so a small ceiling is deliberate here
# rather than the usual larger default.
MAX_TOKENS = 2000

# How many of the artist's past captions to show as voice reference.
VOICE_SAMPLE_SIZE = 8

SYSTEM_PROMPT = """You write Instagram caption options for visual artists and photographers.

You will be given an image, its measured visual properties, and a sample of the \
artist's own past captions. Write caption options that sound like THIS artist -- \
match their length, punctuation, warmth or dryness, and whether they talk about \
process, materials, or nothing at all. If their captions are terse, yours are terse.

Rules:
- Never promise or imply reach, likes, or follower growth.
- No engagement bait: no "double tap if", no "comment below", no "save this".
- No hashtag walls. Suggest at most two or three hashtags, and only if the \
artist's own captions use them.
- Do not describe the image back to the viewer in flat literal terms; they can \
see it. Say something worth reading.
- Do not invent facts about the work -- its title, medium, location, or story. \
If you refer to the making of it, keep it to what the image plainly shows.
- Vary the options meaningfully: they should be different approaches, not \
three rewordings of one idea."""


class CaptionOption(BaseModel):
    text: str = Field(description="The caption itself, ready to post.")
    approach: str = Field(
        description="Two to four words naming the angle, e.g. 'process note' or 'quiet observation'."
    )


class CaptionSuggestions(BaseModel):
    options: list[CaptionOption] = Field(description="Three distinct caption options.")


class CaptionsNotConfiguredError(RuntimeError):
    """Raised when caption generation is used without an API key configured."""


class CaptionProviderError(RuntimeError):
    """
    Raised when the upstream model API fails.

    Provider-neutral on purpose: the route translates this into a 502
    without importing either vendor's SDK, which is what lets the
    provider be swapped in configuration alone.
    """


@dataclass
class CaptionContext:
    """Everything the model sees besides the image itself."""
    image_path: str
    brightness: float | None = None
    contrast: float | None = None
    dominant_colors: list[str] | None = None
    face_count: int = 0
    past_captions: list[str] | None = None


def _encode_image(path: str) -> tuple[str, str]:
    """Downscale and JPEG-encode an image for the API. Returns (media_type, base64)."""
    with Image.open(path) as im:
        im = im.convert("RGB")
        if max(im.size) > MAX_IMAGE_EDGE:
            im.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))
        buffer = io.BytesIO()
        im.save(buffer, format="JPEG", quality=85)
    return "image/jpeg", base64.standard_b64encode(buffer.getvalue()).decode("utf-8")


def _build_prompt_text(context: CaptionContext) -> str:
    """The text half of the request, identical across providers."""
    details: list[str] = []
    if context.brightness is not None:
        tone = "dark" if context.brightness < 80 else "bright" if context.brightness > 180 else "mid-toned"
        details.append(f"Overall tone: {tone}.")
    if context.dominant_colors:
        details.append(f"Dominant colors: {', '.join(context.dominant_colors[:4])}.")
    if context.face_count:
        details.append(f"{context.face_count} face(s) detected.")

    if context.past_captions:
        sample = "\n".join(f"- {c}" for c in context.past_captions[:VOICE_SAMPLE_SIZE])
        voice = f"\n\nThe artist's own past captions, for voice reference:\n{sample}"
    else:
        voice = (
            "\n\nNo past captions are available for this account, so infer a "
            "restrained, artist-appropriate voice rather than imitating one."
        )

    return (
        "Write three caption options for this image."
        + (f"\n\nMeasured properties: {' '.join(details)}" if details else "")
        + voice
    )


def _build_user_content(context: CaptionContext) -> list[dict]:
    """Anthropic message content: an image block plus a text block."""
    media_type, encoded = _encode_image(context.image_path)
    return [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded}},
        {"type": "text", "text": _build_prompt_text(context)},
    ]


def _build_openai_input(context: CaptionContext) -> list[dict]:
    """OpenAI Responses input: the same two parts in that API's shape."""
    media_type, encoded = _encode_image(context.image_path)
    return [
        {
            "role": "user",
            "content": [
                {"type": "input_image", "image_url": f"data:{media_type};base64,{encoded}"},
                {"type": "input_text", "text": _build_prompt_text(context)},
            ],
        }
    ]


REFUSAL_MESSAGE = "The model declined to write captions for this image. Try a different image."


def active_caption_model() -> str:
    """
    The model name the configured provider will actually use. Stored
    against each generated caption, so a provider switch stays visible in
    the history rather than mislabeling old rows.
    """
    if settings.CAPTION_PROVIDER == "openai":
        return settings.OPENAI_CAPTION_MODEL
    return settings.CAPTION_MODEL


def _generate_anthropic(context: CaptionContext) -> list[CaptionOption]:
    import anthropic

    if not settings.ANTHROPIC_API_KEY:
        raise CaptionsNotConfiguredError(
            "Caption generation is not configured. Set ANTHROPIC_API_KEY to enable it, "
            "or set CAPTION_PROVIDER=openai to use OpenAI instead."
        )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        response = client.messages.parse(
            model=settings.CAPTION_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_content(context)}],
            output_format=CaptionSuggestions,
        )
    except anthropic.APIConnectionError as exc:
        raise CaptionProviderError(
            "Could not reach Anthropic. Check the server's network access."
        ) from exc
    except anthropic.APIStatusError as exc:
        raise CaptionProviderError(f"Anthropic returned an error: {exc.message}") from exc

    if response.stop_reason == "refusal":
        logger.warning(
            "Caption generation refused: %s", getattr(response.stop_details, "category", None)
        )
        raise CaptionsNotConfiguredError(REFUSAL_MESSAGE)

    parsed = response.parsed_output
    return parsed.options if parsed else []


def _generate_openai(context: CaptionContext) -> list[CaptionOption]:
    import openai

    if not settings.OPENAI_API_KEY:
        raise CaptionsNotConfiguredError(
            "Caption generation is not configured. Set OPENAI_API_KEY to enable it."
        )

    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        response = client.responses.parse(
            model=settings.OPENAI_CAPTION_MODEL,
            max_output_tokens=MAX_TOKENS,
            instructions=SYSTEM_PROMPT,
            input=_build_openai_input(context),
            text_format=CaptionSuggestions,
        )
    except openai.APIConnectionError as exc:
        raise CaptionProviderError(
            "Could not reach OpenAI. Check the server's network access."
        ) from exc
    except openai.APIStatusError as exc:
        raise CaptionProviderError(f"OpenAI returned an error: {exc.message}") from exc

    # A refusal arrives as a content part rather than a status, and
    # output_parsed is None in that case -- so check it explicitly rather
    # than reporting "no captions" for what is really a declined request.
    for item in getattr(response, "output", None) or []:
        for part in getattr(item, "content", None) or []:
            if getattr(part, "type", None) == "refusal":
                logger.warning("Caption generation refused: %s", getattr(part, "refusal", ""))
                raise CaptionsNotConfiguredError(REFUSAL_MESSAGE)

    parsed = response.output_parsed
    return parsed.options if parsed else []


def generate_captions(context: CaptionContext) -> list[CaptionOption]:
    """
    Generate caption options for an image using the configured provider.

    Raises CaptionsNotConfiguredError when the provider has no API key (or
    declined the image), and CaptionProviderError when the upstream API
    fails. Both are provider-neutral so the route needs no vendor imports.
    """
    provider = settings.CAPTION_PROVIDER.lower()
    if provider == "openai":
        return _generate_openai(context)
    if provider == "anthropic":
        return _generate_anthropic(context)
    raise CaptionsNotConfiguredError(
        f"Unknown CAPTION_PROVIDER {settings.CAPTION_PROVIDER!r}. Use 'anthropic' or 'openai'."
    )
