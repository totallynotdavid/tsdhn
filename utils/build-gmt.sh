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

# Add GMT to PATH in .bashrc
echo "Adding GMT to PATH in .bashrc..."
if grep -q "PATH=.*$GMT_INSTALL_PREFIX/bin" ~/.bashrc; then
    echo "Path already exists in .bashrc"
else
    echo "# GMT Path" >> ~/.bashrc
    echo "export PATH=\$PATH:$GMT_INSTALL_PREFIX/bin" >> ~/.bashrc
    echo "GMT path added to ~/.bashrc"
fi

source ~/.bashrc

echo "GMT build and installation completed successfully!"
echo "GMT is now installed at: $GMT_INSTALL_PREFIX"
echo "GMT has been added to your PATH in ~/.bashrc"
echo "You can now use GMT commands directly in this terminal session."
