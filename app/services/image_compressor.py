import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from PIL import Image, ImageOps
from app.core.config import settings
from app.core.security import generate_safe_filename, ensure_safe_path

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass

class ImageCompressor:
    PRESET_QUALITY = {
        "maximum": 40,
        "balanced": 72,
        "high_quality": 88,
    }

    FORMAT_MAP = {
        "JPEG": "jpg",
        "JPG": "jpg",
        "PNG": "png",
        "WEBP": "webp",
        "AVIF": "avif",
    }

    @classmethod
    def compress_image(
        cls,
        source_path: Path,
        preset: str = "balanced",
        quality: Optional[int] = None,
        target_format: Optional[str] = None,
        resize_mode: Optional[str] = None,  # 'percentage' or 'dimensions'
        resize_percentage: Optional[int] = None,  # 1-100
        width: Optional[int] = None,
        height: Optional[int] = None,
        preserve_aspect_ratio: bool = True,
    ) -> Dict[str, Any]:
        source_path = ensure_safe_path(source_path, settings.UPLOAD_DIR)
        original_size = source_path.stat().st_size

        with Image.open(source_path) as raw_img:
            orig_fmt = (raw_img.format or "PNG").upper()
            try:
                img = ImageOps.exif_transpose(raw_img) or raw_img
            except Exception:
                img = raw_img

            orig_width, orig_height = img.size
            if orig_fmt == "JPG":
                orig_fmt = "JPEG"

            # Determine output format
            out_fmt = (target_format or orig_fmt).upper()
            if out_fmt == "JPG":
                out_fmt = "JPEG"
            if out_fmt not in settings.SUPPORTED_COMPRESS_FORMATS:
                out_fmt = "JPEG" if orig_fmt in ("JPEG", "JPG") else "PNG"

            # Determine quality level
            if quality is not None and 10 <= quality <= 100:
                eff_quality = quality
            else:
                eff_quality = cls.PRESET_QUALITY.get(preset.lower(), 72)

            # Determine resizing
            target_w, target_h = cls._calculate_resized_dimensions(
                orig_width, orig_height, resize_mode, resize_percentage, width, height, preserve_aspect_ratio
            )

            if (target_w, target_h) != (orig_width, orig_height):
                img = img.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)

            ext = cls.FORMAT_MAP.get(out_fmt, "png")
            output_filename = generate_safe_filename(ext)
            output_path = settings.OUTPUT_DIR / output_filename

            # Compress and save
            cls._save_compressed(img, out_fmt, output_path, eff_quality, preset)

        compressed_size = output_path.stat().st_size
        savings_bytes = max(0, original_size - compressed_size)
        savings_percent = round((savings_bytes / original_size * 100), 2) if original_size > 0 else 0.0

        return {
            "filename": output_filename,
            "output_path": str(output_path),
            "format": out_fmt,
            "target_format": out_fmt,
            "original_size_bytes": original_size,
            "compressed_size_bytes": compressed_size,
            "savings_bytes": savings_bytes,
            "savings_percent": savings_percent,
            "original_width": orig_width,
            "original_height": orig_height,
            "width": target_w,
            "height": target_h,
            "quality_used": eff_quality,
            "preset": preset,
            "preset_used": preset,
        }

    @classmethod
    def _calculate_resized_dimensions(
        cls,
        orig_w: int,
        orig_h: int,
        resize_mode: Optional[str],
        percentage: Optional[int],
        width: Optional[int],
        height: Optional[int],
        preserve_aspect: bool,
    ) -> Tuple[int, int]:
        if resize_mode == "percentage" and percentage and 1 <= percentage <= 100:
            scale = percentage / 100.0
            return max(1, int(round(orig_w * scale))), max(1, int(round(orig_h * scale)))

        if resize_mode == "dimensions":
            if width and not height:
                if preserve_aspect:
                    scale = width / orig_w
                    return max(1, width), max(1, int(round(orig_h * scale)))
                return max(1, width), orig_h
            if height and not width:
                if preserve_aspect:
                    scale = height / orig_h
                    return max(1, int(round(orig_w * scale))), max(1, height)
                return orig_w, max(1, height)
            if width and height:
                if not preserve_aspect:
                    return max(1, width), max(1, height)
                scale = min(width / orig_w, height / orig_h)
                return max(1, int(round(orig_w * scale))), max(1, int(round(orig_h * scale)))

        return orig_w, orig_h

    @classmethod
    def _save_compressed(cls, img: Image.Image, fmt: str, out_path: Path, quality: int, preset: str) -> None:
        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)

        if fmt == "JPEG":
            if has_alpha:
                # Matte with white
                rgba = img.convert("RGBA")
                bg = Image.new("RGB", rgba.size, (255, 255, 255))
                bg.paste(rgba, mask=rgba.split()[3])
                rgb_img = bg
            else:
                rgb_img = img.convert("RGB")
            rgb_img.save(out_path, format="JPEG", quality=quality, optimize=True, progressive=True)

        elif fmt == "PNG":
            # PNG is lossless, but palette quantization can significantly compress PNGs for maximum preset
            if preset == "maximum":
                if has_alpha:
                    # Convert RGBA to quantified palette with alpha
                    rgba = img.convert("RGBA")
                    quantized = rgba.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
                    quantized.save(out_path, format="PNG", optimize=True)
                else:
                    rgb = img.convert("RGB")
                    quantized = rgb.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
                    quantized.save(out_path, format="PNG", optimize=True)
            elif preset == "balanced":
                if has_alpha:
                    rgba = img.convert("RGBA")
                    quantized = rgba.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
                    quantized.save(out_path, format="PNG", optimize=True)
                else:
                    rgb = img.convert("RGB")
                    rgb.save(out_path, format="PNG", optimize=True)
            else:
                # High quality
                if has_alpha:
                    img.convert("RGBA").save(out_path, format="PNG", optimize=True)
                else:
                    img.convert("RGB").save(out_path, format="PNG", optimize=True)

        elif fmt == "WEBP":
            mode_img = img.convert("RGBA") if has_alpha else img.convert("RGB")
            mode_img.save(out_path, format="WEBP", quality=quality, method=6)

        elif fmt == "AVIF":
            mode_img = img.convert("RGBA") if has_alpha else img.convert("RGB")
            mode_img.save(out_path, format="AVIF", quality=quality)

        else:
            img.convert("RGB").save(out_path, format=fmt, quality=quality)
