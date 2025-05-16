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
- **Storage**: Backblaze B2
- **Payments**: Stripe
- **3D Processing**: gltfpack from meshoptimizer

## Installation

### Prerequisites

- Python 3.11+
- Redis
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
brew install gltfpack
```

4. Set up environment variables:

```bash
export DATABASE_URL=sqlite:///./poly_slimmer.db
export STRIPE_API_KEY=your_stripe_api_key
export STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret
export B2_KEY_ID=your_b2_key_id
export B2_KEY=your_b2_key
export B2_BUCKET=your_b2_bucket
export JWT_SECRET=your_jwt_secret
```

5. Initialize the database:

```bash
python scripts/init_db.py
```

## Running the Application

### Development

1. Start the FastAPI application:

```bash
uvicorn app.main:app --reload
```

2. Start the worker in a separate terminal:

```bash
python scripts/run_worker.py
```

### Production (using Docker)

1. Build the Docker image:

```bash
docker build -t poly-slimmer -f docker/Dockerfile .
```

2. Run the container:

```bash
docker run -p 8080:8080 -e STRIPE_API_KEY=your_stripe_key -e ... poly-slimmer
```

## Deployment

The app is designed to be deployed on Fly.io:

```bash
fly launch --name poly-slimmer --dockerfile docker/Dockerfile
fly secrets set STRIPE_API_KEY=your_stripe_key B2_KEY_ID=your_b2_key_id ...
fly volumes create data 1
```

## Architecture

The application uses a FastAPI backend with a task queue for handling optimization jobs. The frontend is built with HTMX and Tailwind CSS for a smooth user experience.

When a user uploads a model:
1. The model is stored temporarily in Backblaze B2
2. A preview is generated
3. The user can purchase a plan to download the optimized model
4. The optimization job is processed by a worker using gltfpack
5. The optimized model is available for download for 24 hours

## License

MIT License 