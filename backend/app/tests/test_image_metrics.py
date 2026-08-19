import numpy as np
from PIL import Image

from app.services.image_analysis.metrics import analyze_image


def _make_test_image(path, width=800, height=600, fill=(128, 128, 128), noise=False):
    arr = np.full((height, width, 3), fill, dtype=np.uint8)
    if noise:
        rng = np.random.default_rng(42)
        noise_arr = rng.integers(0, 40, size=arr.shape, dtype=np.uint8)
        arr = np.clip(arr.astype(int) + noise_arr, 0, 255).astype(np.uint8)
    Image.fromarray(arr).save(path)


def test_analyze_image_returns_correct_dimensions(tmp_path):
    path = tmp_path / "flat.jpg"
    _make_test_image(str(path), width=1000, height=500)

    metrics = analyze_image(str(path))

    assert metrics.width == 1000
    assert metrics.height == 500
    assert metrics.aspect_ratio == 2.0


def test_dark_image_has_low_brightness(tmp_path):
    path = tmp_path / "dark.jpg"
    _make_test_image(str(path), fill=(10, 10, 10), noise=True)

    metrics = analyze_image(str(path))

    assert metrics.brightness < 40


def test_bright_image_has_high_brightness(tmp_path):
    path = tmp_path / "bright.jpg"
    _make_test_image(str(path), fill=(245, 245, 245), noise=True)

    metrics = analyze_image(str(path))

    assert metrics.brightness > 200


def test_pure_white_image_has_highlight_clipping(tmp_path):
    path = tmp_path / "white.jpg"
    _make_test_image(str(path), fill=(255, 255, 255))

    metrics = analyze_image(str(path))

    assert metrics.highlight_clipping_pct > 90


def test_pure_black_image_has_shadow_clipping(tmp_path):
    path = tmp_path / "black.jpg"
    _make_test_image(str(path), fill=(0, 0, 0))

    metrics = analyze_image(str(path))

    assert metrics.shadow_clipping_pct > 90


def test_flat_color_image_has_low_contrast(tmp_path):
    path = tmp_path / "flat_gray.jpg"
    _make_test_image(str(path), fill=(120, 120, 120))

    metrics = analyze_image(str(path))

    assert metrics.contrast < 5


def test_dominant_colors_returned(tmp_path):
    path = tmp_path / "colors.jpg"
    _make_test_image(str(path), fill=(200, 50, 50), noise=True)

    metrics = analyze_image(str(path))

    assert len(metrics.dominant_colors) > 0
    for color in metrics.dominant_colors:
        assert color["hex"].startswith("#")
        assert 0 <= color["ratio"] <= 1


def test_no_faces_in_flat_image(tmp_path):
    path = tmp_path / "no_face.jpg"
    _make_test_image(str(path), fill=(100, 100, 100), noise=True)

    metrics = analyze_image(str(path))

    assert metrics.faces == []
