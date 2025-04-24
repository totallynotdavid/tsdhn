FROM ubuntu:24.04 AS base

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/usr/local/texlive/bin/x86_64-linux:/usr/local/share/gmt/bin:${PATH}" \
    GMT_SHAREDIR=/usr/local/share/gmt

# Create non-root user
RUN groupadd -r appuser && \
    useradd --no-log-init -r -g appuser -m -d /app -s /sbin/nologin -c "non-root-user" appuser

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
        python3.12 python3-pip \
        # Build Essentials
        build-essential make pkg-config \
        # GMT Build Deps & Runtime Libs
        cmake ninja-build \
        libcurl4-gnutls-dev libnetcdf-dev libgdal-dev gdal-bin \
        libfftw3-dev libpcre3-dev libpcre3 liblapack-dev \
        libblas-dev libglib2.0-dev \
        ghostscript graphicsmagick ffmpeg \
        # TeXLive Installer Dep
        perl \
        # App Runtime Deps
        csh ps2eps fontconfig && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Update pip & install essentials
RUN python3.12 -m pip install --no-cache-dir --upgrade pip setuptools wheel

# Initialize git-lfs
RUN git lfs install --system

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
    make install datadir docs && \
    make clean

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
    "${TEXLIVE_INSTALL_DIR}/bin/x86_64-linux/tlmgr" update --self && \
    "${TEXLIVE_INSTALL_DIR}/bin/x86_64-linux/tlmgr" install \
        babel-spanish hyphen-spanish booktabs multirow \
        adjustbox collectbox tcbox environ trimspaces epstopdf-pkg && \
    rm -rf /tmp/texlive-install "${TEXLIVE_INSTALL_DIR}/texmf-var/web2c/tlmgr.log" \
           "${TEXLIVE_INSTALL_DIR}/texmf-var/tlpkg/backups" /root/.texlive*

# ========================
# GMT installation
# ========================
FROM system-deps AS gmt-builder

ARG GMT_VERSION_TAG="6.5.0"
ARG GSHHG_VERSION="2.3.7"
ARG DCW_VERSION="2.2.0"
ENV GMT_SHAREDIR=/usr/local/share/gmt

WORKDIR /tmp/gmt-build

# Download source data and build GMT
RUN wget -q "https://github.com/GenericMappingTools/gshhg-gmt/releases/download/${GSHHG_VERSION}/gshhg-gmt-${GSHHG_VERSION}.tar.gz" && \
    wget -q "https://github.com/GenericMappingTools/dcw-gmt/releases/download/${DCW_VERSION}/dcw-gmt-${DCW_VERSION}.tar.gz" && \
    tar xzf "gshhg-gmt-${GSHHG_VERSION}.tar.gz" && \
    tar xzf "dcw-gmt-${DCW_VERSION}.tar.gz" && \
    git clone --depth 1 --branch "${GMT_VERSION_TAG}" https://github.com/GenericMappingTools/gmt.git && \
    cd gmt && \
    echo "set (CMAKE_INSTALL_PREFIX \"/usr/local\")" > cmake/ConfigUser.cmake && \
    echo "set (GSHHG_ROOT \"/tmp/gmt-build/gshhg-gmt-${GSHHG_VERSION}\")" >> cmake/ConfigUser.cmake && \
    echo "set (DCW_ROOT \"/tmp/gmt-build/dcw-gmt-${DCW_VERSION}\")" >> cmake/ConfigUser.cmake && \
    echo "set (GMT_INSTALL_MODULE_LINKS OFF)" >> cmake/ConfigUser.cmake && \
    echo "set (GMT_INSTALL_TRADITIONAL_FOLDERNAMES OFF)" >> cmake/ConfigUser.cmake && \
    mkdir build && cd build && \
    cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Release && \
    cmake --build . && \
    cmake --build . --target install && \
    ldconfig

# ========================
# Intel Fortran Compiler installation
# ========================
FROM system-deps AS ifx-builder

ENV INTEL_ONEAPI_ROOT=/opt/intel/oneapi
ARG IFX_INSTALLER_URL="https://registrationcenter-download.intel.com/akdlm/IRC_NAS/306e03be-1259-4d71-848a-59e23013c4f0/intel-fortran-essentials-2025.1.0.556_offline.sh"

WORKDIR /tmp/ifx-install

# Download and install Intel Fortran Compiler
RUN wget -q --show-progress "${IFX_INSTALLER_URL}" -O intel-fortran-essentials.sh && \
    chmod +x intel-fortran-essentials.sh && \
    ./intel-fortran-essentials.sh -a --silent --eula accept --install-dir "${INTEL_ONEAPI_ROOT}" && \
    rm -rf /tmp/ifx-install /opt/intel/oneapi/installer_payloads \
           "${INTEL_ONEAPI_ROOT}/logs" /root/.intel/

# ========================
# Python dependencies
# ========================
FROM system-deps AS python-deps

WORKDIR /app

# Copy requirements file and install Python dependencies
COPY --chown=appuser:appuser requirements.txt .
RUN python3.12 -m pip install --no-cache-dir -r requirements.txt

# ========================
# Final image assembly
# ========================
FROM base

# Copy tools from builder stages
COPY --from=ttt-builder /usr/local/bin/ttt_* /usr/local/bin/
COPY --from=ttt-builder /usr/local/share/ttt /usr/local/share/ttt
COPY --from=texlive-builder /usr/local/texlive /usr/local/texlive
COPY --from=gmt-builder /usr/local/bin/gmt* /usr/local/bin/
COPY --from=gmt-builder /usr/local/share/gmt /usr/local/share/gmt
COPY --from=ifx-builder /opt/intel/oneapi /opt/intel/oneapi
COPY --from=python-deps /usr/local/lib/python3.12/dist-packages /usr/local/lib/python3.12/dist-packages

# Copy application code
WORKDIR /app
COPY --chown=appuser:appuser orchestrator ./orchestrator
COPY --chown=appuser:appuser model ./model
COPY --chown=appuser:appuser data ./data

# Set environment and path
ENV PATH="/usr/local/texlive/bin/x86_64-linux:/usr/local/share/gmt/bin:/opt/intel/oneapi/setvars.sh:${PATH}" \
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
