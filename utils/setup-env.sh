#!/bin/bash
set -eo pipefail

# ===== Utility Functions =====

log_info() { echo -e "\n■ $1"; }
log_success() { echo -e "✓ $1"; }
log_warn() { echo -e "◇ $1"; }
log_error() { echo -e "✖ $1"; }

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
    local cmd_desc="$1"
    shift

    log_info "Executing: $cmd_desc"
    if ! "$@"; then
        log_error "Command failed: $*"
        return 1
    fi
    log_success "$cmd_desc completed"
    return 0
}

add_to_bashrc() {
    local section="$1"
    local line="$2"

    if ! grep -q "$line" "$HOME/.bashrc"; then
        if ! grep -q "# $section" "$HOME/.bashrc"; then
            echo -e "\n# $section" >> "$HOME/.bashrc"
        fi
        echo "$line" >> "$HOME/.bashrc"
        return 0
    fi
    return 1  # Already exists
}

has_python_version() {
    local required_version="$1"

    # Check if python3 is the required version
    if cmd_exists "python3"; then
        local py_version
        py_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
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

has_ifx_installed() {
    if cmd_exists "ifx"; then
        return 0
    fi

    # Check if it's installed but not in PATH
    if [[ -f "$HOME/intel/oneapi/setvars.sh" ]]; then
        # Check if sourcing setvars.sh would give us ifx
        local tmp_script
        tmp_script=$(mktemp)

        # Create a temporary script to test this
        cat > "$tmp_script" << 'EOF'
#!/bin/bash
source "$HOME/intel/oneapi/setvars.sh" &>/dev/null
command -v ifx &>/dev/null
exit $?
EOF
        chmod +x "$tmp_script"

        if "$tmp_script"; then
            rm "$tmp_script"
            return 0
        fi
        rm "$tmp_script"
    fi

    return 1  # ifx is not installed
}

check_gmt_version() {
    local min_version="$1"

    if ! cmd_exists "gmt"; then
        return 1
    fi

    local current_version
    current_version=$(gmt --version 2>/dev/null | cut -d' ' -f3)
    
    if [[ $(echo -e "$current_version\n$min_version" | sort -V | head -n1) == "$min_version" ]] || 
       [[ "$current_version" == "$min_version" ]]; then
        # Current version is greater than or equal to min_version
        return 0
    else
        # Current version is less than min_version
        return 1
    fi
}

# ===== System Status Check =====
log_info "Checking system status\n"

REQUIRED_PKGS=(
    # Required for building Python with pyenv
    build-essential zlib1g-dev libffi-dev libssl-dev libbz2-dev
    libreadline-dev libsqlite3-dev liblzma-dev libncurses-dev tk-dev

    # Required for TTT SDK
    git-lfs 

    # Used to build GMT
    cmake ninja-build

    # GMT build deps (https://github.com/GenericMappingTools/gmt/wiki/Install-dependencies-on-Ubuntu-and-Debian)
    libcurl4-gnutls-dev libnetcdf-dev libgdal-dev gdal-bin \
    libfftw3-dev libpcre3-dev libpcre3-dev liblapack-dev libblas-dev \
    libglib2.0-dev ghostscript graphicsmagick ffmpeg

    # Other dependencies
    redis-server ps2eps csh
)

NEED_SYSTEM_PKGS=false
NEED_PYENV=false
NEED_PYTHON312=false
NEED_POETRY=false
NEED_TTT_SDK=false
NEED_TEXLIVE=false
NEED_REDIS_CONFIG=false
NEED_GMT_BUILD=false
NEED_IFX=false

REQUIRED_PYTHON_VERSION="3.12"
GMT_MIN_VERSION="6.5.0"

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
    log_success "All required system packages are installed"
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

# Check GMT version
if check_gmt_version "$GMT_MIN_VERSION"; then
    log_success "GMT $(gmt --version 2>/dev/null | cut -d' ' -f3) is installed and meets minimum version requirements"
else
    if cmd_exists "gmt"; then
        log_warn "GMT $(gmt --version 2>/dev/null | cut -d' ' -f3) is installed but does not meet minimum version requirement ($GMT_MIN_VERSION)"
    else
        log_warn "GMT command not found"
    fi
    NEED_GMT_BUILD=true
fi

if has_ifx_installed; then
    if cmd_exists "ifx"; then
        log_success "Intel® Fortran Essentials is available ($(
            ifx --version 2>/dev/null \
                | head -n1 \
                | awk '{print $3}' \
                || echo unknown
        ))"
    else
        log_success "Intel® Fortran Essentials is installed but not in PATH"
        SETVARS="$HOME/intel/oneapi/setvars.sh"
        if [[ -f "$SETVARS" ]] && ! grep -q "intel/oneapi/setvars.sh" "$HOME/.bashrc"; then
            log_info "Adding Intel OneAPI environment to bashrc"
            add_to_bashrc "Intel OneAPI environment" '[ -f "$HOME/intel/oneapi/setvars.sh" ] && source "$HOME/intel/oneapi/setvars.sh" > /dev/null'
            source "$SETVARS" > /dev/null 2>&1 || true
            log_success "Intel® Fortran Essentials is available ($(ifx --version 2>/dev/null | head -n 1 || echo "unknown version"))"
        fi
    fi
