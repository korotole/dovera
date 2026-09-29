FROM python:3.12-slim

# tesseract + Czech language data for scanned-PDF OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-ces curl \
  && rm -rf /var/lib/apt/lists/*

# uv for fast dependency management
RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml README.md ./
COPY invoice_agent ./invoice_agent

RUN uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV ANNEX13_UI_PORT=8600

EXPOSE 8600 8700

# default: GUI. Override: docker run annex13-store / annex13 <pdf>
CMD ["annex13-ui"]
