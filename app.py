from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import OcrMode, PdfPipelineOptions, TesseractCliOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pdf-to-epub")

app = FastAPI(title="PDF to EPUB parser", version="0.2.0")

# Fast path for PDFs with a trustworthy embedded text layer.
native_converter = DocumentConverter()

# Reliable path for PDFs whose embedded text layer has broken glyph spacing,
# encoding, or reading order. Every page is rendered and OCRed from pixels.
ocr_options = TesseractCliOcrOptions(
    mode=OcrMode.FULL_PAGE,
    lang=["eng"],
)
ocr_pipeline_options = PdfPipelineOptions()
ocr_pipeline_options.do_ocr = True
ocr_pipeline_options.ocr_options = ocr_options
ocr_converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=ocr_pipeline_options,
        )
    }
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "ocr": "tesseract-full-page"}


@app.post("/convert")
async def convert(
    file: UploadFile = File(...),
    format: str = Query("html", pattern="^(html|md|json)$"),
    mode: str = Query("ocr", pattern="^(ocr|native)$"),
):
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Upload a PDF file")

    suffix = Path(file.filename or "document.pdf").suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=415, detail="File must have a .pdf extension")

    started = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="docling-") as tmpdir:
        input_path = Path(tmpdir) / "input.pdf"
        with input_path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                out.write(chunk)

        try:
            converter = ocr_converter if mode == "ocr" else native_converter
            result = converter.convert(input_path)
            document = result.document
        except Exception as exc:
            logger.exception("Docling conversion failed mode=%s", mode)
            raise HTTPException(status_code=422, detail=f"Docling conversion failed: {exc}") from exc

        elapsed = time.perf_counter() - started
        logger.info(
            "conversion_complete filename=%s mode=%s format=%s seconds=%.2f bytes=%d",
            file.filename,
            mode,
            format,
            elapsed,
            input_path.stat().st_size,
        )

        headers = {
            "X-Conversion-Mode": mode,
            "X-Conversion-Seconds": f"{elapsed:.2f}",
        }

        if format == "html":
            return HTMLResponse(document.export_to_html(), headers=headers)
        if format == "md":
            return PlainTextResponse(
                document.export_to_markdown(),
                media_type="text/markdown",
                headers=headers,
            )

        exported = document.export_to_dict()
        return JSONResponse(
            content=json.loads(json.dumps(exported, default=str)),
            headers=headers,
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