else
    log_warn "Intel® Fortran Essentials not installed"
    NEED_IFX=true
fi

# ===== Installation Plan =====
if ! $NEED_SYSTEM_PKGS && ! $NEED_PYENV && ! $NEED_PYTHON312 &&
   ! $NEED_POETRY && ! $NEED_TTT_SDK && ! $NEED_TEXLIVE &&
   ! $NEED_REDIS_CONFIG && ! $NEED_GMT_BUILD && ! $NEED_IFX; then
    log_success "All components are already installed and configured!"
    exit 0
fi

log_info "Installation plan:\n"
$NEED_SYSTEM_PKGS && echo "- System packages will be installed/updated"
$NEED_PYENV && echo "- Pyenv will be installed"
$NEED_PYTHON312 && echo "- Python $REQUIRED_PYTHON_VERSION will be installed"
$NEED_POETRY && echo "- Poetry will be installed"
$NEED_TTT_SDK && echo "- TTT SDK will be installed"
$NEED_TEXLIVE && echo "- TeXLive will be installed"
$NEED_REDIS_CONFIG && echo "- Redis will be configured for systemd"
$NEED_GMT_BUILD && echo "- GMT will be built from source (version $GMT_MIN_VERSION or newer)"
$NEED_IFX && echo "- Intel Fortran Essentials (ifx) will be installed"

# Prompt to continue
echo "" # Add a space between the installation plan and the question for better readability
read -p "Continue with installation? [Y/n] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ -n $REPLY ]]; then
    log_info "Installation aborted."
    exit 1
fi

# ===== Installation Process =====

