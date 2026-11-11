# Pramaan API. Runs from source (the signing key + cache live in /srv/backend/data, mounted as a volume).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /srv/backend

# Dependencies first so code changes don't invalidate this layer.
COPY pyproject.toml ./
RUN python - <<'PY' > requirements.txt
import tomllib
print("\n".join(tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]))
PY
RUN apt-get update \
 && apt-get install -y --no-install-recommends libatomic1 \
 && pip install -r requirements.txt \
 && playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/*

# Semantic search model, baked into the image (no download at runtime). Build with
# --build-arg WITH_EMBEDDINGS=false (and set EMBEDDINGS=hash) on a host that is short on memory.
ARG WITH_EMBEDDINGS=true
ENV FASTEMBED_CACHE_PATH=/opt/fastembed
RUN if [ "$WITH_EMBEDDINGS" = "true" ]; then \
      pip install "fastembed>=0.3" \
      && python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')" \
      && chmod -R a+rX /opt/fastembed; \
    fi

COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
COPY plugins ./plugins
COPY scripts ./scripts

# Unprivileged user; it must be able to write the data dir and the plugin folder.
RUN useradd --uid 10001 --create-home pramaan && mkdir -p data && chown -R pramaan /srv/backend/data /srv/backend/plugins
USER pramaan

# Hosts like Railway tell us the port through $PORT; locally it stays 8000.
ENV PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=8 CMD python -c "import os,urllib.request as u; u.urlopen('http://127.0.0.1:%s/healthz' % os.environ['PORT'], timeout=4)"
# Schema first (Alembic), then the API. A separate worker service runs:  python -m app.worker
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
