import os
import time
import zipfile
import shutil
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from fastapi import UploadFile
from app.core.config import settings
from app.core.security import generate_safe_filename, sanitize_filename, ensure_safe_path

CHUNK_SIZE = 1024 * 1024  # 1 MB

class FileManager:
    @staticmethod
    async def save_upload(upload_file: UploadFile, target_dir: Optional[Path] = None) -> Tuple[Path, str]:
        if target_dir is None:
            target_dir = settings.UPLOAD_DIR
        
        original_name = upload_file.filename or "unnamed.png"
        sanitized_orig = sanitize_filename(original_name)
        ext = Path(sanitized_orig).suffix
        if not ext:
            ext = ".png"
            
        safe_name = generate_safe_filename(ext)
        dest_path = target_dir / safe_name
        
        bytes_read = 0
        with open(dest_path, "wb") as f:
            while True:
                chunk = await upload_file.read(CHUNK_SIZE)
                if not chunk:
                    break
                bytes_read += len(chunk)
                if bytes_read > settings.MAX_UPLOAD_SIZE_BYTES:
                    # Delete partially written file
                    f.close()
                    dest_path.unlink(missing_ok=True)
                    raise ValueError(
                        f"File exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_MB} MB"
                    )
                f.write(chunk)
                
        return dest_path, sanitized_orig

    @staticmethod
    def create_zip(items: List[Tuple[Path, str]], zip_name: Optional[str] = None) -> Path:
        if not zip_name:
            zip_name = generate_safe_filename("zip")
        elif not zip_name.endswith(".zip"):
            zip_name = f"{sanitize_filename(zip_name)}.zip"
            
        zip_path = settings.OUTPUT_DIR / zip_name
        zip_path = ensure_safe_path(zip_path, settings.OUTPUT_DIR)
        
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            used_names = set()
            for file_path, display_name in items:
                if not file_path.exists():
                    continue
                clean_name = sanitize_filename(display_name)
                # Avoid collisions in zip archive
                final_name = clean_name
                counter = 1
                base, ext = os.path.splitext(clean_name)
                while final_name in used_names:
                    final_name = f"{base}_{counter}{ext}"
                    counter += 1
                used_names.add(final_name)
                zipf.write(file_path, arcname=final_name)
                
        return zip_path

    @staticmethod
    def cleanup_old_files(max_age_hours: Optional[int] = None) -> int:
        if max_age_hours is None:
            max_age_hours = settings.FILE_RETENTION_HOURS
            
        cutoff = time.time() - (max_age_hours * 3600)
        deleted_count = 0
        
        for folder in [settings.UPLOAD_DIR, settings.OUTPUT_DIR, settings.TEMP_DIR]:
            if not folder.exists():
                continue
            for item in folder.iterdir():
                try:
                    if item.is_file() and item.stat().st_mtime < cutoff:
                        item.unlink(missing_ok=True)
                        deleted_count += 1
                    elif item.is_dir() and item.stat().st_mtime < cutoff:
                        shutil.rmtree(item, ignore_errors=True)
                        deleted_count += 1
                except Exception:
                    pass
        return deleted_count

    @staticmethod
    def get_file_info(file_path: Path) -> Dict[str, Any]:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path.name}")
        stat = file_path.stat()
        return {
            "filename": file_path.name,
            "size_bytes": stat.st_size,
            "created_at": stat.st_ctime,
            "modified_at": stat.st_mtime,
        }
