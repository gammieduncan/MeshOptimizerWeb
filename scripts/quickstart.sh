#!/bin/bash
# Quick start script for Poly Slimmer
# This script sets up and runs the application in development mode

# Text colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Poly Slimmer Quick Start${NC}"
echo -e "${BLUE}========================================${NC}"

# Check Python version - fixed comparison
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)

if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 9 ]]; then
    echo -e "${RED}Error: Python 3.9+ is required. You have $PYTHON_VERSION${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $PYTHON_VERSION detected${NC}"

# Check for virtual environment
if [ -d "venv" ]; then
    echo "Virtual environment already exists. Activating..."
    source venv/bin/activate || source venv/Scripts/activate
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate || source venv/Scripts/activate
fi
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Check if Redis is installed
echo "Checking for Redis..."
REDIS_SERVER_CMD=$(which redis-server || echo "")
BREW_CMD=$(which brew || echo "")

if [ -z "$REDIS_SERVER_CMD" ]; then
    echo -e "${YELLOW}Redis server not found in PATH${NC}"
    
    if [ ! -z "$BREW_CMD" ]; then
        echo "Installing Redis using Homebrew..."
        brew install redis
        REDIS_SERVER_CMD=$(which redis-server)
        if [ -z "$REDIS_SERVER_CMD" ]; then
            echo -e "${RED}Failed to install Redis. Please install it manually.${NC}"
        else
            echo -e "${GREEN}✓ Redis installed successfully${NC}"
        fi
    else
        echo -e "${YELLOW}Homebrew not found. Please install Redis manually.${NC}"
    fi
else
    echo -e "${GREEN}✓ Redis found at $REDIS_SERVER_CMD${NC}"
fi

# Check if Redis is running
REDIS_RUNNING=0
if [ ! -z "$REDIS_SERVER_CMD" ]; then
    echo "Checking if Redis is running..."
    if pgrep -x "redis-server" > /dev/null; then
        echo -e "${GREEN}✓ Redis is already running${NC}"
        REDIS_RUNNING=1
    else
        echo "Starting Redis server..."
        # Start Redis in the background
        redis-server --daemonize yes
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Redis server started${NC}"
            REDIS_RUNNING=1
        else
            echo -e "${RED}Failed to start Redis server. Job queue processing won't work.${NC}"
        fi
    fi
fi

# Check if gltfpack is installed
GLTFPACK_PATH=$(which gltfpack || echo "")
if [ -z "$GLTFPACK_PATH" ]; then
    echo -e "${YELLOW}Warning: gltfpack not found in PATH${NC}"
    echo "You'll need to install gltfpack for the optimization to work:"
    echo "  - MacOS: brew install meshoptimizer"
    echo "  - Linux: Download from https://github.com/zeux/meshoptimizer/releases"
    echo "Once installed, update your .env file with the correct path."
    GLTFPACK_PATH="/usr/local/bin/gltfpack"  # Default path
else
    echo -e "${GREEN}✓ gltfpack found at $GLTFPACK_PATH${NC}"
fi

# Set up environment file
if [ ! -f ".env" ]; then
    echo "Setting up environment file..."
    cp .env.local .env
    
    # Update gltfpack path
    sed -i.bak "s|GLTFPACK_PATH=.*|GLTFPACK_PATH=$GLTFPACK_PATH|" .env
    rm -f .env.bak
    
    # Make sure REDIS_URL is set correctly
    if [ $REDIS_RUNNING -eq 1 ]; then
        # Uncomment Redis URL if needed
        sed -i.bak "s|#REDIS_URL=redis://localhost:6379|REDIS_URL=redis://localhost:6379|" .env
        rm -f .env.bak
    fi
    
    echo -e "${GREEN}✓ Environment file created${NC}"
else
    echo -e "${YELLOW}Note: Using existing .env file${NC}"
fi

# Initialize database
echo "Initializing database..."
python scripts/init_db.py
echo -e "${GREEN}✓ Database initialized${NC}"

# Create watermark
echo "Creating watermark image..."
python scripts/create_watermark.py
echo -e "${GREEN}✓ Watermark created${NC}"

# Create test job
echo "Creating a test job..."
python scripts/test_mock_job.py
echo -e "${GREEN}✓ Test job created${NC}"

# Start the worker if Redis is running
if [ $REDIS_RUNNING -eq 1 ]; then
    echo "Starting ARQ worker in background..."
    # Start worker in the background
    python scripts/run_worker.py > worker.log 2>&1 &
    WORKER_PID=$!
    echo -e "${GREEN}✓ Worker started with PID $WORKER_PID${NC}"
    echo "  Worker logs: worker.log"
    
    # Function to handle exit and cleanup
    function cleanup {
        echo "Stopping worker..."
        kill $WORKER_PID 2>/dev/null
        
        # Stop Redis if we started it
        echo "Stopping Redis..."
        redis-cli shutdown
        
        echo "Cleanup complete."
    }
    
    # Register cleanup function for SIGINT (Ctrl+C)
    trap cleanup EXIT
else
    echo -e "${YELLOW}Skipping worker start as Redis is not running${NC}"
    echo "Jobs will be marked as completed automatically in local development mode."
fi

# Start application
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Setup complete! Starting application...${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Visit http://127.0.0.1:8000 in your browser${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Start the application
uvicorn app.main:app --reload 