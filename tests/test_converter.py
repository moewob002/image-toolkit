import io
from pathlib import Path
from PIL import Image
import pytest
from app.services.image_converter import ImageConverter

def test_convert_rgb_png_to_jpeg(tmp_path):
    src = tmp_path / "test.png"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(src, format="PNG")

    res = ImageConverter.convert_image(src, "JPEG", quality=85)
    assert res["target_format"] == "JPEG"
    assert res["width"] == 100
    assert res["height"] == 100
    assert Path(res["output_path"]).exists()

def test_convert_rgba_to_jpeg_matte(tmp_path):
    src = tmp_path / "transparent.png"
    img = Image.new("RGBA", (80, 80), color=(0, 0, 255, 128))
    img.save(src, format="PNG")

    res = ImageConverter.convert_image(src, "JPEG", background_matte=(0, 255, 0))
    out_img = Image.open(res["output_path"])
    assert out_img.mode == "RGB"

def test_convert_with_resize_and_aspect_ratio(tmp_path):
    src = tmp_path / "orig.jpg"
    img = Image.new("RGB", (200, 100), color="blue")
    img.save(src, format="JPEG")

    # Width specified, height auto
    res = ImageConverter.convert_image(src, "WEBP", width=100, preserve_aspect_ratio=True)
    assert res["width"] == 100
    assert res["height"] == 50

def test_convert_to_avif(tmp_path):
    src = tmp_path / "orig.png"
    img = Image.new("RGB", (50, 50), color="green")
    img.save(src, format="PNG")

    res = ImageConverter.convert_image(src, "AVIF", quality=75)
    assert res["target_format"] == "AVIF"
    assert Path(res["output_path"]).exists()

def test_convert_to_ico(tmp_path):
    src = tmp_path / "orig.png"
    img = Image.new("RGBA", (256, 256), color=(255, 255, 0, 255))
    img.save(src, format="PNG")

    res = ImageConverter.convert_image(src, "ICO")
    assert res["target_format"] == "ICO"
    assert Path(res["output_path"]).exists()
