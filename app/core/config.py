import os
from pathlib import Path
from typing import List, Set

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Local Image Toolkit")
    APP_VERSION: str = "1.0.0"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # Storage directories
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
    OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "output")))
    TEMP_DIR: Path = Path(os.getenv("TEMP_DIR", str(BASE_DIR / "temp")))
    MODELS_DIR: Path = Path(os.getenv("U2NET_HOME", os.getenv("MODELS_DIR", str(BASE_DIR / "models"))))

    # Size limits & security constraints
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    MAX_UPLOAD_SIZE_BYTES: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    # 100 megapixels ceiling to prevent decompression bomb attacks
    MAX_IMAGE_PIXELS: int = int(os.getenv("MAX_IMAGE_PIXELS", "100000000"))
    MAX_BATCH_FILES: int = int(os.getenv("MAX_BATCH_FILES", "30"))
    FILE_RETENTION_HOURS: int = int(os.getenv("FILE_RETENTION_HOURS", "2"))

    # Background Removal model
    BG_MODEL_NAME: str = os.getenv("BG_MODEL_NAME", "u2net")

    # Allowed formats
    SUPPORTED_INPUT_FORMATS: Set[str] = {
        "JPEG", "JPG", "PNG", "WEBP", "AVIF", "GIF", "BMP", "TIFF", "TIF", "ICO"
    }
    SUPPORTED_CONVERT_FORMATS: List[str] = [
        "JPEG", "PNG", "WEBP", "AVIF", "GIF", "BMP", "TIFF", "ICO"
    ]
    SUPPORTED_COMPRESS_FORMATS: List[str] = [
        "JPEG", "PNG", "WEBP", "AVIF"
    ]

    def init_directories(self) -> None:
        for directory in [self.UPLOAD_DIR, self.OUTPUT_DIR, self.TEMP_DIR, self.MODELS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.init_directories()

# Export U2NET_HOME so rembg uses our local models directory
os.environ["U2NET_HOME"] = str(settings.MODELS_DIR)
