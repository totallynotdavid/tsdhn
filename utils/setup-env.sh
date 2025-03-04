#!/bin/bash
set -eo pipefail

log_info() { echo -e "\n■ $1"; }
log_success() { echo -e "✓ $1"; }
log_warn() { echo -e "◇ $1"; }

cmd_exists() {
    command -v "$1" &>/dev/null
}

is_pkg_installed() {
    dpkg -s "$1" &>/dev/null
}

path_exists() {
    [[ -e "$1" ]]
}

safe_exec() {
    if ! "$@"; then
        log_warn "Command failed: $*"
        return 1
    fi
    return 0
}

has_python_version() {
    local required_version="$1"
    local python_cmd

    if cmd_exists "python3"; then
        python_cmd="python3"
        local py_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        if [[ "$py_version" == "$required_version" ]]; then
            return 0
        fi
    fi


    if cmd_exists "python$required_version"; then
        return 0
    fi
    
    # Check if pyenv has the required version
    if cmd_exists "pyenv"; then
        if pyenv versions 2>/dev/null | grep -q "$required_version"; then
            return 0
        fi
    fi
    
    return 1
}

log_info "Checking system status"

REQUIRED_PKGS=(
    build-essential zlib1g-dev libffi-dev libssl-dev libbz2-dev
    libreadline-dev libsqlite3-dev liblzma-dev libncurses-dev tk-dev
    git-lfs cmake gfortran redis-server gmt gmt-dcw gmt-gshhg ps2eps csh
)

NEED_SYSTEM_PKGS=false
NEED_PYENV=false
NEED_PYTHON312=false
NEED_POETRY=false
NEED_TTT_SDK=false
NEED_TEXLIVE=false
NEED_REDIS_CONFIG=false
NEED_GMT_CONFIG=false

REQUIRED_PYTHON_VERSION="3.12"

missing_pkgs=()
for pkg in "${REQUIRED_PKGS[@]}"; do
    if ! is_pkg_installed "$pkg"; then
        missing_pkgs+=("$pkg")
    fi
done

