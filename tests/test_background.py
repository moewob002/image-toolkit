import io
from pathlib import Path
from PIL import Image
from unittest.mock import patch, MagicMock
import pytest
from app.services.background_removal import BackgroundRemover

def test_remove_background_with_mocked_rembg(tmp_path):
    src = tmp_path / "portrait.png"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(src, format="PNG")

    # Create a mock transparent return
    mock_cutout = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
    
    with patch("rembg.remove", return_value=mock_cutout):
        res = BackgroundRemover.remove_background(src, bg_type="transparent")
        assert res["bg_type"] == "transparent"
        assert Path(res["output_path"]).exists()
        out_img = Image.open(res["output_path"])
        assert out_img.mode == "RGBA"

def test_remove_background_solid_color(tmp_path):
    src = tmp_path / "portrait2.png"
    img = Image.new("RGB", (80, 80), color="yellow")
    img.save(src, format="PNG")

    mock_cutout = Image.new("RGBA", (80, 80), color=(255, 255, 0, 200))
    
    with patch("rembg.remove", return_value=mock_cutout):
        res = BackgroundRemover.remove_background(src, bg_type="color", bg_color="#0000FF")
        assert res["bg_type"] == "color"
        assert Path(res["output_path"]).exists()
