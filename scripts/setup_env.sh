#!/bin/bash
# Script to set up environment files for different environments

# Determine OS for gltfpack path
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    DEFAULT_GLTFPACK_PATH=$(which gltfpack || echo "/usr/local/bin/gltfpack")
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    DEFAULT_GLTFPACK_PATH=$(which gltfpack || echo "/usr/local/bin/gltfpack")
else
    # Windows or other
    DEFAULT_GLTFPACK_PATH="C:\\path\\to\\gltfpack.exe"
fi

# Function to set up local environment
setup_local() {
    echo "Setting up local development environment..."
    if [ -f .env ]; then
        echo ".env file already exists. Do you want to overwrite it? (y/n)"
        read -r overwrite
        if [[ ! $overwrite =~ ^[Yy]$ ]]; then
            echo "Keeping existing .env file."
            return
        fi
    fi
    
    cp .env.local .env
    
    # Update gltfpack path
    sed -i.bak "s|GLTFPACK_PATH=.*|GLTFPACK_PATH=$DEFAULT_GLTFPACK_PATH|" .env
    rm -f .env.bak
    
    echo "Local environment set up successfully."
    echo "Edit .env file to customize your settings if needed."
}

# Function to set up production environment
setup_production() {
    echo "Setting up production environment template..."
    if [ -f .env ]; then
        echo ".env file already exists. Do you want to overwrite it? (y/n)"
        read -r overwrite
        if [[ ! $overwrite =~ ^[Yy]$ ]]; then
            echo "Keeping existing .env file."
            return
        fi
    fi
    
    cp .env.production .env
    
    # Generate a random JWT secret
    JWT_SECRET=$(openssl rand -hex 32)
    sed -i.bak "s|JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" .env
    rm -f .env.bak
    
    echo "Production environment template set up successfully."
    echo "Edit .env file to fill in your production settings."
}

# Main menu
echo "Poly Slimmer Environment Setup"
echo "-----------------------------"
echo "1) Set up local development environment"
echo "2) Set up production environment template"
echo "q) Quit"
echo ""
echo -n "Please choose an option: "
read -r option

case $option in
    1) setup_local ;;
    2) setup_production ;;
    q|Q) echo "Exiting..." ;;
    *) echo "Invalid option" ;;
esac

echo "Done." 