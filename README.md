# pdf-to-epub

Minimal Docling-backed PDF parser service for testing PDF → structured document conversion before EPUB packaging.

## API

- `GET /health`
- `POST /convert?format=html|md|json` with multipart field `file`

Example:

```bash
curl -F file=@book.pdf 'http://localhost:8000/convert?format=html' -o book.html
```

## Local

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

## Docker

```bash
docker build -t pdf-to-epub .
docker run --rm -p 8000:8000 pdf-to-epub
```
