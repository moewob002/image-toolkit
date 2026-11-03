import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from PIL import Image, ImageSequence, ImageOps
from app.core.config import settings
from app.core.security import generate_safe_filename, ensure_safe_path

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass

class ImageConverter:
    FORMAT_EXTENSIONS = {
        "JPEG": "jpg",
        "JPG": "jpg",
        "PNG": "png",
        "WEBP": "webp",
        "AVIF": "avif",
        "GIF": "gif",
        "BMP": "bmp",
        "TIFF": "tiff",
        "ICO": "ico",
    }

    TRANSPARENCY_FORMATS = {"PNG", "WEBP", "AVIF", "GIF", "ICO"}

    @classmethod
    def convert_image(
        cls,
        source_path: Path,
        target_format: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        preserve_aspect_ratio: bool = True,
        quality: int = 90,
        background_matte: Tuple[int, int, int] = (255, 255, 255),
    ) -> Dict[str, Any]:
        source_path = ensure_safe_path(source_path, settings.UPLOAD_DIR)
        target_fmt = target_format.upper()
        if target_fmt == "JPG":
            target_fmt = "JPEG"
            
        if target_fmt not in settings.SUPPORTED_CONVERT_FORMATS:
            raise ValueError(f"Unsupported target format: {target_format}. Supported: {settings.SUPPORTED_CONVERT_FORMATS}")

        ext = cls.FORMAT_EXTENSIONS.get(target_fmt, target_fmt.lower())
        output_filename = generate_safe_filename(ext)
        output_path = settings.OUTPUT_DIR / output_filename

        with Image.open(source_path) as raw_img:
            orig_format = (raw_img.format or "UNKNOWN").upper()
            if orig_format == "JPG":
                orig_format = "JPEG"
            try:
                img = ImageOps.exif_transpose(raw_img) or raw_img
            except Exception:
                img = raw_img

            orig_width, orig_height = img.size
            is_animated = getattr(img, "is_animated", False) and target_fmt == "GIF"

            # Compute new dimensions if resize requested
            new_width, new_height = cls._calculate_dimensions(
                orig_width, orig_height, width, height, preserve_aspect_ratio
            )

            if is_animated:
                cls._process_animated_gif(
                    img, output_path, new_width, new_height, quality
                )
            else:
                cls._process_single_frame(
                    img, target_fmt, output_path, new_width, new_height, quality, background_matte
                )

        final_stat = output_path.stat()
        return {
            "filename": output_filename,
            "output_path": str(output_path),
            "format": target_fmt,
            "target_format": target_fmt,
            "original_format": orig_format,
            "original_width": orig_width,
            "original_height": orig_height,
            "width": new_width,
            "height": new_height,
            "size_bytes": final_stat.st_size,
        }

    @classmethod
    def _calculate_dimensions(
        cls,
        orig_w: int,
        orig_h: int,
        target_w: Optional[int],
        target_h: Optional[int],
        preserve_aspect: bool,
    ) -> Tuple[int, int]:
        if not target_w and not target_h:
            return orig_w, orig_h

        if target_w and not target_h:
            if preserve_aspect:
                ratio = target_w / orig_w
                return max(1, target_w), max(1, int(round(orig_h * ratio)))
            return max(1, target_w), orig_h

        if target_h and not target_w:
            if preserve_aspect:
                ratio = target_h / orig_h
                return max(1, int(round(orig_w * ratio))), max(1, target_h)
            return orig_w, max(1, target_h)

        # Both width and height provided
        if target_w and target_h:
            if not preserve_aspect:
                return max(1, target_w), max(1, target_h)
            # Fit within box preserving aspect ratio
            ratio = min(target_w / orig_w, target_h / orig_h)
            return max(1, int(round(orig_w * ratio))), max(1, int(round(orig_h * ratio)))

        return orig_w, orig_h

    @classmethod
    def _process_single_frame(
        cls,
        img: Image.Image,
        target_fmt: str,
        output_path: Path,
        width: int,
        height: int,
        quality: int,
        background_matte: Tuple[int, int, int],
    ) -> None:
        # Resize if dimensions differ
        if (width, height) != img.size:
            img = img.resize((width, height), resample=Image.Resampling.LANCZOS)

        save_kwargs: Dict[str, Any] = {}
        supports_transparency = target_fmt in cls.TRANSPARENCY_FORMATS

        # Check if source has transparency
        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)

        if target_fmt in ("JPEG", "BMP"):
            # Target does not support alpha channel
            if has_alpha:
                # Matte with solid background color
                rgba_img = img.convert("RGBA")
                matte_bg = Image.new("RGB", rgba_img.size, background_matte)
                matte_bg.paste(rgba_img, mask=rgba_img.split()[3])
                final_img = matte_bg
            else:
                final_img = img.convert("RGB")
                
            if target_fmt == "JPEG":
                save_kwargs["quality"] = max(1, min(100, quality))
                save_kwargs["optimize"] = True
                save_kwargs["progressive"] = True

        elif target_fmt == "PNG":
            if has_alpha:
                final_img = img.convert("RGBA")
            else:
                final_img = img.convert("RGB")
            save_kwargs["optimize"] = True

        elif target_fmt == "WEBP":
            if has_alpha:
                final_img = img.convert("RGBA")
            else:
                final_img = img.convert("RGB")
            save_kwargs["quality"] = max(1, min(100, quality))
            save_kwargs["method"] = 6

        elif target_fmt == "AVIF":
            if has_alpha:
                final_img = img.convert("RGBA")
            else:
                final_img = img.convert("RGB")
            save_kwargs["quality"] = max(1, min(100, quality))

        elif target_fmt == "GIF":
            if has_alpha:
                final_img = img.convert("RGBA")
            else:
                final_img = img.convert("RGB")
            save_kwargs["optimize"] = True

        elif target_fmt == "TIFF":
            if has_alpha:
                final_img = img.convert("RGBA")
            else:
                final_img = img.convert("RGB")
            save_kwargs["compression"] = "tiff_lzw"

        elif target_fmt == "ICO":
            # ICO usually expects RGBA and max 256x256
            ico_w = min(256, width)
            ico_h = min(256, height)
            final_img = img.convert("RGBA").resize((ico_w, ico_h), resample=Image.Resampling.LANCZOS)
            save_kwargs["sizes"] = [(ico_w, ico_h)]

        else:
            final_img = img.convert("RGB")

        final_img.save(output_path, format=target_fmt, **save_kwargs)

    @classmethod
    def _process_animated_gif(
        cls,
        img: Image.Image,
        output_path: Path,
        width: int,
        height: int,
        quality: int,
    ) -> None:
        frames = []
        durations = []
        loop = img.info.get("loop", 0)

        for frame in ImageSequence.Iterator(img):
            f = frame.copy()
            if (width, height) != f.size:
                f = f.resize((width, height), resample=Image.Resampling.LANCZOS)
            frames.append(f)
            durations.append(frame.info.get("duration", 100))

        if frames:
            frames[0].save(
                output_path,
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=loop,
                optimize=True,
            )
        else:
            img.save(output_path, format="GIF")
