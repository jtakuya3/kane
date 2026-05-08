FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install fastapi "uvicorn[standard]" httpx python-dotenv

COPY kane ./kane
RUN pip install --no-deps .

ENV HOST=0.0.0.0 PORT=8000
EXPOSE 8000

# Healthcheck — a simple GET on /api/health.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3).status==200 else 1)"

CMD ["python", "-m", "kane.server"]
