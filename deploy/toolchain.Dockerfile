FROM ubuntu:26.04

ARG TTT_SDK_REPO="https://gitlab.com/totallynotdavid/tttapi/"
ARG TYPST_VERSION=0.15.0

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    INTEL_ONEAPI_ROOT=/opt/intel/oneapi \
    PATH="/opt/intel/oneapi/compiler/latest/bin:/usr/local/bin:${PATH}" \
    LD_LIBRARY_PATH="/opt/intel/oneapi/compiler/latest/lib:${LD_LIBRARY_PATH}"

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
        libcurl4 \
        libfftw3-dev \
        libgdal-dev \
        liblapack-dev \
        libnetcdf-dev \
        libpcre3 \
        lsb-release \
        make \
        pkg-config \
        ps2eps \
        python3.12 \
        python3.12-venv \
        python3-pip \
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

RUN mkdir -p /tmp/ttt-sdk-build \
 && git clone --depth 1 "${TTT_SDK_REPO}" /tmp/ttt-sdk-build/tttapi \
 && make -C /tmp/ttt-sdk-build/tttapi config compile \
 && make -C /tmp/ttt-sdk-build/tttapi install clean \
 && rm -rf /tmp/ttt-sdk-build

ADD https://github.com/typst/typst/releases/download/v${TYPST_VERSION}/typst-x86_64-unknown-linux-musl.tar.xz /tmp/typst.tar.xz
RUN tar -xJf /tmp/typst.tar.xz -C /tmp \
 && install /tmp/typst-x86_64-unknown-linux-musl/typst /usr/local/bin/typst \
 && rm -rf /tmp/typst.tar.xz /tmp/typst-x86_64-unknown-linux-musl

# pygmt expects an unversioned libgmt.so on the dynamic linker path.
RUN set -eux; \
    SO="$(ls /lib/*/libgmt.so.* /usr/lib/*/libgmt.so.* 2>/dev/null | head -n1)"; \
    if [ -n "$SO" ]; then ln -sf "$SO" "$(dirname "$SO")/libgmt.so"; fi; \
    command -v gmt; \
    command -v ttt_client; \
    command -v typst; \
    command -v ifx

WORKDIR /app
USER appuser
CMD ["bash"]
