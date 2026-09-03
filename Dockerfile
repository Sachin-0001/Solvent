FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt

# CPU-only torch first, before sentence-transformers pulls in the default
# CUDA build as a transitive dep — this API never touches a GPU, and the
# CUDA build costs ~380MB extra RAM at import time for nothing (measured:
# 587MB vs 210MB just to `import torch`), which matters on a memory-capped
# free-tier host.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
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
