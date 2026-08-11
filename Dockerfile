# Legal-AI backend
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Only what the API serves at runtime.
COPY backend/ ./backend/
COPY data/ ./data/
COPY tools/validate_data.py ./tools/

# Fail the build if the shipped data doesn't match the schemas.
RUN python tools/validate_data.py

RUN useradd -m app && chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/livez').status==200 else 1)"

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
