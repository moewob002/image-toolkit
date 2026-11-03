import asyncio
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from PIL import ImageColor
from app.core.config import settings
from app.core.security import validate_image_file
from app.services.file_manager import FileManager
from app.services.image_converter import ImageConverter

router = APIRouter(prefix="/api", tags=["Image Converter"])

@router.post("/convert")
async def convert_images(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    target_format: str = Form(...),
    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None),
    preserve_aspect_ratio: bool = Form(True),
    quality: int = Form(90),
    background_color: str = Form("#FFFFFF"),
):
    if not files:
        raise HTTPException(status_code=400, detail="No image files uploaded")
        
    if len(files) > settings.MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.MAX_BATCH_FILES} files can be processed in a single batch",
        )
        
    target_fmt = target_format.upper()
    if target_fmt == "JPG":
        target_fmt = "JPEG"
    if target_fmt not in settings.SUPPORTED_CONVERT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Target format '{target_format}' is not supported. Supported: {settings.SUPPORTED_CONVERT_FORMATS}",
        )

    # Parse background matte color
    try:
        matte_rgb = ImageColor.getrgb(background_color)
        if len(matte_rgb) == 4:
            matte_rgb = matte_rgb[:3]
    except Exception:
        matte_rgb = (255, 255, 255)

    results = []
    
    for upload_file in files:
        temp_path = None
        original_name = upload_file.filename or "image.png"
        try:
            temp_path, orig_name = await FileManager.save_upload(upload_file)
            # Deep validation of image integrity and format
            meta = validate_image_file(temp_path)
            
            # Offload synchronous CPU-bound conversion to thread
            res = await asyncio.to_thread(
                ImageConverter.convert_image,
                source_path=temp_path,
                target_format=target_fmt,
                width=width,
                height=height,
                preserve_aspect_ratio=preserve_aspect_ratio,
                quality=quality,
                background_matte=matte_rgb,
            )
            
            results.append({
                "status": "success",
                "original_filename": original_name,
                "converted_filename": res["filename"],
                "download_url": f"/api/download/{res['filename']}",
                "preview_url": f"/api/preview/{res['filename']}",
                "original_format": res["original_format"],
                "target_format": res["format"],
                "original_width": res["original_width"],
                "original_height": res["original_height"],
                "width": res["width"],
                "height": res["height"],
                "original_size_bytes": meta["size_bytes"],
                "size_bytes": res["size_bytes"],
            })
        except Exception as e:
            results.append({
                "status": "error",
                "original_filename": original_name,
                "error": str(e),
            })
        finally:
            # Clean up uploaded file once converted
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)

    # Schedule retention cleanup
    background_tasks.add_task(FileManager.cleanup_old_files)

    return {
        "total": len(files),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    }
