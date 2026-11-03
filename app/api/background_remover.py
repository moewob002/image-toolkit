import asyncio
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from app.core.config import settings
from app.core.security import validate_image_file
from app.services.file_manager import FileManager
from app.services.background_removal import BackgroundRemover

router = APIRouter(prefix="/api", tags=["AI Background Remover"])

@router.post("/remove-bg")
async def remove_background(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    bg_type: str = Form("transparent"),
    bg_color: Optional[str] = Form("#FFFFFF"),
    bg_image: Optional[UploadFile] = File(None),
    model_name: Optional[str] = Form(None),
):
    if not files:
        raise HTTPException(status_code=400, detail="No image files uploaded")
        
    if len(files) > settings.MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.MAX_BATCH_FILES} files can be processed in a single batch",
        )
        
    bg_clean = bg_type.lower()
    if bg_clean not in ("transparent", "color", "image"):
        bg_clean = "transparent"
        
    # If custom background image uploaded
    bg_image_temp = None
    if bg_clean == "image" and bg_image and bg_image.filename:
        bg_image_temp, _ = await FileManager.save_upload(bg_image)
        try:
            validate_image_file(bg_image_temp)
        except Exception as e:
            bg_image_temp.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"Invalid background replacement image: {str(e)}")

    results = []
    
    for upload_file in files:
        temp_path = None
        original_name = upload_file.filename or "image.png"
        try:
            temp_path, orig_name = await FileManager.save_upload(upload_file)
            meta = validate_image_file(temp_path)
            
            res = await asyncio.to_thread(
                BackgroundRemover.remove_background,
                source_path=temp_path,
                bg_type=bg_clean,
                bg_color=bg_color,
                bg_image_path=bg_image_temp,
                model_name=model_name,
            )
            
            results.append({
                "status": "success",
                "original_filename": original_name,
                "processed_filename": res["filename"],
                "download_url": f"/api/download/{res['filename']}",
                "preview_url": f"/api/preview/{res['filename']}",
                "format": res["format"],
                "original_size_bytes": res["original_size_bytes"],
                "size_bytes": res["size_bytes"],
                "original_width": res["original_width"],
                "original_height": res["original_height"],
                "width": res["width"],
                "height": res["height"],
                "bg_type": res["bg_type"],
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

    # Cleanup background template if uploaded
    if bg_image_temp and bg_image_temp.exists():
        bg_image_temp.unlink(missing_ok=True)

    background_tasks.add_task(FileManager.cleanup_old_files)

    return {
        "total": len(files),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    }
