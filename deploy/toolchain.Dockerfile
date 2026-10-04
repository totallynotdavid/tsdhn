FROM ubuntu:26.04

ARG TTT_SDK_REPO="https://gitlab.com/totallynotdavid/tttapi/"

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    INTEL_ONEAPI_ROOT=/opt/intel/oneapi \
    PATH="/opt/intel/oneapi/compiler/latest/bin:/usr/local/bin:${PATH}" \
    LD_LIBRARY_PATH="/opt/intel/oneapi/compiler/latest/lib"

RUN groupadd -r appuser \
 && useradd --no-log-init -r -g appuser -m -d /app -s /bin/bash -c "application-user" appuser

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        csh \
        curl \
        ffmpeg \
        fontconfig \
        gdal-bin \
        ghostscript \
        git \
        git-lfs \
        gnupg \
        graphicsmagick \
        gmt \
        gmt-dcw \
        gmt-gshhg \
        libblas-dev \
        libcurl4t64 \
        libfftw3-dev \
        libgdal-dev \
        liblapack-dev \
        libnetcdf-dev \
        lsb-release \
        make \
        pkg-config \
        ps2eps \
        python3 \
        python3-pip \
        python3-venv \
        wget \
        xz-utils \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

RUN git lfs install --system

RUN wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB \
    | gpg --dearmor > /usr/share/keyrings/oneapi-archive-keyring.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" \
    > /etc/apt/sources.list.d/oneAPI.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends intel-fortran-essentials \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /opt/intel/oneapi/installer_payloads \
          "${INTEL_ONEAPI_ROOT}/logs" /root/.intel/

# tttapi sets CMP0026 to OLD, which CMake 4 removed.
# Build tttapi with pinned CMake 3 in a temporary virtual environment.
RUN python3 -m venv /tmp/cmake3 \
 && /tmp/cmake3/bin/pip install --no-cache-dir cmake==3.31.6 \
 && export PATH="/tmp/cmake3/bin:${PATH}" \
 && mkdir -p /tmp/ttt-sdk-build \
 && git clone --depth 1 "${TTT_SDK_REPO}" /tmp/ttt-sdk-build/tttapi \
 && make -C /tmp/ttt-sdk-build/tttapi config compile \
 && make -C /tmp/ttt-sdk-build/tttapi install clean \
 && rm -rf /tmp/ttt-sdk-build /tmp/cmake3

# pygmt expects an unversioned libgmt.so on the dynamic linker path.
RUN set -eux; \
    SO="$(ls /lib/*/libgmt.so.* /usr/lib/*/libgmt.so.* 2>/dev/null | head -n1)"; \
    if [ -n "$SO" ]; then ln -sf "$SO" "$(dirname "$SO")/libgmt.so"; fi; \
    command -v gmt; \
    command -v gs; \
    command -v ttt_client; \
    command -v ifx

WORKDIR /app
USER appuser
CMD ["bash"]
