# Local Image Toolkit — Docker + Python

> **AI-Generated / AI-Assisted**: This project was created and developed with AI assistance, designed for high-performance, privacy-focused local image manipulation without external cloud dependencies.

A modern, production-grade, self-hosted web application for local image processing powered by **Python 3.12+**, **FastAPI**, **Pillow**, **pillow-heif**, and **rembg** with ONNX Runtime.

Everything runs 100% locally on your machine or private server. No external APIs, no paid cloud services, and zero telemetry.

---

## 🌟 Features

### 1. Image Converter
- **Multi-Format Support**: JPEG / JPG, PNG, WebP, AVIF, GIF, BMP, TIFF, and ICO.
- **Batch Conversion**: Upload multiple files simultaneously and convert them in a single batch.
- **Quality & Transparency Handling**: Intelligently preserves alpha transparency for supported formats (PNG, WebP, AVIF, GIF, ICO) and provides customizable background color matting when converting transparent assets to non-alpha formats like JPEG or BMP.
- **Custom Resizing**: Resize by custom width and height with optional aspect-ratio preservation.
- **ZIP Archive Export**: Download processed images individually or bundled into a clean ZIP archive.

### 2. Image Compressor
- **Smart Optimization**: Compresses JPEG, PNG, WebP, and AVIF images with minimal perceptible loss.
- **Flexible Quality & Presets**:
  - `Maximum Compression` (Quality: 40, WebP effort: 6)
  - `Balanced` (Quality: 75, WebP effort: 4) — *Default*
  - `High Quality` (Quality: 90, WebP effort: 2)
  - `Custom` (Adjustable slider: 10–100)
- **Downscaling Options**: Percentage-based downscaling (e.g. 50%, 75%) or explicit dimension limits.
- **Real-Time Savings Statistics**: Displays original file size, compressed file size, bytes saved, and compression percentage.

### 3. AI Background Remover
- **Offline AI Model**: Powered by `rembg` running ONNX `u2net` models locally on CPU.
- **Thread-Safe Model Caching**: Loads the neural network session once into memory and reuses it across requests to ensure low latency and high concurrency.
- **Flexible Background Replacement**:
  - Transparent output (PNG)
  - Solid hex color fill (e.g. clean studio white `#FFFFFF`, blue `#0055FF`, etc.)
  - Custom uploaded background image
- **Batch Processing**: Strip backgrounds from multiple images at once.

### 4. Modern Web Interface
- Sleek dark-mode dashboard designed for desktop, tablet, and mobile browsers.
- Interactive drag-and-drop zone with instant file validation.
- Progress bar, status badges, thumbnail previews, and modal inspect view.
- Queue manager allowing users to remove items prior to processing.

---
## 🛠️ Architecture & Security

- **Decompression Bomb Protection**: Pillow's `MAX_IMAGE_PIXELS` capped at 100,000,000 pixels (100 MP) to eliminate denial-of-service image memory exploits.
- **Magic Byte Signature Inspection**: All uploads are verified against binary file magic numbers in addition to filename extensions.
- **Strict Path Traversal Guards**: Filenames are cryptographically randomized with UUIDv4, and all disk writes/reads are strictly jailed within `/app/uploads`, `/app/output`, and `/app/temp`.
- **Unprivileged Container**: Runs under non-root user `appuser` (UID: 1000) inside Docker.
- **Localhost Default**: Defaults to binding on `127.0.0.1:8000` to prevent unintended public exposure.

---

## 🚀 Quick Start with Docker

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) (v20.10+)
- [Docker Compose](https://docs.docker.com/compose/) (v2.0+)

### 1. Clone & Configure
```bash
git clone <repo-url> image-toolkit
cd image-toolkit
cp .env.example .env
```

### 2. Start the Application
```bash
docker compose up -d --build
```

### 3. Access the Dashboard
Open your browser and navigate to:
**`http://localhost:8000`**

To stop the application:
```bash
docker compose down
```

---

## 🧠 Background Removal Model Setup & Offline Operation

The AI background remover uses the `u2net` model (~170 MB). 

### Automatic Download
On the very first background removal request, `rembg` will download `u2net.onnx` from GitHub releases to the persistent volume mounted at `/app/models`. Subsequent runs use this cached model completely offline without internet connectivity.

### Manual / Air-Gapped Offline Pre-Seeding
If deploying in a strictly offline or air-gapped environment:
1. Download `u2net.onnx` from [rembg releases](https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx).
2. Place the file inside your local `./models/` directory:
   ```bash
   mkdir -p models
   curl -L -o models/u2net.onnx https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx
   ```
3. When Docker Compose starts, the local `./models` volume is automatically mounted to `/app/models` and used by `rembg` immediately.

---

## ⚙️ Configuration (.env)

Customize runtime settings via environment variables:

| Variable | Default | Description |
|---|---|---|
| `HOST` | `127.0.0.1` | Bind host address (`0.0.0.0` for LAN/WAN access) |
| `PORT` | `8000` | HTTP port |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum upload size per file in MB |
| `MAX_BATCH_FILES` | `50` | Maximum files allowed per batch operation |
| `MAX_IMAGE_PIXELS` | `100000000` | Pillow decompression bomb safety ceiling (100 MP) |
| `TEMP_FILE_LIFETIME_HOURS` | `2` | Stale file cleanup threshold |
| `U2NET_HOME` | `/app/models` | Directory path where AI ONNX models are stored |

---

## 💻 Local Development Setup (Without Docker)

### Requirements
- Python 3.12+ (or UV / venv)
- `libheif` / `libde265` for AVIF encoding

### Steps
```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run development server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Running Automated Tests
```bash
pytest tests/ -v
```

---

## 📡 API Reference

Interactive OpenAPI documentation is available locally at `http://localhost:8000/docs`.

- `GET /api/health`: Health status and supported format codecs.
- `POST /api/convert`: Batch image format converter (`multipart/form-data`).
- `POST /api/compress`: Batch image optimizer with presets and custom sliders.
- `POST /api/remove-bg`: AI background removal with transparency or custom background fills.
- `GET /api/download/{filename}`: Safe download handler for processed output images.
- `POST /api/download-zip`: Generates an on-the-fly zip archive of multiple output files.

---

## 🛡️ Production & Security Considerations
- **Reverse Proxy**: If exposing to the public internet, deploy behind Nginx or Caddy with TLS/HTTPS and configure rate limiting.
- **Resource Allocation**: The included `docker-compose.yml` specifies memory limits (`2GB` limit, `512MB` reservation) and CPU quotas (`2.0` CPUs) suitable for home servers and VPS instances.
- **Data Privacy**: Processed images and uploads are purged periodically during application startup and task execution.
