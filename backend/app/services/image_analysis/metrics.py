"""
Measurable visual property extraction for uploaded images.

Everything here is a deterministic, explainable calculation (histograms,
Laplacian variance, simple color-space math) -- there is no ML model and
nothing here predicts engagement. See services/recommendations for how
these numbers turn into rule-based advice.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image


@dataclass
class FaceInfo:
    box: tuple[int, int, int, int]  # x, y, w, h in pixels
    area_ratio: float  # face area / total image area


@dataclass
class ImageMetrics:
    width: int
    height: int
    aspect_ratio: float
    brightness: float  # 0-255 mean luminance
    contrast: float  # 0-255 stddev of luminance
    saturation: float  # 0-255 mean saturation (HSV)
    color_temperature: float  # approximate kelvin, 1000-40000 range
    sharpness: float  # Laplacian variance, unbounded (higher = sharper)
    highlight_clipping_pct: float  # % of pixels with luminance >= 250
    shadow_clipping_pct: float  # % of pixels with luminance <= 5
    dominant_colors: list[dict] = field(default_factory=list)  # [{hex, ratio}]
    faces: list[FaceInfo] = field(default_factory=list)
    subject_offset_x: float | None = None  # -1..1, 0 = centered
    subject_offset_y: float | None = None
    negative_space_ratio: float | None = None  # 0-1, fraction of "empty" area
    raw: dict = field(default_factory=dict)


_FACE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"


def _load_face_cascade() -> cv2.CascadeClassifier:
    return cv2.CascadeClassifier(_FACE_CASCADE_PATH)


_face_cascade = None


def _get_face_cascade() -> cv2.CascadeClassifier:
    global _face_cascade
    if _face_cascade is None:
        _face_cascade = _load_face_cascade()
    return _face_cascade


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*[max(0, min(255, int(c))) for c in rgb])


def _dominant_colors(rgb_small: np.ndarray, k: int = 5) -> list[dict]:
    pixels = rgb_small.reshape(-1, 3).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 15, 1.0)
    k = min(k, max(1, len(pixels)))
    _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=k)
    order = np.argsort(-counts)
    total = counts.sum()
    results = []
    for idx in order:
        ratio = float(counts[idx]) / float(total)
        results.append({"hex": _rgb_to_hex(tuple(centers[idx])), "ratio": round(ratio, 4)})
    return results


def _approximate_color_temperature(rgb_mean: tuple[float, float, float]) -> float:
    """
    Very rough RGB -> color temperature approximation (McCamy-ish), good
    enough to flag "this image reads warm/cool" -- not a colorimetric
    instrument. Returns an approximate Kelvin value.
    """
    r, g, b = rgb_mean
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    # Normalize to chromaticity-like ratio and map to a kelvin range using
    # a simple empirical curve (warm/red-heavy -> lower K, cool/blue-heavy -> higher K).
    if r + b == 0:
        return 6500.0
    ratio = b / (r + 1e-6)
    # ratio ~0.5 (warm) -> ~3000K, ratio ~1 (neutral) -> ~6500K, ratio ~1.8 (cool) -> ~12000K
    kelvin = 3000 + (ratio - 0.5) * 6000
    return float(max(1500.0, min(15000.0, kelvin)))


def _subject_placement(gray: np.ndarray) -> tuple[float, float, float]:
    """
    Approximate the visual "center of mass" of the image using a saliency
    proxy (gradient magnitude, i.e. edge energy) rather than raw pixel
    intensity, since interesting subjects usually have more local
    contrast/detail than background. Returns (offset_x, offset_y,
    negative_space_ratio) where offsets are -1..1 relative to center and
    negative_space_ratio is the fraction of the frame with low edge
    energy (a rough "empty space" estimate).
    """
    h, w = gray.shape
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    energy = cv2.magnitude(gx, gy)

    total_energy = energy.sum()
    if total_energy <= 1e-6:
        return 0.0, 0.0, 1.0

    ys, xs = np.indices(energy.shape)
    cx = float((xs * energy).sum() / total_energy)
    cy = float((ys * energy).sum() / total_energy)

    offset_x = (cx - w / 2) / (w / 2)
    offset_y = (cy - h / 2) / (h / 2)

    threshold = np.percentile(energy, 60)
    negative_space_ratio = float((energy < threshold).sum()) / float(energy.size)

    return round(offset_x, 3), round(offset_y, 3), round(negative_space_ratio, 3)


def _detect_faces(bgr: np.ndarray) -> list[FaceInfo]:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    cascade = _get_face_cascade()
    if cascade.empty():
        return []
    boxes = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
    h, w = gray.shape
    total_area = float(h * w)
    faces = []
    for (x, y, fw, fh) in boxes:
        faces.append(FaceInfo(box=(int(x), int(y), int(fw), int(fh)), area_ratio=round((fw * fh) / total_area, 4)))
    return faces


def analyze_image(path: str, max_dimension_for_analysis: int = 1600) -> ImageMetrics:
    """
    Load an image from disk and compute all measurable visual properties.
    Analysis is performed on a downscaled copy (max_dimension_for_analysis)
    for speed; reported width/height reflect the original file.
    """
    with Image.open(path) as im:
        im = im.convert("RGB")
        width, height = im.size
        scale = min(1.0, max_dimension_for_analysis / max(width, height))
        if scale < 1.0:
            small = im.resize((max(1, int(width * scale)), max(1, int(height * scale))))
        else:
            small = im
        rgb_array = np.array(small)

    bgr = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))
    saturation = float(np.mean(hsv[:, :, 1]))

    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = float(laplacian.var())

    total_pixels = gray.size
    highlight_clipping_pct = round(float(np.sum(gray >= 250)) / total_pixels * 100, 2)
    shadow_clipping_pct = round(float(np.sum(gray <= 5)) / total_pixels * 100, 2)

    rgb_mean = tuple(float(c) for c in np.mean(rgb_array.reshape(-1, 3), axis=0))
    color_temperature = _approximate_color_temperature(rgb_mean)

    dominant = _dominant_colors(rgb_array, k=5)

    faces = _detect_faces(bgr)

    offset_x, offset_y, negative_space_ratio = _subject_placement(gray)

    return ImageMetrics(
        width=width,
        height=height,
        aspect_ratio=round(width / height, 4),
        brightness=round(brightness, 2),
        contrast=round(contrast, 2),
        saturation=round(saturation, 2),
        color_temperature=round(color_temperature, 1),
        sharpness=round(sharpness, 2),
        highlight_clipping_pct=highlight_clipping_pct,
        shadow_clipping_pct=shadow_clipping_pct,
        dominant_colors=dominant,
        faces=faces,
        subject_offset_x=offset_x,
        subject_offset_y=offset_y,
        negative_space_ratio=negative_space_ratio,
        raw={
            "rgb_mean": rgb_mean,
            "analysis_dimensions": list(rgb_array.shape[:2][::-1]),
        },
    )
