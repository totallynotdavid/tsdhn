FROM ghcr.io/totallynotdavid/seismic-toolkit:main

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        sudo vim nano htop \
        iputils-ping net-tools \
        bash-completion \
        git git-lfs \
        # Debugging tools
        gdb strace lsof \
        # Process monitoring
        htop && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Configure sudo access for appuser
RUN echo "appuser ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/appuser && \
    chmod 0440 /etc/sudoers.d/appuser

RUN . ${VIRTUAL_ENV}/bin/activate && \
    pip install --no-cache-dir \
        pylint black isort mypy \
        ipython ipdb \
        pytest pytest-cov \
        jupyter

RUN echo 'export PS1="\[\e[32m\]\u@dev-container\[\e[m\]:\[\e[34m\]\w\[\e[m\]\\$ "' >> /app/.bashrc && \
    echo 'alias ll="ls -la"' >> /app/.bashrc && \
    echo 'alias python=python3' >> /app/.bashrc && \
    chown appuser:appuser /app/.bashrc

USER appuser
WORKDIR /app

CMD ["bash"]
