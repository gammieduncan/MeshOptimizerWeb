import os
import tempfile
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
from arq import create_pool
from arq.connections import RedisSettings
import redis.asyncio as redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import models outside of functions to avoid import errors
try:
    from app.deps import get_db, get_b2, B2_BUCKET
    from app.models import OptimizationJob
    from sqlalchemy.orm import Session
except ImportError:
    logger.warning("Could not import app modules. This is normal if running in worker-only mode.")

# Path to gltfpack binary
GLTFPACK_PATH = os.getenv("GLTFPACK_PATH", "/usr/local/bin/gltfpack")
B2_BUCKET = os.getenv("B2_BUCKET", "poly-slimmer")

# Define the optimization function
async def optimize(ctx, job_id: int, preview_only: bool = False):
    """Optimize a 3D model with gltfpack"""
    try:
        logger.info(f"Starting optimization job {job_id} (preview_only={preview_only})")
        
        # Get job from database
        job, db = await get_job_from_db(job_id)
        
        if not job:
            logger.error(f"Job {job_id} not found")
            return {"status": "error", "message": "Job not found"}
        
        # Update job status
        await update_job_status(job, db, "processing")
        
        # Get B2 client
        b2_api = get_b2()
        bucket = b2_api.get_bucket_by_name(B2_BUCKET)
        
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "input.glb"
            output_file = temp_path / "output.glb"
            
            # Download input file
            download_data = bucket.download_file_by_name(
                file_name=job.input_file,
                download_dest=str(input_file)
            )
            
            # Get original vertex count
            vertex_info_cmd = [GLTFPACK_PATH, "-i", str(input_file), "-v"]
            
            try:
                returncode, stdout, stderr = await run_command(vertex_info_cmd)
                
                # Extract vertex count from output
                for line in stdout.splitlines():
                    if "vertices:" in line:
                        vertex_count = int(line.split("vertices:")[1].strip().split()[0])
                        job.vertex_count_before = vertex_count
                        db.commit()
                        break
            except Exception as e:
                logger.error(f"Error getting vertex count: {str(e)}")
                
            # If preview only, create a preview and return
            if preview_only:
                # TODO: Generate preview image using Three.js or other renderer
                # For now, we'll just update the job status
                job.status = "completed"
                job.preview_file = job.input_file  # Use input file as preview for now
                db.commit()
                
                return {"status": "completed", "job_id": job_id}
            
            # Run gltfpack to optimize the model
            optimize_cmd = [
                GLTFPACK_PATH,
                "-i", str(input_file),
                "-o", str(output_file),
                "-si", str(job.target_triangles / vertex_count),  # Simplification ratio
                "-cc"  # Compression
            ]
            
            try:
                returncode, stdout, stderr = await run_command(optimize_cmd, timeout=300)
                
                if returncode != 0:
                    error_msg = f"gltfpack failed with code {returncode}: {stderr}"
                    logger.error(error_msg)
                    await update_job_status(job, db, "failed", error_msg)
                    return {"status": "failed", "message": error_msg}
                
                # Get optimized vertex count
                vertex_info_cmd = [GLTFPACK_PATH, "-i", str(output_file), "-v"]
                returncode, stdout, stderr = await run_command(vertex_info_cmd)
                
                # Extract vertex count from output
                for line in stdout.splitlines():
                    if "vertices:" in line:
                        vertex_count_after = int(line.split("vertices:")[1].strip().split()[0])
                        job.vertex_count_after = vertex_count_after
                        break
                
                # Upload optimized file to B2
                output_key = f"outputs/{job.user_email}/{job_id}.glb"
                bucket.upload_local_file(
                    local_file=str(output_file),
                    file_name=output_key
                )
                
                # Update job record
                job.output_file = output_key
                job.status = "completed"
                job.updated_at = datetime.utcnow()
                db.commit()
                
                logger.info(f"Job {job_id} completed successfully")
                return {"status": "completed", "job_id": job_id}
            
            except Exception as e:
                error_msg = f"Error optimizing model: {str(e)}"
                logger.error(error_msg)
                await update_job_status(job, db, "failed", error_msg)
                return {"status": "failed", "message": error_msg}
    
    except Exception as e:
        logger.error(f"Unhandled exception in optimize job: {str(e)}")
        return {"status": "error", "message": str(e)}

async def get_job_from_db(job_id):
    """Get job from database"""
    # Get the database session
    db = next(get_db())
    
    # Get the job
    job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
    
    return job, db

async def update_job_status(job, db, status, error_message=None):
    """Update job status in the database"""
    job.status = status
    if error_message:
        job.error_message = error_message
    
    job.updated_at = datetime.utcnow()
    db.commit()

async def run_command(cmd, timeout=120):
    """Run a command asynchronously with timeout"""
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return process.returncode, stdout.decode(), stderr.decode()
    except asyncio.TimeoutError:
        process.kill()
        raise TimeoutError(f"Command timed out after {timeout} seconds: {' '.join(cmd)}")

async def queue_optimize_job(redis_client, job_id, preview_only=False):
    """Queue a job to optimize a 3D model"""
    # Create a Redis pool
    pool = await create_pool(WorkerSettings.redis_settings)
    
    # Queue the optimization job
    job = await pool.enqueue_job(
        "optimize", 
        job_id, 
        preview_only,
        _job_id=f"optimize:{job_id}"
    )
    
    # Close the pool
    await pool.close()
    
    return job.job_id

# ARQ Worker settings - this must be at the end of the file
class WorkerSettings:
    """Settings for ARQ worker"""
    redis_settings = RedisSettings.from_dsn(os.getenv("REDIS_URL", "redis://localhost:6379"))
    
    # Register functions
    functions = [optimize]
    
    # Worker configuration
    max_jobs = 10
    job_timeout = 300  # 5 minutes 