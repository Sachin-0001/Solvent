FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Pre-download the embedding model at build time so the first request in
# production doesn't stall on a HuggingFace fetch (or fail if outbound
# network access is restricted at runtime).
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY backend backend
COPY ML/notebooks/artifacts ML/notebooks/artifacts

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
