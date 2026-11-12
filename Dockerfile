# VITALIS backend: FastAPI + trained NCS ML models
# Works on Render, Hugging Face Spaces (Docker), Koyeb, Fly.io or any container host.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
# scikit-learn pinned to the version the models were trained/saved with (safe unpickling)
RUN pip install -r requirements.txt "scikit-learn==1.8.0"

COPY app ./app
COPY ml_model ./ml_model

# Run as a non-root user with a writable home for the SQLite demo database
RUN useradd -m -u 1000 vitalis && chown -R vitalis /app
USER vitalis

# Demo database is created and seeded automatically on startup (SEED_ON_STARTUP=true).
ENV DATABASE_URL=sqlite:////app/vitalis.db

# Hosts inject $PORT (Render, Koyeb); Hugging Face Spaces uses 7860.
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
