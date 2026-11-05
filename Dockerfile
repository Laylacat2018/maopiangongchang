FROM node:22-bookworm-slim AS web
WORKDIR /build
COPY web/package*.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.14-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CATSTUDIO_DATA=/var/lib/catstudio/data TMPDIR=/var/lib/catstudio/data/tmp
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 catstudio && useradd --uid 10001 --gid 10001 --create-home catstudio
WORKDIR /app
COPY requirements-lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements-lock.txt
COPY catstudio/ ./catstudio/
COPY scripts/create_server_auth.py ./scripts/create_server_auth.py
COPY VERSION ./
COPY --from=web /build/dist/ ./web/dist/
RUN mkdir -p /var/lib/catstudio/data /var/lib/catstudio/secrets \
    && chown -R 10001:10001 /var/lib/catstudio && chmod 700 /var/lib/catstudio/secrets
USER 10001:10001
EXPOSE 8776
CMD ["python", "-m", "uvicorn", "catstudio.main:app", "--host", "0.0.0.0", "--port", "8776", "--workers", "1", "--no-access-log", "--no-proxy-headers"]
