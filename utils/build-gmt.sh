#!/bin/bash

set -e 

# Configuration variables
GMT_INSTALL_PREFIX="/opt/gmt"
BUILD_DIR="build"
PARALLEL_JOBS=$(nproc)

# Install dependencies
echo "Installing dependencies..."
sudo apt-get update
sudo apt-get install -y build-essential cmake libcurl4-gnutls-dev libnetcdf-dev libgdal-dev
sudo apt-get install -y ninja-build gdal-bin libfftw3-dev libpcre3-dev liblapack-dev \
                   libblas-dev libglib2.0-dev ghostscript graphicsmagick ffmpeg xdg-utils

# Download GMT source code
echo "Downloading GMT source code..."
if [ ! -d "gmt" ]; then
    git clone --depth 50 https://github.com/GenericMappingTools/gmt
else
    echo "GMT source already exists, updating..."
    cd gmt
    git pull
    cd ..
fi

# Configure and build
echo "Configuring and building GMT..."
cd gmt
mkdir -p $BUILD_DIR
cd $BUILD_DIR

# Configure with CMake
cmake .. -G Ninja \
    -DCMAKE_INSTALL_PREFIX=$GMT_INSTALL_PREFIX

# Build GMT
echo "Building GMT..."
cmake --build . --parallel $PARALLEL_JOBS

# Install GMT
echo "Installing GMT..."
sudo cmake --build . --target install

# Add GMT to PATH
echo "Adding GMT to PATH..."
echo "export PATH=\$PATH:$GMT_INSTALL_PREFIX/bin" | sudo tee /etc/profile.d/gmt.sh
sudo chmod +x /etc/profile.d/gmt.sh

echo "GMT build and installation completed successfully!"
echo "GMT is now installed at: $GMT_INSTALL_PREFIX"
echo "You can run GMT commands after restarting your terminal or running: source /etc/profile.d/gmt.sh"
