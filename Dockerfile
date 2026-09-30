FROM python:3.12-slim

# tesseract + Czech language data for scanned-PDF OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-ces curl \
  && rm -rf /var/lib/apt/lists/*

# uv for fast dependency management
RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml README.md uv.lock ./
COPY dovera ./dovera

RUN uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8600 8700

# default: GUI. Override: docker run dovera-store / dovera check <pdf>
CMD ["dovera", "ui"]
