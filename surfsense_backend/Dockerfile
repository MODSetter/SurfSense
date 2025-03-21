FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml .
COPY uv.lock .

# Install python dependencies
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache-dir -e .

# Install Playwright browsers for web scraping if needed
RUN pip install playwright && \
    playwright install --with-deps chromium

# Copy source code
COPY . .

# Prevent uvloop compatibility issues
ENV PYTHONPATH=/app
ENV UVICORN_LOOP=asyncio

# Run
EXPOSE 8000
CMD ["python", "main.py"] 