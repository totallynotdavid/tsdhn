ARG TOOLCHAIN_IMAGE=ghcr.io/totallynotdavid/tsdhn-toolchain:main
FROM ${TOOLCHAIN_IMAGE}

USER root

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        bash-completion \
        gdb \
        htop \
        iputils-ping \
        lsof \
        nano \
        net-tools \
        strace \
        sudo \
        vim \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

RUN echo "appuser ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/appuser \
 && chmod 0440 /etc/sudoers.d/appuser

ENV VIRTUAL_ENV=/opt/venv
RUN python3.12 -m venv "${VIRTUAL_ENV}" \
 && "${VIRTUAL_ENV}/bin/pip" install --no-cache-dir --upgrade pip setuptools wheel \
 && "${VIRTUAL_ENV}/bin/pip" install --no-cache-dir \
        ipython \
        ipdb \
        jupyter

ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

RUN echo 'export PS1="\[\e[32m\]\u@dev-container\[\e[m\]:\[\e[34m\]\w\[\e[m\]\\$ "' >> /app/.bashrc \
 && echo 'alias ll="ls -la"' >> /app/.bashrc \
 && echo 'alias python=python3' >> /app/.bashrc \
 && chown appuser:appuser /app/.bashrc

USER appuser
WORKDIR /app

CMD ["bash"]
