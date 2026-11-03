import asyncio
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from app.core.config import settings
from app.core.security import validate_image_file
from app.services.file_manager import FileManager
from app.services.image_compressor import ImageCompressor

router = APIRouter(prefix="/api", tags=["Image Compressor"])

@router.post("/compress")
async def compress_images(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    preset: str = Form("balanced"),
    quality: Optional[int] = Form(None),
    target_format: Optional[str] = Form(None),
    resize_mode: Optional[str] = Form(None),
    resize_percentage: Optional[int] = Form(None),
    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None),
    preserve_aspect_ratio: bool = Form(True),
):
    if not files:
        raise HTTPException(status_code=400, detail="No image files uploaded")
        
    if len(files) > settings.MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.MAX_BATCH_FILES} files can be processed in a single batch",
        )
        
    preset_clean = preset.lower()
    if preset_clean not in ("maximum", "balanced", "high_quality", "custom"):
        preset_clean = "balanced"
        
    target_fmt = target_format.upper() if target_format else None
    if target_fmt == "JPG":
        target_fmt = "JPEG"
    if target_fmt and target_fmt not in settings.SUPPORTED_COMPRESS_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Target format '{target_format}' is not supported for compression. Supported: {settings.SUPPORTED_COMPRESS_FORMATS}",
        )

    results = []
    
    for upload_file in files:
        temp_path = None
        original_name = upload_file.filename or "image.png"
        try:
            temp_path, orig_name = await FileManager.save_upload(upload_file)
            meta = validate_image_file(temp_path)
            
            res = await asyncio.to_thread(
                ImageCompressor.compress_image,
                source_path=temp_path,
                preset=preset_clean,
                quality=quality,
                target_format=target_fmt,
                resize_mode=resize_mode,
                resize_percentage=resize_percentage,
                width=width,
                height=height,
                preserve_aspect_ratio=preserve_aspect_ratio,
            )
            
            results.append({
                "status": "success",
                "original_filename": original_name,
                "compressed_filename": res["filename"],
                "download_url": f"/api/download/{res['filename']}",
                "preview_url": f"/api/preview/{res['filename']}",
                "format": res["format"],
                "original_size_bytes": res["original_size_bytes"],
                "compressed_size_bytes": res["compressed_size_bytes"],
                "savings_bytes": res["savings_bytes"],
                "savings_percent": res["savings_percent"],
                "original_width": res["original_width"],
                "original_height": res["original_height"],
                "width": res["width"],
                "height": res["height"],
                "quality_used": res["quality_used"],
                "preset_used": res["preset_used"],
            })
        except Exception as e:
            results.append({
                "status": "error",
                "original_filename": original_name,
                "error": str(e),
            })
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)

    background_tasks.add_task(FileManager.cleanup_old_files)

    return {
        "total": len(files),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    }
