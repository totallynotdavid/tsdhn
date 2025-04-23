#!/usr/bin/env bash
set -euo pipefail

# It is better to run this script as a non-root user
if [[ $EUID -eq 0 ]]; then
  echo "❌ This script is for user installs only. Do not run it with sudo."
  exit 1
fi

INSTALLER_URL="https://registrationcenter-download.intel.com/akdlm/IRC_NAS/306e03be-1259-4d71-848a-59e23013c4f0/intel-fortran-essentials-2025.1.0.556_offline.sh"
INSTALLER="${INSTALLER_URL##*/}"
WORKDIR="${TMPDIR:-/tmp}/ifx-install-$$"

echo "Creating work directory: $WORKDIR"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

if [[ ! -f "$INSTALLER" ]]; then
  echo "Downloading Intel Fortran Essentials installer... (this may take a while as the file weight about 950mb)"
  wget -q --show-progress "$INSTALLER_URL"
else
  echo "Installer already downloaded: $INSTALLER"
fi

chmod +x "$INSTALLER"

# installing to ~/intel/oneapi
echo "Running silent install (user-local)..."
sh "./$INSTALLER" -a --silent --eula accept

SETVARS="$HOME/intel/oneapi/setvars.sh"
source "$SETVARS"

echo "Cleaning up..."
rm -rf "$WORKDIR"

echo "✅ Intel Fortran Essentials has been installed to ~/intel/oneapi. Run 'ifx --version' to check the installation."
