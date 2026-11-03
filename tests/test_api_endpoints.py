import io
from PIL import Image
import pytest

def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "supported_convert_formats" in data
    assert "models_ready" in data

def test_api_convert_endpoint(client, sample_rgb_image_bytes):
    files = [("files", ("test.png", sample_rgb_image_bytes, "image/png"))]
    data = {
        "target_format": "WEBP",
        "quality": 80,
    }
    res = client.post("/api/convert", files=files, data=data)
    assert res.status_code == 200
    payload = res.json()
    assert payload["total"] == 1
    assert payload["successful"] == 1
    item = payload["results"][0]
    assert item["target_format"] == "WEBP"
    assert item["download_url"].startswith("/api/download/")

def test_api_compress_endpoint(client, sample_jpeg_image_bytes):
    files = [("files", ("test.jpg", sample_jpeg_image_bytes, "image/jpeg"))]
    data = {
        "preset": "balanced",
    }
    res = client.post("/api/compress", files=files, data=data)
    assert res.status_code == 200
    payload = res.json()
    assert payload["total"] == 1
    assert payload["successful"] == 1
    item = payload["results"][0]
    assert "savings_percent" in item
    assert item["compressed_size_bytes"] > 0

def test_api_invalid_corrupted_upload(client):
    # Upload a bogus text file disguised as an image
    corrupted_data = b"THIS IS NOT A VALID IMAGE CONTENT JUST PLAIN TEXT!"
    files = [("files", ("malicious.jpg", corrupted_data, "image/jpeg"))]
    res = client.post("/api/convert", files=files, data={"target_format": "PNG"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["failed"] == 1
    assert payload["results"][0]["status"] == "error"

def test_api_path_traversal_protection(client):
    # Attempt path traversal on download route
    res = client.get("/api/download/../../../../etc/passwd")
    assert res.status_code in (400, 404)

def test_api_download_zip_endpoint(client, sample_rgb_image_bytes):
    # First convert an image
    files = [("files", ("item.png", sample_rgb_image_bytes, "image/png"))]
    res = client.post("/api/convert", files=files, data={"target_format": "PNG"})
    filename = res.json()["results"][0]["converted_filename"]

    # Request ZIP
    zip_req = {
        "filenames": [filename],
        "zip_name": "test_archive.zip",
    }
    res_zip = client.post("/api/download-zip", json=zip_req)
    assert res_zip.status_code == 200
    assert res_zip.headers["content-type"] == "application/zip"
    assert len(res_zip.content) > 0
