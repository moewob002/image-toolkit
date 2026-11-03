from pathlib import Path
from PIL import Image
import pytest
from app.services.image_compressor import ImageCompressor

def test_compress_jpeg_presets(tmp_path):
    src = tmp_path / "photo.jpg"
    # Create detailed test image with varying pixels
    img = Image.new("RGB", (300, 300))
    pixels = img.load()
    for i in range(300):
        for j in range(300):
            pixels[i, j] = (i % 256, j % 256, (i + j) % 256)
    img.save(src, format="JPEG", quality=100)

    # Maximum compression
    res_max = ImageCompressor.compress_image(src, preset="maximum")
    assert res_max["preset"] == "maximum"
    assert res_max["compressed_size_bytes"] > 0
    assert Path(res_max["output_path"]).exists()

    # Balanced compression
    res_bal = ImageCompressor.compress_image(src, preset="balanced")
    assert res_bal["preset"] == "balanced"
    assert res_bal["format"] == "JPEG"
    assert res_bal["filename"].endswith(".jpeg")

def test_compress_jpeg_keep_original_format_no_target(tmp_path):
    src = tmp_path / "photo_keep.jpg"
    img = Image.new("RGB", (150, 150), color="red")
    img.save(src, format="JPEG")

    # target_format=None implies keep original format
    res = ImageCompressor.compress_image(src, target_format=None)
    assert res["format"] == "JPEG"
    assert res["filename"].endswith(".jpeg")

def test_compress_with_percentage_resize(tmp_path):
    src = tmp_path / "orig.png"
    img = Image.new("RGB", (200, 200), color="cyan")
    img.save(src, format="PNG")

    res = ImageCompressor.compress_image(
        src,
        preset="custom",
        quality=80,
        resize_mode="percentage",
        resize_percentage=50,
    )
    assert res["width"] == 100
    assert res["height"] == 100

def test_compress_transparency_preservation(tmp_path):
    src = tmp_path / "transparent.png"
    img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 100))
    img.save(src, format="PNG")

    # Compress to WebP
    res = ImageCompressor.compress_image(src, target_format="WEBP")
    out_img = Image.open(res["output_path"])
    assert out_img.mode in ("RGBA", "LA", "P")