if $NEED_SYSTEM_PKGS; then
    log_info "Updating system packages"
    safe_exec "APT update" sudo apt update -y
    safe_exec "APT upgrade" sudo apt upgrade -y

    if (( ${#missing_pkgs[@]} > 0 )); then
        log_info "Installing missing packages"
        safe_exec "Installing required packages" sudo apt install -y "${missing_pkgs[@]}"
    fi
fi

if $NEED_PYENV; then
    log_info "Installing Pyenv"
    safe_exec "Downloading and running pyenv installer" curl -fsSL https://pyenv.run | bash

    if [[ -d "$HOME/.pyenv" ]]; then
        export PYENV_ROOT="$HOME/.pyenv"
        export PATH="$PYENV_ROOT/bin:$PATH"

        # Detect if running under WSL because:
        # WSL appends Windows path to the PATH variable,
        # which can cause issues with pyenv if pyenv is
        # installed in both Windows and WSL
        if [[ -f /proc/sys/fs/binfmt_misc/WSLInterop ]]; then
            log_info "WSL environment detected"
            WSL_MODE=true
            PYENV_INIT_CMD='eval "$(pyenv init -)"'
        else
            log_info "Native Linux environment detected"
            WSL_MODE=false
            PYENV_INIT_CMD='eval "$(pyenv init - bash)"'
        fi
        
        # Add pyenv to bashrc
        add_to_bashrc "Pyenv configuration" 'export PYENV_ROOT="$HOME/.pyenv"'
        
        if $WSL_MODE; then
            add_to_bashrc "Pyenv configuration" 'export PATH="$PYENV_ROOT/bin:$PATH"'
            add_to_bashrc "Pyenv configuration" 'eval "$(pyenv init -)"'
        else
            add_to_bashrc "Pyenv configuration" '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"'
            add_to_bashrc "Pyenv configuration" 'eval "$(pyenv init - bash)"'
        fi

        eval "$PYENV_INIT_CMD"
    else
        log_warn "Pyenv installation directory not found"
    fi
fi

if $NEED_PYTHON312 && (cmd_exists "pyenv" || $NEED_PYENV); then
    log_info "Installing Python $REQUIRED_PYTHON_VERSION using pyenv"
    safe_exec "Installing Python $REQUIRED_PYTHON_VERSION" pyenv install -s "$REQUIRED_PYTHON_VERSION"
    safe_exec "Setting Python $REQUIRED_PYTHON_VERSION as global" pyenv global "$REQUIRED_PYTHON_VERSION"
fi

if $NEED_POETRY; then
    log_info "Installing Poetry"
    TMP_INSTALLER=$(mktemp)
    safe_exec "Downloading Poetry installer" curl -sSL https://install.python-poetry.org -o "$TMP_INSTALLER"
    safe_exec "Running Poetry installer" python3 "$TMP_INSTALLER"
    rm "$TMP_INSTALLER"

    if [[ -d "$HOME/.local/bin" ]]; then
        export PATH="$HOME/.local/bin:$PATH"
        add_to_bashrc "Poetry path" 'export PATH="$HOME/.local/bin:$PATH"'
    fi
fi

if $NEED_TTT_SDK; then
    log_info "Installing TTT SDK"
    TMP_DIR=$(mktemp -d)
    safe_exec "Cloning TTT SDK repository" git clone -q https://gitlab.com/totallynotdavid/tttapi/ "$TMP_DIR/tttapi"

    if [[ -d "$TMP_DIR/tttapi" ]]; then
        (
            cd "$TMP_DIR/tttapi" || exit 1
            safe_exec "Configuring and compiling TTT SDK" make config compile >/dev/null 2>&1
            safe_exec "Installing TTT SDK" sudo make install datadir docs >/dev/null 2>&1
            safe_exec "Testing and cleaning TTT SDK" make test clean >/dev/null 2>&1
        )
        rm -rf "$TMP_DIR"
    else
        log_error "TTT SDK clone failed"
    fi
fi

if $NEED_TEXLIVE; then
    log_info "Installing TeXLive"
    TMP_TL=$(mktemp -d)
    pushd "$TMP_TL" > /dev/null || exit 1

    safe_exec "Downloading TeXLive installer" wget -q https://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz
    safe_exec "Extracting TeXLive installer" tar -xzf install-tl-unx.tar.gz

    INSTALL_TL_DIR=$(find . -maxdepth 1 -type d -name "install-tl-*" | head -1)

    if [[ -n "$INSTALL_TL_DIR" ]]; then
        cd "$INSTALL_TL_DIR" || exit 1

        # Create profile for non-interactive installation
        cat > texlive.profile << EOF
selected_scheme scheme-basic
tlpdbopt_autobackup 0
tlpdbopt_install_docfiles 0
tlpdbopt_install_srcfiles 0
EOF

        TEXLIVE_INSTALL_DIR="$HOME/texlive"
        safe_exec "Installing TeXLive" perl ./install-tl \
            --profile=texlive.profile \
            --texdir="$TEXLIVE_INSTALL_DIR" \
            --texuserdir="$HOME/.texlive" \
            --no-interaction

        if [[ -d "$TEXLIVE_INSTALL_DIR/bin" ]]; then
            TEXLIVE_BIN_DIR=$(find "$TEXLIVE_INSTALL_DIR/bin" -type d -name "x86_64*" | head -1)

            if [[ -n "$TEXLIVE_BIN_DIR" ]]; then
                export PATH="$TEXLIVE_BIN_DIR:$PATH"
                add_to_bashrc "TeXLive path" "export PATH=\"$TEXLIVE_BIN_DIR:\$PATH\""

                if command -v tlmgr >/dev/null 2>&1; then
                    safe_exec "Installing additional TeXLive packages" "$TEXLIVE_BIN_DIR/tlmgr" install babel-spanish hyphen-spanish booktabs --verify-repo=none
                fi
            fi
        fi
    fi

    popd >/dev/null || exit 1
    rm -rf "$TMP_TL"
fi

if $NEED_REDIS_CONFIG && sudo test -f "$REDIS_CONF"; then
    log_info "Configuring Redis for systemd"
    safe_exec "Backing up Redis config" sudo cp "$REDIS_CONF" "${REDIS_CONF}.bak"
    safe_exec "Updating Redis config" sudo sed -i -E 's/^(# ?)?supervised .*/supervised systemd/' "$REDIS_CONF"
    safe_exec "Checking system services" service --status-all
    safe_exec "Restarting Redis server" sudo systemctl restart redis-server
fi

if $NEED_GMT_BUILD; then
    log_info "Building GMT from source"

    GMT_BUILD_DIR=$(mktemp -d)
    pushd "$GMT_BUILD_DIR" > /dev/null || exit 1

    safe_exec "Cloning GMT repository" git clone --depth 50 https://github.com/GenericMappingTools/gmt.git

    # Get support data
    safe_exec "Downloading GSHHG data" wget https://github.com/GenericMappingTools/gshhg-gmt/releases/download/2.3.7/gshhg-gmt-2.3.7.tar.gz
    safe_exec "Extracting GSHHG data" tar xzf gshhg-gmt-2.3.7.tar.gz

    safe_exec "Downloading DCW data" wget https://github.com/GenericMappingTools/dcw-gmt/releases/download/2.2.0/dcw-gmt-2.2.0.tar.gz
    safe_exec "Extracting DCW data" tar xzf dcw-gmt-2.2.0.tar.gz

    cat > gmt/cmake/ConfigUser.cmake << EOF
set (CMAKE_INSTALL_PREFIX "/usr/local")
set (GSHHG_ROOT "${GMT_BUILD_DIR}/gshhg-gmt-2.3.7")
set (DCW_ROOT "${GMT_BUILD_DIR}/dcw-gmt-2.2.0")
EOF

    mkdir -p gmt/build
    cd gmt/build || exit 1

    safe_exec "Configuring GMT build" cmake .. -G Ninja

    safe_exec "Building GMT" cmake --build .
    safe_exec "Installing GMT" sudo cmake --build . --target install
    safe_exec "Running ldconfig" sudo ldconfig

    popd > /dev/null || exit 1
    rm -rf "$GMT_BUILD_DIR"

    if command -v gmt >/dev/null; then
        GMT_VERSION=$(gmt --version 2>/dev/null | cut -d' ' -f3)
        log_success "GMT $GMT_VERSION installed successfully"
    else
        log_error "GMT installation failed - command not found"
    fi
fi

if $NEED_IFX; then
    log_info "Installing Intel® Fortran Essentials (ifx)"

    INSTALLER_URL="https://registrationcenter-download.intel.com/akdlm/IRC_NAS/306e03be-1259-4d71-848a-59e23013c4f0/intel-fortran-essentials-2025.1.0.556_offline.sh"
    INSTALLER="${INSTALLER_URL##*/}"
    WORKDIR="${TMPDIR:-/tmp}/ifx-install-$$"

    safe_exec "Creating temporary directory" mkdir -p "$WORKDIR"
    pushd "$WORKDIR" > /dev/null || exit 1

    if [[ ! -f "$INSTALLER" ]]; then
        log_info "Downloading Intel Fortran Essentials installer... (this may take a while as the file weighs about 950MB)"
        safe_exec "Downloading Intel Fortran installer" wget -q --show-progress "$INSTALLER_URL"
    else
        log_info "Installer already downloaded: $INSTALLER"
    fi

    safe_exec "Making installer executable" chmod +x "$INSTALLER"

    log_info "Running silent install (user-local)..."
    safe_exec "Installing Intel Fortran" sh "./$INSTALLER" -a --silent --eula accept

    SETVARS="$HOME/intel/oneapi/setvars.sh"
    if [[ -f "$SETVARS" ]]; then
        log_success "Intel Fortran installed successfully"
        add_to_bashrc "Intel OneAPI environment" '[ -f "$HOME/intel/oneapi/setvars.sh" ] && source "$HOME/intel/oneapi/setvars.sh" > /dev/null'
        
        source "$SETVARS" > /dev/null 2>&1 || true
    else
        log_error "Intel Fortran installation may have failed - setvars.sh not found"
    fi

    popd > /dev/null || exit 1
    rm -rf "$WORKDIR"
fi

source "$HOME/.bashrc" 2>/dev/null || true

# ===== Installation Verification =====
log_info "Verifying installation"

VERIFICATION_FAILED=false

# Verify only what was installed
if $NEED_SYSTEM_PKGS; then
    for pkg in "${missing_pkgs[@]}"; do
        if ! is_pkg_installed "$pkg"; then
            log_error "Package $pkg failed to install"
            VERIFICATION_FAILED=true
        fi
    done
fi

if $NEED_PYENV; then
    if ! cmd_exists "pyenv"; then
        log_error "Pyenv verification failed - command not available"
        VERIFICATION_FAILED=true
    fi
fi

if $NEED_PYTHON312; then
    if ! has_python_version "$REQUIRED_PYTHON_VERSION"; then
        log_error "Python $REQUIRED_PYTHON_VERSION verification failed - not installed"
        VERIFICATION_FAILED=true
    fi
fi

if $NEED_POETRY; then
    if ! cmd_exists "poetry"; then
        log_error "Poetry verification failed - command not available"
        VERIFICATION_FAILED=true
        echo "You may need to restart your terminal or run: 'source ~/.bashrc'"
    fi
fi

if $NEED_TTT_SDK; then
    if ! cmd_exists "ttt_client"; then
        log_error "TTT SDK verification failed - command not available"
        VERIFICATION_FAILED=true
    fi
fi

if $NEED_TEXLIVE; then
    if ! path_exists "$HOME/texlive"; then
        log_error "TeXLive verification failed - installation directory not found"
        VERIFICATION_FAILED=true
    elif ! cmd_exists "tex" && ! cmd_exists "pdflatex"; then
        log_error "TeXLive verification failed - commands not available"
        echo "You may need to restart your terminal or run: 'source ~/.bashrc'"
        VERIFICATION_FAILED=true
    fi
fi

if $NEED_REDIS_CONFIG; then
    if sudo test -f "$REDIS_CONF" && ! sudo grep -q "^supervised systemd" "$REDIS_CONF"; then
        log_error "Redis configuration verification failed"
        VERIFICATION_FAILED=true
    fi
fi

if $NEED_GMT_BUILD; then
    if ! cmd_exists "gmt"; then
        log_error "GMT verification failed - command not available"
        VERIFICATION_FAILED=true
    elif ! check_gmt_version "$GMT_MIN_VERSION"; then
        log_error "GMT verification failed - version $(gmt --version 2>/dev/null | cut -d' ' -f3) does not meet minimum requirement ($GMT_MIN_VERSION)"
        VERIFICATION_FAILED=true
    fi
fi

if $NEED_IFX; then
    if ! has_ifx_installed; then
        log_error "Intel Fortran Essentials verification failed - not installed"
        VERIFICATION_FAILED=true
        echo "You may need to restart your terminal or run: 'source ~/.bashrc'"
    fi
fi

# Final status report
if $VERIFICATION_FAILED; then
    log_warn "Some components may require additional configuration"
    echo "You may need to restart your terminal or run: 'source ~/.bashrc'"
else
    log_success "All installed components verified successfully"
    echo "You might need to restart your terminal for all changes to take effect"
fi
