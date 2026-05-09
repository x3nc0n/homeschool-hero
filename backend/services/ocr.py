from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from statistics import pvariance

import fitz
from PIL import Image, ImageOps
import pytesseract

logger = logging.getLogger(__name__)


def _apply_threshold(image: Image.Image) -> Image.Image:
    return image.point(lambda px: 255 if px > 160 else 0)


def _projection_variance(image: Image.Image) -> float:
    width, height = image.size
    pixels = list(image.getdata())
    row_totals = []
    for row in range(height):
        start = row * width
        row_pixels = pixels[start : start + width]
        row_totals.append(sum(1 for value in row_pixels if value < 128))
    return pvariance(row_totals) if row_totals else 0.0


def _deskew(image: Image.Image) -> Image.Image:
    best_image = image
    best_score = _projection_variance(image)

    for angle in (-3, -2, -1, 0, 1, 2, 3):
        rotated = image.rotate(angle, expand=True, fillcolor=255)
        score = _projection_variance(rotated)
        if score > best_score:
            best_image = rotated
            best_score = score
    return best_image


def preprocess_image(image: Image.Image) -> Image.Image:
    normalized = ImageOps.exif_transpose(image).convert("L")
    deskewed = _deskew(normalized)
    return _apply_threshold(deskewed)


def _extract_text_from_pil_image(image: Image.Image) -> str:
    processed = preprocess_image(image)
    return pytesseract.image_to_string(processed).strip()


def extract_text_from_image(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        logger.warning("OCR file does not exist: %s", path)
        return ""

    try:
        with Image.open(path) as image:
            return _extract_text_from_pil_image(image)
    except pytesseract.TesseractNotFoundError:
        logger.warning("OCR skipped because Tesseract is unavailable: %s", path)
        return ""
    except Exception:
        logger.exception("OCR failed for image: %s", path)
        return ""


def extract_text_from_pdf(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        logger.warning("OCR file does not exist: %s", path)
        return ""

    pages: list[str] = []
    try:
        with fitz.open(path) as document:
            for page in document:
                pixmap = page.get_pixmap(dpi=200)
                with Image.open(BytesIO(pixmap.tobytes("png"))) as image:
                    page_text = _extract_text_from_pil_image(image)
                if page_text:
                    pages.append(page_text)
        return "\n\n".join(pages).strip()
    except pytesseract.TesseractNotFoundError:
        logger.warning("OCR skipped because Tesseract is unavailable: %s", path)
        return ""
    except Exception:
        logger.exception("OCR failed for PDF: %s", path)
        return ""


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    if path.suffix.lower() == ".pdf":
        return extract_text_from_pdf(file_path)
    return extract_text_from_image(file_path)
