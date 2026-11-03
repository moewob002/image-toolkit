import os
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from PIL import Image, ImageOps, ImageColor
from app.core.config import settings
from app.core.security import generate_safe_filename, ensure_safe_path

logger = logging.getLogger("background_removal")

# Global session cache to prevent reloading ONNX model on every image
_session_lock = threading.Lock()
_rembg_sessions: Dict[str, Any] = {}

def get_rembg_session(model_name: Optional[str] = None):
    model = model_name or settings.BG_MODEL_NAME
    with _session_lock:
        if model not in _rembg_sessions:
            try:
                import rembg
                # rembg uses U2NET_HOME environment variable to store/load models
                os.environ["U2NET_HOME"] = str(settings.MODELS_DIR)
                logger.info(f"Initializing rembg ONNX session with model '{model}' in '{settings.MODELS_DIR}'...")
                session = rembg.new_session(model)
                _rembg_sessions[model] = session
                logger.info(f"Successfully loaded rembg session '{model}'")
            except Exception as e:
                logger.error(f"Failed to initialize rembg session: {e}")
                raise RuntimeError(
                    f"Failed to initialize AI model '{model}'. If running offline, ensure the ONNX model file "
                    f"is placed in '{settings.MODELS_DIR}'. Details: {str(e)}"
                )
        return _rembg_sessions[model]


class BackgroundRemover:
    @classmethod
    def remove_background(
        cls,
        source_path: Path,
        bg_type: str = "transparent",  # 'transparent' | 'color' | 'image'
        bg_color: Optional[str] = None,  # Hex color like '#FFFFFF'
        bg_image_path: Optional[Path] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        source_path = ensure_safe_path(source_path, settings.UPLOAD_DIR)
        original_size = source_path.stat().st_size

        with Image.open(source_path) as raw_img:
            orig_format = (raw_img.format or "PNG").upper()
            if orig_format == "JPG":
                orig_format = "JPEG"
            try:
                img = ImageOps.exif_transpose(raw_img) or raw_img
            except Exception:
                img = raw_img
            orig_width, orig_height = img.size

        session = get_rembg_session(model_name)

        try:
            import rembg
            with open(source_path, "rb") as f:
                input_bytes = f.read()
            # Remove background using the cached session
            output_data = rembg.remove(input_bytes, session=session)
        except Exception as e:
            raise RuntimeError(f"Background removal processing error: {str(e)}")

        # Load the transparent RGBA foreground (handle both bytes and PIL.Image output)
        import io
        if isinstance(output_data, Image.Image):
            fg_image = output_data.convert("RGBA")
        else:
            fg_image = Image.open(io.BytesIO(output_data)).convert("RGBA")
        fg_w, fg_h = fg_image.size

        # Apply background replacement
        final_image = cls._composite_background(fg_image, bg_type, bg_color, bg_image_path)

        # Output is transparent PNG or RGB PNG/JPEG if background is opaque
        out_format = "PNG"
        out_filename = generate_safe_filename("png")
        output_path = settings.OUTPUT_DIR / out_filename

        final_image.save(output_path, format=out_format, optimize=True)
        final_size = output_path.stat().st_size

        return {
            "filename": out_filename,
            "output_path": str(output_path),
            "format": out_format,
            "original_format": orig_format,
            "original_width": orig_width,
            "original_height": orig_height,
            "width": fg_w,
            "height": fg_h,
            "original_size_bytes": original_size,
            "size_bytes": final_size,
            "bg_type": bg_type,
        }

    @classmethod
    def _composite_background(
        cls,
        fg: Image.Image,
        bg_type: str,
        bg_color: Optional[str],
        bg_image_path: Optional[Path],
    ) -> Image.Image:
        w, h = fg.size

        if bg_type == "transparent":
            return fg

        if bg_type == "color":
            hex_color = (bg_color or "#FFFFFF").strip()
            if not hex_color.startswith("#"):
                hex_color = f"#{hex_color}"
            try:
                rgb = ImageColor.getrgb(hex_color)
            except Exception:
                rgb = (255, 255, 255)
            bg = Image.new("RGBA", (w, h), (*rgb, 255))
            bg.paste(fg, mask=fg.split()[3])
            return bg

        if bg_type == "image" and bg_image_path and bg_image_path.exists():
            bg_image_path = ensure_safe_path(bg_image_path, settings.UPLOAD_DIR)
            with Image.open(bg_image_path) as bg_raw:
                try:
                    bg_raw = ImageOps.exif_transpose(bg_raw) or bg_raw
                except Exception:
                    pass
                # Fit/crop custom background to match foreground dimensions
                fitted_bg = ImageOps.fit(bg_raw.convert("RGBA"), (w, h), method=Image.Resampling.LANCZOS)
                fitted_bg.paste(fg, mask=fg.split()[3])
                return fitted_bg

        return fg
