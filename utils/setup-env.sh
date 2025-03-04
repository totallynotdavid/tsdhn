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

if ! cmd_exists "pyenv"; then
    log_warn "pyenv command not found"
    NEED_PYENV=true
else
    log_success "pyenv is available ($(pyenv --version 2>/dev/null || echo "unknown version"))"
fi

if cmd_exists "pyenv"; then
    PYENV_VERSION_OUTPUT=$(pyenv versions 2>/dev/null)
    
    if ! echo "$PYENV_VERSION_OUTPUT" | grep -q "3\.12"; then
        log_warn "Python 3.12.x not found in pyenv"
        NEED_PYTHON312=true
    else
        PYTHON312_VERSION=$(echo "$PYENV_VERSION_OUTPUT" | grep "3\.12" | 
                           sed -E 's/^[[:space:]]*\*?[[:space:]]*([3]\.12[0-9.]*).*/\1/' | 
                           head -1)
        log_success "Python ${PYTHON312_VERSION} is installed via pyenv"
    fi
else
    log_warn "Cannot check Python versions - pyenv not available"
    NEED_PYTHON312=true
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
    # Additional check to ensure it's working
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
$NEED_PYTHON312 && echo "- Python 3.12 will be installed"
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

# Update system packages if needed
if $NEED_SYSTEM_PKGS; then
    log_info "Updating system packages"
    safe_exec sudo apt update -y
    safe_exec sudo apt upgrade -y
    
    if (( ${#missing_pkgs[@]} > 0 )); then
        log_info "Installing missing packages"
        safe_exec sudo apt install -y "${missing_pkgs[@]}"
    fi
fi

# Install Pyenv if needed
if $NEED_PYENV; then
    log_info "Installing Pyenv"
    safe_exec curl -fsSL https://pyenv.run | bash
    
    # Set up path for current session
    if [[ -d "$HOME/.pyenv/bin" ]]; then
        export PYENV_ROOT="$HOME/.pyenv"
        export PATH="$PYENV_ROOT/bin:$PATH"
        
        # Add to bashrc only if not already working
        if ! grep -q "PYENV_ROOT" "$HOME/.bashrc"; then
            log_info "Adding pyenv to PATH in bashrc"
            echo -e '\n# Pyenv configuration' >> "$HOME/.bashrc"
            echo 'export PYENV_ROOT="$HOME/.pyenv"' >> "$HOME/.bashrc"
            echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> "$HOME/.bashrc"
            echo 'eval "$(pyenv init -)"' >> "$HOME/.bashrc"
        fi

        # Initialize for current session
        eval "$(pyenv init -)"
    else
        log_warn "Pyenv installation directory not found"
    fi
fi

# Install Python if needed
if $NEED_PYTHON312 && cmd_exists "pyenv"; then
    log_info "Installing Python 3.12"
    safe_exec pyenv install -s 3.12
    safe_exec pyenv global 3.12
fi

# Install Poetry if needed
if $NEED_POETRY; then
    log_info "Installing Poetry"
    safe_exec curl -sSL https://install.python-poetry.org | python3 -
    
    # Add to PATH for current session
    if [[ -d "$HOME/.local/bin" ]]; then
        export PATH="$HOME/.local/bin:$PATH"
        
        # Add to bashrc only if not already in PATH
        if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
            log_info "Adding poetry to PATH in bashrc"
            echo -e '\n# Poetry path' >> "$HOME/.bashrc"
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        fi
    fi
fi

# Install TTT SDK if needed
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

# Install TeXLive if needed
if $NEED_TEXLIVE; then
    log_info "Installing TeXLive"
    TMP_TL=$(mktemp -d)
    pushd "$TMP_TL" > /dev/null || exit 1
    
    safe_exec wget -q https://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz
    safe_exec tar -xzf install-tl-unx.tar.gz
    
    if [[ -d "$TMP_TL/install-tl-"* ]]; then
        cd install-tl-* || exit 1
        cat > texlive.profile <<EOF
selected_scheme scheme-basic
tlpdbopt_autobackup 0
tlpdbopt_install_docfiles 0
tlpdbopt_install_srcfiles 0
EOF
        safe_exec perl ./install-tl \
            --profile=texlive.profile \
            --texdir="$HOME/texlive" \
            --texuserdir="$HOME/.texlive" \
            --no-interaction
            
        if [[ -d "$HOME/texlive/bin" ]]; then
            # Find the actual binary directory
            TEXLIVE_BIN_DIR=$(find "$HOME/texlive/bin" -type d -name "x86_64*" | head -1)
            
            if [[ -n "$TEXLIVE_BIN_DIR" ]]; then
                # Add to path for current session
                export PATH="$TEXLIVE_BIN_DIR:$PATH"
                
                # Add to bashrc if not already there
                if ! grep -q "texlive/bin" "$HOME/.bashrc"; then
                    log_info "Adding TeXLive to PATH in bashrc"
                    echo -e '\n# TeXLive path' >> "$HOME/.bashrc"
                    echo "export PATH=\"$TEXLIVE_BIN_DIR:\$PATH\"" >> "$HOME/.bashrc"
                fi
                
                # Install additional packages
                if cmd_exists "tlmgr"; then
                    safe_exec tlmgr install babel-spanish hyphen-spanish booktabs --verify-repo=none --quiet
                fi
            fi
        fi
    fi
    
    popd >/dev/null || exit 1
    rm -rf "$TMP_TL"
fi

# Configure Redis if needed
if $NEED_REDIS_CONFIG && sudo test -f "$REDIS_CONF"; then
    log_info "Configuring Redis for systemd"
    safe_exec sudo cp "$REDIS_CONF" "${REDIS_CONF}.bak"
    safe_exec sudo sed -i -E 's/^(# ?)?supervised .*/supervised systemd/' "$REDIS_CONF"
    safe_exec sudo systemctl restart redis-server
fi

# Configure GMT library if needed
if $NEED_GMT_CONFIG; then
    log_info "Setting up GMT library symlink"
    if sudo test -f "/lib/x86_64-linux-gnu/libgmt.so.6"; then
        safe_exec sudo ln -sf /lib/x86_64-linux-gnu/libgmt.so.6 /lib/x86_64-linux-gnu/libgmt.so
    else
        log_warn "GMT library file not found at /lib/x86_64-linux-gnu/libgmt.so.6"
    fi
fi

# Final verification after installation
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

if $NEED_PYTHON312 && cmd_exists "pyenv"; then
    if ! pyenv versions 2>/dev/null | grep -q "3\.12"; then
        log_warn "Python 3.12 verification failed - not installed with pyenv"
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
