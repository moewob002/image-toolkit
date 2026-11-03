import os
import shutil
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.core.config import settings
from app.core.security import ensure_safe_path, sanitize_filename
from app.services.file_manager import FileManager

router = APIRouter(tags=["System & Downloads"])

class ZipRequest(BaseModel):
    filenames: List[str]
    zip_name: str = "processed_images.zip"

@router.get("/api/health")
def health_check():
    # Check disk and model directory
    disk = shutil.disk_usage(settings.OUTPUT_DIR)
    models_exist = list(settings.MODELS_DIR.glob("*.onnx"))
    
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "supported_convert_formats": settings.SUPPORTED_CONVERT_FORMATS,
        "supported_compress_formats": settings.SUPPORTED_COMPRESS_FORMATS,
        "disk_free_mb": round(disk.free / (1024 * 1024), 2),
        "models_cached": [m.name for m in models_exist],
        "models_ready": True,
    }

@router.get("/api/download/{filename}")
def download_file(filename: str):
    clean_name = sanitize_filename(filename)
    file_path = settings.OUTPUT_DIR / clean_name
    try:
        file_path = ensure_safe_path(file_path, settings.OUTPUT_DIR)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access forbidden")
        
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found or expired")
        
    return FileResponse(
        path=file_path,
        filename=clean_name,
        media_type="application/octet-stream",
    )

@router.get("/api/preview/{filename}")
def preview_file(filename: str):
    clean_name = sanitize_filename(filename)
    # Check output dir, then upload dir
    file_path = settings.OUTPUT_DIR / clean_name
    if not file_path.exists():
        file_path = settings.UPLOAD_DIR / clean_name
        
    try:
        if file_path.exists():
            file_path = ensure_safe_path(file_path, file_path.parent)
        else:
            raise HTTPException(status_code=404, detail="Preview file not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access forbidden")
        
    ext = file_path.suffix.lstrip(".").lower()
    media_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "avif": "image/avif",
        "gif": "image/gif",
        "bmp": "image/bmp",
        "tiff": "image/tiff",
        "ico": "image/x-icon",
    }
    media_type = media_types.get(ext, "application/octet-stream")
    return FileResponse(path=file_path, media_type=media_type)

@router.post("/api/download-zip")
def download_zip(request: ZipRequest, background_tasks: BackgroundTasks):
    if not request.filenames:
        raise HTTPException(status_code=400, detail="No filenames provided")
        
    items = []
    for fname in request.filenames:
        clean_name = sanitize_filename(fname)
        path = settings.OUTPUT_DIR / clean_name
        if path.exists():
            try:
                safe_p = ensure_safe_path(path, settings.OUTPUT_DIR)
                items.append((safe_p, clean_name))
            except PermissionError:
                continue
                
    if not items:
        raise HTTPException(status_code=404, detail="None of the requested files were found")
        
    zip_path = FileManager.create_zip(items, request.zip_name)
    
    # Schedule cleanup of the zip archive after sending
    background_tasks.add_task(FileManager.cleanup_old_files)
    
    return FileResponse(
        path=zip_path,
        filename=zip_path.name,
        media_type="application/zip",
    )
