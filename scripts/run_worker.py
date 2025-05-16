#!/usr/bin/env python
import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

# Import the ARQ worker settings
from worker.gltf_worker import WorkerSettings, optimize

if __name__ == "__main__":
    print("Starting ARQ worker...")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    print("Make sure Redis is running at:", redis_url)
    print("Press Ctrl+C to stop the worker")
    
    # Import arq runner function directly
    from arq.worker import run_worker
    
    # Run the worker - this handles event loop properly
    run_worker(WorkerSettings) 