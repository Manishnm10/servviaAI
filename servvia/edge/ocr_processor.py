"""
ServVia Edge — Document Extractor
==================================

Local-only text extraction from lab report files.
Runs entirely on the user's machine — no data leaves the device.

Supports:
    - Digital PDFs (pdfplumber — fast, no OCR needed)
    - Scanned images / photographed reports (easyocr — neural OCR)
"""

import logging
import os
from typing import Optional

import pdfplumber

logger = logging.getLogger("ServVia.Edge.OCR")


class DocumentExtractor:
    """Extract text from lab report PDFs and images locally."""

    def __init__(self, ocr_languages: Optional[list] = None):
        """
        Args:
            ocr_languages: Language codes for easyocr (default: ["en"]).
                           Lazy-loaded on first image call to save RAM.
        """
        self._ocr_languages = ocr_languages or ["en"]
        self._ocr_reader = None  # Lazy init — easyocr loads ~1GB models

    def extract_text_from_pdf(self, file_path: str) -> str:
        """
        Extract text from a digital PDF using pdfplumber.

        Args:
            file_path: Absolute path to the PDF file.

        Returns:
            Concatenated text from all pages.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If no text could be extracted.
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"PDF not found: {file_path}")

        pages_text = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    pages_text.append(text)
                    logger.debug(f"Page {i + 1}: extracted {len(text)} chars")

        if not pages_text:
            raise ValueError(
                f"No text extracted from {file_path}. "
                "The PDF may be image-based — try extract_text_from_image() instead."
            )

        full_text = "\n\n".join(pages_text)
        logger.info(
            f"Extracted {len(full_text)} chars from {len(pages_text)} pages: {file_path}"
        )
        return full_text

    def extract_text_from_image(self, image_path: str) -> str:
        """
        Extract text from a scanned lab report image using easyocr.

        Args:
            image_path: Path to the image file (PNG, JPG, TIFF, etc.)

        Returns:
            Extracted text joined by newlines.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If no text could be extracted.
        """
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        if self._ocr_reader is None:
            import easyocr
            logger.info(f"Initializing easyocr with languages: {self._ocr_languages}")
            self._ocr_reader = easyocr.Reader(self._ocr_languages, gpu=False)

        results = self._ocr_reader.readtext(image_path, detail=0)

        if not results:
            raise ValueError(f"No text extracted from image: {image_path}")

        full_text = "\n".join(results)
        logger.info(
            f"OCR extracted {len(full_text)} chars from {len(results)} text regions: {image_path}"
        )
        return full_text

    def extract(self, file_path: str) -> str:
        """
        Auto-detect file type and extract text.

        Args:
            file_path: Path to PDF or image file.

        Returns:
            Extracted text.
        """
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            try:
                return self.extract_text_from_pdf(file_path)
            except (ValueError, Exception) as e:
                logger.info(f"PDF text extraction failed ({e}), falling back to OCR")
                return self.extract_text_from_image(file_path)

        if ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"):
            return self.extract_text_from_image(file_path)

        raise ValueError(f"Unsupported file type: {ext}")
