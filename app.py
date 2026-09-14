from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from docling.document_converter import DocumentConverter
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

app = FastAPI(title="PDF to EPUB parser", version="0.1.0")
converter = DocumentConverter()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/convert")
async def convert(
    file: UploadFile = File(...),
    format: str = Query("html", pattern="^(html|md|json)$"),
):
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Upload a PDF file")

    suffix = Path(file.filename or "document.pdf").suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=415, detail="File must have a .pdf extension")

    with tempfile.TemporaryDirectory(prefix="docling-") as tmpdir:
        input_path = Path(tmpdir) / "input.pdf"
        with input_path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                out.write(chunk)

        try:
            result = converter.convert(input_path)
            document = result.document
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Docling conversion failed: {exc}") from exc

        if format == "html":
            return HTMLResponse(document.export_to_html())
        if format == "md":
            return PlainTextResponse(document.export_to_markdown(), media_type="text/markdown")

        exported = document.export_to_dict()
        return JSONResponse(content=json.loads(json.dumps(exported, default=str)))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