if (( ${#missing_pkgs[@]} > 0 )); then
    NEED_SYSTEM_PKGS=true
    log_warn "Missing packages: ${missing_pkgs[*]}"
else
    log_success "All required packages are installed"
fi

if has_python_version "$REQUIRED_PYTHON_VERSION"; then
    if cmd_exists "python$REQUIRED_PYTHON_VERSION"; then
        log_success "Python $REQUIRED_PYTHON_VERSION is available in the system ($(python$REQUIRED_PYTHON_VERSION --version 2>&1))"
    elif cmd_exists "python3" && [[ $(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")') == "$REQUIRED_PYTHON_VERSION" ]]; then
        log_success "Python $REQUIRED_PYTHON_VERSION is available as the default python3 ($(python3 --version 2>&1))"
    elif cmd_exists "pyenv"; then
        PYTHON312_VERSION=$(pyenv versions 2>/dev/null | grep "$REQUIRED_PYTHON_VERSION" | 
                           sed -E 's/^[[:space:]]*\*?[[:space:]]*([3]\.12[0-9.]*).*/\1/' | 
                           head -1)
        log_success "Python ${PYTHON312_VERSION} is available via pyenv"
    fi
else
    log_warn "Python $REQUIRED_PYTHON_VERSION not found in system"
    NEED_PYTHON312=true

    if ! cmd_exists "pyenv"; then
        log_warn "pyenv command not found"
        NEED_PYENV=true
    else
        log_success "pyenv is available ($(pyenv --version 2>/dev/null || echo "unknown version"))"
    fi
fi

if ! cmd_exists "poetry"; then
    log_warn "Poetry not installed"
    NEED_POETRY=true
else
    log_success "Poetry is available ($(poetry --version 2>/dev/null || echo "unknown version"))"
fi

if ! cmd_exists "ttt_client"; then
    log_warn "TTT SDK not installed"
    NEED_TTT_SDK=true
else
    log_success "TTT SDK is available ($(ttt_client 2>&1 | head -n 2 | grep -oP '\[ttt API version \K[0-9]+\.[0-9]+\.[0-9]+'))"
fi

if ! path_exists "$HOME/texlive"; then
    log_warn "TeXLive not found in $HOME/texlive"
    NEED_TEXLIVE=true
else
    if ! cmd_exists "tex" && ! cmd_exists "pdflatex"; then
        if ! echo "$PATH" | grep -q "$HOME/texlive/bin"; then
            log_warn "TeXLive is installed but not in PATH"
            NEED_TEXLIVE=false
            export PATH="$HOME/texlive/bin/x86_64-linux:$PATH"
        else
            log_warn "TeXLive commands not found despite directory existing"
        fi
    else
        log_success "TeXLive is available ($(pdflatex --version | head -n 1 2>/dev/null || echo "unknown version"))"
    fi
fi

REDIS_CONF="/etc/redis/redis.conf"
if sudo test -f "$REDIS_CONF"; then
    if ! sudo grep -q "^supervised systemd" "$REDIS_CONF"; then
        log_warn "Redis not configured for systemd"
        NEED_REDIS_CONFIG=true
    else
        log_success "Redis is configured for systemd ($(redis-cli -v 2>/dev/null || echo "unknown version"))"
    fi
else
    log_warn "Redis configuration file not found at $REDIS_CONF"
    # Can't configure if file doesn't exist
    NEED_REDIS_CONFIG=false
fi

# Check GMT library configuration (symlink)
if ! sudo test -L "/lib/x86_64-linux-gnu/libgmt.so" || 
   ! sudo test -f "/lib/x86_64-linux-gnu/libgmt.so.6"; then
    log_warn "GMT library symlink not properly configured"
    NEED_GMT_CONFIG=true
else
    log_success "GMT library is properly configured ($(gmt --version 2>/dev/null || echo "unknown version"))"
fi

# Installation plan
if ! $NEED_SYSTEM_PKGS && ! $NEED_PYENV && ! $NEED_PYTHON312 && 
   ! $NEED_POETRY && ! $NEED_TTT_SDK && ! $NEED_TEXLIVE &&
   ! $NEED_REDIS_CONFIG && ! $NEED_GMT_CONFIG; then
    log_success "All components are already installed and configured!"
    exit 0
fi

log_info "Installation plan:"
$NEED_SYSTEM_PKGS && echo "- System packages will be installed/updated"
$NEED_PYENV && echo "- Pyenv will be installed"
$NEED_PYTHON312 && echo "- Python $REQUIRED_PYTHON_VERSION will be installed"
$NEED_POETRY && echo "- Poetry will be installed"
$NEED_TTT_SDK && echo "- TTT SDK will be installed"
$NEED_TEXLIVE && echo "- TeXLive will be installed"
$NEED_REDIS_CONFIG && echo "- Redis will be configured for systemd"
$NEED_GMT_CONFIG && echo "- GMT library symlink will be configured"

# Prompt to continue
read -p "Continue with installation? [Y/n] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ -n $REPLY ]]; then
    echo "Installation aborted."
    exit 1
fi

if $NEED_SYSTEM_PKGS; then
    log_info "Updating system packages"
    safe_exec sudo apt update -y
    safe_exec sudo apt upgrade -y

    if (( ${#missing_pkgs[@]} > 0 )); then
        log_info "Installing missing packages"
        safe_exec sudo apt install -y "${missing_pkgs[@]}"
    fi
fi

if $NEED_PYENV; then
    log_info "Installing Pyenv"
    safe_exec curl -fsSL https://pyenv.run | bash

    if [[ -d "$HOME/.pyenv" ]]; then
        export PYENV_ROOT="$HOME/.pyenv"
        export PATH="$PYENV_ROOT/bin:$PATH"

        # Detect if running under WSL
        if [[ -f /proc/sys/fs/binfmt_misc/WSLInterop ]]; then
            log_info "WSL environment detected"
            WSL_MODE=true
            PYENV_INIT_CMD="eval \"\$(pyenv init -)\""
        else
            log_info "Native Linux environment detected"
            WSL_MODE=false
            PYENV_INIT_CMD="eval \"\$(pyenv init - bash)\""
        fi
        if ! grep -q "PYENV_ROOT" "$HOME/.bashrc"; then
            log_info "Adding pyenv to PATH in bashrc"
            echo -e '\n# Pyenv configuration' >> "$HOME/.bashrc"
            echo 'export PYENV_ROOT="$HOME/.pyenv"' >> "$HOME/.bashrc"

            if $WSL_MODE; then
                echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> "$HOME/.bashrc"
                echo 'eval "$(pyenv init -)"' >> "$HOME/.bashrc"
            else
                echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> "$HOME/.bashrc"
                echo 'eval "$(pyenv init - bash)"' >> "$HOME/.bashrc"
            fi
        fi

        eval "$PYENV_INIT_CMD"
    else
        log_warn "Pyenv installation directory not found"
    fi
fi

if $NEED_PYTHON312 && (cmd_exists "pyenv" || $NEED_PYENV); then
    log_info "Installing Python $REQUIRED_PYTHON_VERSION using pyenv"
    safe_exec pyenv install -s $REQUIRED_PYTHON_VERSION
    safe_exec pyenv global $REQUIRED_PYTHON_VERSION
fi

if $NEED_POETRY; then
    log_info "Installing Poetry"
    safe_exec curl -sSL https://install.python-poetry.org | python3 -

    if [[ -d "$HOME/.local/bin" ]]; then
        export PATH="$HOME/.local/bin:$PATH"
        
        if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
            log_info "Adding poetry to PATH in bashrc"
            echo -e '\n# Poetry path' >> "$HOME/.bashrc"
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        fi
    fi
fi

if $NEED_TTT_SDK; then
    log_info "Installing TTT SDK"
    TMP_DIR=$(mktemp -d)
    safe_exec git clone -q https://gitlab.com/totallynotdavid/tttapi/ "$TMP_DIR/tttapi"
    
    if [[ -d "$TMP_DIR/tttapi" ]]; then
        (
            cd "$TMP_DIR/tttapi" || exit 1
            safe_exec make config compile >/dev/null 2>&1
            safe_exec sudo make install datadir docs >/dev/null 2>&1
            safe_exec make test clean >/dev/null 2>&1
        )
        rm -rf "$TMP_DIR"
    else
        log_warn "TTT SDK clone failed"
    fi
fi

if $NEED_TEXLIVE; then
    log_info "Installing TeXLive"
    TMP_TL=$(mktemp -d)
    pushd "$TMP_TL" > /dev/null || exit 1

    safe_exec wget -q https://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz
    safe_exec tar -xzf install-tl-unx.tar.gz

    INSTALL_TL_DIR=$(find . -maxdepth 1 -type d -name "install-tl-*" | head -1)

    if [[ -n "$INSTALL_TL_DIR" ]]; then
        cd "$INSTALL_TL_DIR" || exit 1

        echo -e "selected_scheme scheme-basic\ntlpdbopt_autobackup 0\ntlpdbopt_install_docfiles 0\ntlpdbopt_install_srcfiles 0" > texlive.profile

        TEXLIVE_INSTALL_DIR="$HOME/texlive"
        safe_exec perl ./install-tl \
            --profile=texlive.profile \
            --texdir="$TEXLIVE_INSTALL_DIR" \
            --texuserdir="$HOME/.texlive" \
            --no-interaction

        if [[ -d "$TEXLIVE_INSTALL_DIR/bin" ]]; then
            TEXLIVE_BIN_DIR=$(find "$TEXLIVE_INSTALL_DIR/bin" -type d -name "x86_64*" | head -1)

            if [[ -n "$TEXLIVE_BIN_DIR" ]]; then
                export PATH="$TEXLIVE_BIN_DIR:$PATH"
                
                if ! grep -q "texlive/bin" "$HOME/.bashrc"; then
                    echo -e '\n# TeXLive path\nexport PATH="'"$TEXLIVE_BIN_DIR"':\$PATH"' >> "$HOME/.bashrc"
                fi

                if command -v tlmgr >/dev/null 2>&1; then
                    safe_exec "$TEXLIVE_BIN_DIR/tlmgr" install babel-spanish hyphen-spanish booktabs --verify-repo=none --quiet
                fi
            fi
        fi
    fi

    popd >/dev/null || exit 1
    rm -rf "$TMP_TL"
fi

if $NEED_REDIS_CONFIG && sudo test -f "$REDIS_CONF"; then
    log_info "Configuring Redis for systemd"
    safe_exec sudo cp "$REDIS_CONF" "${REDIS_CONF}.bak"
    safe_exec sudo sed -i -E 's/^(# ?)?supervised .*/supervised systemd/' "$REDIS_CONF"
    safe_exec service --status-all
    safe_exec sudo systemctl restart redis-server
fi

if $NEED_GMT_CONFIG; then
    log_info "Setting up GMT library symlink"
    if sudo test -f "/lib/x86_64-linux-gnu/libgmt.so.6"; then
        safe_exec sudo ln -sf /lib/x86_64-linux-gnu/libgmt.so.6 /lib/x86_64-linux-gnu/libgmt.so
    else
        log_warn "GMT library file not found at /lib/x86_64-linux-gnu/libgmt.so.6"
    fi
fi

source "$HOME/.bashrc"

log_info "Verifying installation"

VERIFICATION_FAILED=false

# Verify only what was installed
if $NEED_SYSTEM_PKGS; then
    for pkg in "${missing_pkgs[@]}"; do
        if ! is_pkg_installed "$pkg"; then
            log_warn "Package $pkg failed to install"
            VERIFICATION_FAILED=true
        fi
    done
fi

if $NEED_PYENV; then
    if ! cmd_exists "pyenv"; then
        log_warn "Pyenv verification failed - command not available"
        VERIFICATION_FAILED=true
    fi
fi

if $NEED_PYTHON312; then
    if ! has_python_version "$REQUIRED_PYTHON_VERSION"; then
        log_warn "Python $REQUIRED_PYTHON_VERSION verification failed - not installed"
        VERIFICATION_FAILED=true
    fi
fi

if $NEED_POETRY; then
    if ! cmd_exists "poetry"; then
        log_warn "Poetry verification failed - command not available"
        VERIFICATION_FAILED=true
        echo "You may need to restart your terminal or run: 'source ~/.bashrc'"
    fi
fi

if $NEED_TTT_SDK; then
    if ! cmd_exists "ttt_client"; then
        log_warn "TTT SDK verification failed - command not available"
        VERIFICATION_FAILED=true
    fi
fi

if $NEED_TEXLIVE; then
    if ! path_exists "$HOME/texlive"; then
        log_warn "TeXLive verification failed - installation directory not found"
        VERIFICATION_FAILED=true
    elif ! cmd_exists "tex" && ! cmd_exists "pdflatex"; then
        log_warn "TeXLive verification failed - commands not available"
        echo "You may need to restart your terminal or run: 'source ~/.bashrc'"
        VERIFICATION_FAILED=true
    fi
fi

if $NEED_REDIS_CONFIG; then
    if sudo test -f "$REDIS_CONF" && ! sudo grep -q "^supervised systemd" "$REDIS_CONF"; then
        log_warn "Redis configuration verification failed"
        VERIFICATION_FAILED=true
    fi
fi

if $NEED_GMT_CONFIG; then
    if ! sudo test -L "/lib/x86_64-linux-gnu/libgmt.so"; then
        log_warn "GMT library symlink verification failed"
        VERIFICATION_FAILED=true
    fi
fi

if $VERIFICATION_FAILED; then
    log_warn "Some components may require additional configuration"
    echo "You may need to restart your terminal or run: 'source ~/.bashrc'"
else
    log_success "All installed components verified successfully"
fi
