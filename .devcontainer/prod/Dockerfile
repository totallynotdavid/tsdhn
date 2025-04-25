FROM ubuntu:24.04 AS base

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/usr/local/texlive/bin/x86_64-linux:${PATH}"

# Create non-root user
RUN groupadd -r appuser && \
    useradd --no-log-init -r -g appuser -m -d /app -s /bin/bash -c "application-user" appuser

# ========================
# Base system dependencies
# ========================
FROM base AS system-deps

# Install system dependencies in a single layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        # Core Utils
        wget curl ca-certificates gnupg lsb-release git git-lfs \
        # Python 3.12
        python3.12 python3.12-venv python3-pip \
        # Build Essentials
        build-essential cmake make pkg-config \
        # TeXLive Installer Dep
        perl \
        # App Runtime Deps
        csh ps2eps fontconfig && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Initialize git-lfs
RUN git lfs install --system

# Create and activate Python virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python3.12 -m venv ${VIRTUAL_ENV}
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# ========================
# TTT SDK installation
# ========================
FROM system-deps AS ttt-builder

ARG TTT_SDK_REPO="https://gitlab.com/totallynotdavid/tttapi/"

WORKDIR /tmp/ttt-sdk-build

# Clone and build TTT SDK
RUN git clone --depth 1 "${TTT_SDK_REPO}" tttapi
WORKDIR /tmp/ttt-sdk-build/tttapi
RUN make config compile && \
    make install clean

# ========================
# TeXLive installation
# ========================
FROM system-deps AS texlive-builder

ENV TEXLIVE_INSTALL_DIR=/usr/local/texlive
ARG TEXLIVE_INSTALLER_URL="https://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz"

WORKDIR /tmp/texlive-install

# Download and install TeXLive
RUN wget -q -O install-tl-unx.tar.gz "${TEXLIVE_INSTALLER_URL}" && \
    INSTALL_TL_DIR=$(tar -tzf install-tl-unx.tar.gz | head -1 | cut -f1 -d"/") && \
    tar -xzf install-tl-unx.tar.gz && \
    cd "${INSTALL_TL_DIR}" && \
    echo "selected_scheme scheme-basic" > texlive.profile && \
    echo "tlpdbopt_autobackup 0" >> texlive.profile && \
    echo "tlpdbopt_install_docfiles 0" >> texlive.profile && \
    echo "tlpdbopt_install_srcfiles 0" >> texlive.profile && \
    perl ./install-tl \
        --profile=texlive.profile \
        --repository=http://mirror.ctan.org/systems/texlive/tlnet \
        --texdir="${TEXLIVE_INSTALL_DIR}" \
        --no-interaction && \
    "${TEXLIVE_INSTALL_DIR}/bin/x86_64-linux/tlmgr" option repository http://mirror.ctan.org/systems/texlive/tlnet && \
    "${TEXLIVE_INSTALL_DIR}/bin/x86_64-linux/tlmgr" install --force \
        babel-spanish hyphen-spanish booktabs && \
    rm -rf /tmp/texlive-install "${TEXLIVE_INSTALL_DIR}/texmf-var/web2c/tlmgr.log" \
           "${TEXLIVE_INSTALL_DIR}/texmf-var/tlpkg/backups" /root/.texlive*

# ========================
# Intel Fortran Compiler installation
# ========================
FROM system-deps AS ifx-builder

ENV INTEL_ONEAPI_ROOT=/opt/intel/oneapi

RUN wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB \
    | gpg --dearmor | tee /usr/share/keyrings/oneapi-archive-keyring.gpg > /dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" \
    | tee /etc/apt/sources.list.d/oneAPI.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends intel-fortran-essentials && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /opt/intel/oneapi/installer_payloads \
           "${INTEL_ONEAPI_ROOT}/logs" /root/.intel/

# ========================
# Python dependencies
# ========================
FROM system-deps AS python-deps

WORKDIR /app

# Copy requirements file and install Python dependencies
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ========================
# Final image assembly
# ========================
FROM base

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.12 python3.12-venv \
        libcurl4 libpcre3 \
        ghostscript graphicsmagick ffmpeg \
        csh ps2eps fontconfig \
        libgdal-dev libnetcdf-dev libfftw3-dev libblas-dev liblapack-dev \
        gmt gmt-dcw gmt-gshhg \
        ghostscript gdal-bin graphicsmagick ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy virtual environment
ENV VIRTUAL_ENV=/opt/venv
COPY --from=python-deps ${VIRTUAL_ENV} ${VIRTUAL_ENV}
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

# Copy binaries from builder stages
COPY --from=ttt-builder /usr/local/bin/ttt_* /usr/local/bin/
COPY --from=texlive-builder /usr/local/texlive /usr/local/texlive
COPY --from=ifx-builder /opt/intel/oneapi /opt/intel/oneapi

# Update library links
RUN ldconfig

# Copy application code
WORKDIR /app
COPY --chown=appuser:appuser orchestrator ./orchestrator
COPY --chown=appuser:appuser model ./model
COPY --chown=appuser:appuser data ./data

# Set environment and path
ENV PATH="/usr/local/texlive/bin/x86_64-linux:/opt/intel/oneapi/setvars.sh:${PATH}" \
    INTEL_ONEAPI_ROOT=/opt/intel/oneapi

# Switch to non-root user
USER appuser

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"]
