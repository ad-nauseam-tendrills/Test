"""
Image optimization engine ("Artwork Integrity" mode).

This module only ever performs photographic *preparation* -- exposure,
white balance, contrast, highlight/shadow recovery, mild saturation
correction, sharpening, resize, crop, and simple perspective/rotation
correction. It never:
  - alters local shapes or geometry beyond crop/perspective/resize
  - retouches or repaints any region
  - adds or removes objects
  - changes composition beyond cropping

There is exactly one code path (this one) that produces optimized
images, and Artwork Integrity mode is ON by default. When
artwork_integrity_mode=True, the set of allowed adjustments is restricted
to the list above -- there is currently no "non-integrity" mode that does
anything different in this MVP; the flag is threaded through end-to-end
so a future, more aggressive editing mode could be added later without
breaking this contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image

ALLOWED_ADJUSTMENTS = {
    "exposure",
    "contrast",
    "white_balance_shift",
    "highlight_recovery",
    "shadow_recovery",
    "saturation",
    "sharpen_amount",
    "crop_box",
    "target_aspect_ratio",
    "rotation_degrees",
}


@dataclass
class Adjustments:
    exposure: float = 0.0  # -1..1, additive stops-ish brightness
    contrast: float = 0.0  # -1..1
    white_balance_shift: float = 0.0  # -1..1, negative=cooler, positive=warmer
    highlight_recovery: float = 0.0  # 0..1
    shadow_recovery: float = 0.0  # 0..1
    saturation: float = 0.0  # -1..1
    sharpen_amount: float = 0.0  # 0..1
    crop_box: tuple[int, int, int, int] | None = None  # x0,y0,x1,y1 in source pixels
    target_aspect_ratio: str | None = None
    rotation_degrees: float = 0.0

    def clamped(self) -> "Adjustments":
        """Artwork Integrity mode caps every adjustment to a mild range."""
        return Adjustments(
            exposure=max(-0.35, min(0.35, self.exposure)),
            contrast=max(-0.3, min(0.3, self.contrast)),
            white_balance_shift=max(-0.3, min(0.3, self.white_balance_shift)),
            highlight_recovery=max(0.0, min(1.0, self.highlight_recovery)),
            shadow_recovery=max(0.0, min(1.0, self.shadow_recovery)),
            saturation=max(-0.25, min(0.25, self.saturation)),
            sharpen_amount=max(0.0, min(0.6, self.sharpen_amount)),
            crop_box=self.crop_box,
            target_aspect_ratio=self.target_aspect_ratio,
            rotation_degrees=max(-5.0, min(5.0, self.rotation_degrees)),
        )

    def to_dict(self) -> dict:
        return {
            "exposure": round(self.exposure, 3),
            "contrast": round(self.contrast, 3),
            "white_balance_shift": round(self.white_balance_shift, 3),
            "highlight_recovery": round(self.highlight_recovery, 3),
            "shadow_recovery": round(self.shadow_recovery, 3),
            "saturation": round(self.saturation, 3),
            "sharpen_amount": round(self.sharpen_amount, 3),
            "crop_box": list(self.crop_box) if self.crop_box else None,
            "target_aspect_ratio": self.target_aspect_ratio,
            "rotation_degrees": round(self.rotation_degrees, 2),
        }


def _apply_exposure(img: np.ndarray, amount: float) -> np.ndarray:
    if amount == 0:
        return img
    factor = 1.0 + amount  # simple linear brightness scale
    return np.clip(img.astype(np.float32) * factor, 0, 255)


def _apply_contrast(img: np.ndarray, amount: float) -> np.ndarray:
    if amount == 0:
        return img
    factor = 1.0 + amount
    mean = img.mean()
    return np.clip((img.astype(np.float32) - mean) * factor + mean, 0, 255)


def _apply_white_balance(img: np.ndarray, amount: float) -> np.ndarray:
    """Positive = warmer (boost red, cut blue); negative = cooler."""
    if amount == 0:
        return img
    out = img.astype(np.float32)
    out[:, :, 0] = out[:, :, 0] * (1.0 - amount * 0.15)  # blue channel (BGR)
    out[:, :, 2] = out[:, :, 2] * (1.0 + amount * 0.15)  # red channel
    return np.clip(out, 0, 255)


def _apply_highlight_shadow_recovery(img: np.ndarray, highlight: float, shadow: float) -> np.ndarray:
    if highlight == 0 and shadow == 0:
        return img
    out = img.astype(np.float32) / 255.0
    if highlight > 0:
        # Pull down the brightest tones toward mid-gray, proportionally.
        mask = out > 0.7
        out = np.where(mask, out - (out - 0.7) * highlight * 0.6, out)
    if shadow > 0:
        # Lift the darkest tones.
        mask = out < 0.3
        out = np.where(mask, out + (0.3 - out) * shadow * 0.6, out)
    return np.clip(out * 255.0, 0, 255)


def _apply_saturation(img: np.ndarray, amount: float) -> np.ndarray:
    if amount == 0:
        return img
    hsv = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * (1.0 + amount), 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)


def _apply_sharpen(img: np.ndarray, amount: float) -> np.ndarray:
    if amount == 0:
        return img
    blurred = cv2.GaussianBlur(img, (0, 0), sigmaX=2)
    sharpened = cv2.addWeighted(img, 1 + amount, blurred, -amount, 0)
    return np.clip(sharpened, 0, 255)


def _apply_rotation(img: np.ndarray, degrees: float) -> np.ndarray:
    """Small-angle straightening (perspective/level correction), not a full warp."""
    if degrees == 0:
        return img
    h, w = img.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), degrees, 1.0)
    return cv2.warpAffine(img, matrix, (w, h), borderMode=cv2.BORDER_REFLECT)


def apply_adjustments(
    source_path: str,
    adjustments: Adjustments,
    artwork_integrity_mode: bool = True,
) -> Image.Image:
    """
    Apply the given adjustments to the image at source_path and return a
    Pillow Image. When artwork_integrity_mode is True (the default and, in
    this MVP, the only supported mode) adjustments are clamped to mild,
    non-destructive ranges before being applied.
    """
    if artwork_integrity_mode:
        adjustments = adjustments.clamped()

    with Image.open(source_path) as im:
        im = im.convert("RGB")
        rgb = np.array(im)

    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR).astype(np.float32)

    bgr = _apply_rotation(bgr, adjustments.rotation_degrees)
    bgr = _apply_white_balance(bgr, adjustments.white_balance_shift)
    bgr = _apply_exposure(bgr, adjustments.exposure)
    bgr = _apply_highlight_shadow_recovery(bgr, adjustments.highlight_recovery, adjustments.shadow_recovery)
    bgr = _apply_contrast(bgr, adjustments.contrast)
    bgr = _apply_saturation(bgr, adjustments.saturation)
    bgr = _apply_sharpen(bgr, adjustments.sharpen_amount)

    bgr = np.clip(bgr, 0, 255).astype(np.uint8)
    rgb_out = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    out_image = Image.fromarray(rgb_out)

    if adjustments.crop_box:
        out_image = out_image.crop(adjustments.crop_box)

    return out_image
