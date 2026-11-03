import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    settings.init_directories()

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def sample_rgb_image_bytes():
    img = Image.new("RGB", (120, 80), color=(255, 50, 50))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

@pytest.fixture
def sample_rgba_image_bytes():
    img = Image.new("RGBA", (100, 100), color=(0, 128, 255, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

@pytest.fixture
def sample_jpeg_image_bytes():
    img = Image.new("RGB", (150, 100), color=(30, 200, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()
