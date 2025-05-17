# Poly Slimmer

A web application for reducing polygon counts in 3D models (GLB, FBX, GLTF) for VRChat, game mods, and NFTs.

## Features

- Upload 3D models directly in your browser
- Preview model with reduced polygon count
- Safely reduce polygon count while preserving rigs and animations
- Two pricing plans: $4 for a single export or $25 for 30 days of unlimited exports

## Tech Stack

- **Backend**: FastAPI + Pydantic
- **Frontend**: HTMX + Tailwind CSS
- **Database**: SQLite (development) / PostgreSQL (production)
- **Task Queue**: ARQ (Redis-based queue)
- **Storage**: Backblaze B2 (production) / Local filesystem (development)
- **Payments**: Stripe
- **3D Processing**: gltfpack from meshoptimizer

## Installation

### Prerequisites

- Python 3.11+
- Redis (optional for development, required for production)
- gltfpack (from meshoptimizer)

### Setup

1. Clone the repository:

```bash
git clone https://github.com/yourusername/poly-slimmer.git
cd poly-slimmer
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Download gltfpack binary:

```bash
# Linux
wget -O /usr/local/bin/gltfpack https://github.com/zeux/meshoptimizer/releases/download/v0.20/gltfpack
chmod +x /usr/local/bin/gltfpack

# macOS (using Homebrew)
brew install meshoptimizer
```

4. Set up environment:

```bash
# Use the setup script
./scripts/setup_env.sh

# Or manually copy the sample environment file
cp .env.local .env
# Edit .env to set your configuration
```

5. Initialize the database:

```bash
python scripts/init_db.py
```

6. Generate the watermark image:

```bash
python scripts/create_watermark.py
```

## Running the Application

### Development

#### Minimal Setup (no Redis or B2)

This configuration uses local file storage and skips background processing.

1. Set up environment:
```bash
cp .env.local .env
# Make sure B2_KEY_ID and B2_KEY are empty
# Comment out REDIS_URL
```

2. Start the FastAPI application:
```bash
uvicorn app.main:app --reload
```

3. Open http://127.0.0.1:8000 in your browser

#### Full Development Setup

This setup uses Redis for background job processing.

1. Set up environment with Redis:
```bash
cp .env.local .env
# Make sure REDIS_URL is set to redis://localhost:6379
```

2. Start Redis:
```bash
redis-server
```

3. Start the FastAPI application:
```bash
uvicorn app.main:app --reload
```

4. Start the worker in a separate terminal:
```bash
python scripts/run_worker.py
```

5. Open http://127.0.0.1:8000 in your browser

### Production (using Docker)

1. Set up production environment:
```bash
cp .env.production .env
# Edit .env with your production settings
```

2. Build the Docker image:
```bash
docker build -t poly-slimmer -f docker/Dockerfile .
```

3. Run the container:
```bash
docker run -p 8080:8080 --env-file .env poly-slimmer
```

## Deployment

The app is designed to be deployed on Fly.io:

```bash
fly launch --name poly-slimmer --dockerfile docker/Dockerfile
fly secrets set STRIPE_API_KEY=your_stripe_key B2_KEY_ID=your_b2_key_id ...
fly volumes create data 1
```

## Troubleshooting

### "Processing..." message hangs after upload

This can happen for several reasons:
1. Redis is not running (if configured to use Redis)
2. The worker is not running
3. gltfpack is not installed or not in the specified path

For local development testing, you can:
1. Use the minimal setup without Redis
2. Check the application logs for errors
3. Verify your path to gltfpack is correct in .env

### File upload fails with 500 error

This is likely due to missing or invalid B2 storage configuration. For local development:
1. Make sure B2_KEY_ID and B2_KEY are empty in your .env file
2. Restart the application

## Architecture

The application uses a FastAPI backend with a task queue for handling optimization jobs. The frontend is built with HTMX and Tailwind CSS for a smooth user experience.

When a user uploads a model:
1. The model is stored temporarily in Backblaze B2 (or locally for development)
2. A preview is generated
3. The user can purchase a plan to download the optimized model
4. The optimization job is processed by a worker using gltfpack
5. The optimized model is available for download for 24 hours

## License

MIT License 