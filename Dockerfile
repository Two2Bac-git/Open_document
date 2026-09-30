# Works with `docker build` and `podman build --format docker` (the HEALTHCHECK needs the docker format).
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
ARG VERSION=dev
ARG REVISION=unknown
LABEL org.opencontainers.image.title="Plow-Agent" \
      org.opencontainers.image.description="Sorts loose files by metadata and repairs broken symlinks, never reading file content." \
      org.opencontainers.image.source="https://github.com/Two2Bac-git/Open_document" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.authors="Andrey Bacelar" \
      org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.revision=$REVISION
WORKDIR /app
COPY plow.py indexer.py test_plow.py entrypoint.sh ./
# Container HOME: user folders are mounted here (e.g. /home/plow/Downloads)
ENV HOME=/home/plow \
    PLOW_LOG=/home/plow/.plow/plow.log \
    PLOW_DB=/home/plow/.plow/plow-agent.db \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
# The image only exists if the self-check passes.
RUN python3 test_plow.py >/dev/null && mkdir -p /home/plow/.plow && chmod +x entrypoint.sh
HEALTHCHECK --interval=60s --timeout=5s CMD kill -0 "$(cat /tmp/indexer.pid)"
CMD ["/app/entrypoint.sh"]
