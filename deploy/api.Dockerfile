# FastAPI and the Procrastinate worker run in this image for the self-hosted backend.
#
# Builds on the TSDHN toolchain base, which provides the scientific runtime:
# GMT, Intel Fortran, Typst, and ttt_client. The base ships Python 3.12 for
# system tooling; the app uses uv-managed Python 3.14.
#
# Build context is the repo root:  docker build -f deploy/api.Dockerfile .
ARG TOOLCHAIN_IMAGE=ghcr.io/totallynotdavid/tsdhn-toolchain:main
FROM ${TOOLCHAIN_IMAGE}

USER root
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python

COPY --from=ghcr.io/astral-sh/uv:0.11.25 /uv /uvx /usr/local/bin/

WORKDIR /app

# Dependencies are installed before source changes invalidate the build cache.
COPY pyproject.toml uv.lock ./
COPY packages ./packages
RUN uv python install 3.14 \
 && uv sync --frozen --no-dev --package tsdhn-api

# TSDHN_MODEL_DIR points at this copied model tree at runtime.
COPY model ./model
RUN mkdir -p /app/tools \
 && ifx -parallel /app/model/fault_plane.f90 -o /app/tools/fault_plane \
 && ifx -parallel /app/model/def_oka.f -o /app/tools/deform \
 && ifx -parallel -qopenmp /app/model/tsunami1.for -o /app/tools/tsunami \
 && command -v gmt \
 && command -v ttt_client \
 && command -v typst \
 && test -x /app/tools/fault_plane \
 && test -x /app/tools/deform \
 && test -x /app/tools/tsunami

ENV APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    COMPUTE_DATABASE_URL=postgresql://tsdhn:tsdhn@postgres:5432/tsdhn_compute \
    MINIO_ENDPOINT=minio:9000 \
    MINIO_ACCESS_KEY=minioadmin \
    MINIO_SECRET_KEY=minioadmin \
    MINIO_BUCKET=tsdhn-results \
    TSDHN_MODEL_DIR=/app/model \
    TSDHN_TOOLS_DIR=/app/tools \
    TSDHN_JOBS_DIR=/app/jobs

EXPOSE 8000
CMD ["uv", "run", "--no-dev", "tsdhn-api"]
