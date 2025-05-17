#!/usr/bin/env python
"""
Worker diagnostic script

This script helps diagnose issues with Redis and the ARQ worker.
It checks Redis connection, queued jobs, and worker status.
"""

import os
import sys
import redis
import json
from pathlib import Path
from datetime import datetime

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

# Try to import app modules
try:
    from app.deps import get_db, get_redis
    from app.models import OptimizationJob
    from worker.gltf_worker import WorkerSettings
except ImportError as e:
    print(f"Warning: Could not import app modules: {e}")

async def check_redis_connection():
    """Check if Redis is running and accessible"""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    print(f"Checking Redis connection: {redis_url}")
    
    try:
        client = redis.from_url(redis_url)
        info = client.info()
        print(f"✅ Redis is running: version {info.get('redis_version', 'unknown')}")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {str(e)}")
        return False

def check_worker_process():
    """Check if ARQ worker process is running"""
    import subprocess
    
    try:
        # Use ps command to find worker process
        result = subprocess.run(
            ["ps", "-ef"], 
            capture_output=True, 
            text=True
        )
        
        output = result.stdout
        worker_processes = [line for line in output.split('\n') if 'run_worker.py' in line and 'grep' not in line]
        
        if worker_processes:
            print(f"✅ ARQ worker is running:")
            for proc in worker_processes:
                print(f"   {proc.strip()}")
            return True
        else:
            print("❌ No ARQ worker process found")
            print("To start worker: python scripts/run_worker.py")
            return False
            
    except Exception as e:
        print(f"❌ Error checking worker process: {str(e)}")
        return False

async def check_queued_jobs():
    """Check jobs in Redis queue"""
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        client = redis.from_url(redis_url)
        
        # Check queued jobs
        queue_key = 'arq:queue'
        queue_len = client.llen(queue_key)
        
        print(f"Queue length: {queue_len}")
        
        if queue_len > 0:
            print("Queued jobs:")
            queued_jobs = client.lrange(queue_key, 0, -1)
            for i, job_data in enumerate(queued_jobs):
                job = json.loads(job_data)
                job_id = job.get('job_id', 'unknown')
                function = job.get('function', 'unknown')
                args = job.get('args', [])
                print(f"  {i+1}. Job ID: {job_id}, Function: {function}, Args: {args}")
        
        # Check jobs in progress
        in_progress_key = 'arq:in_progress'
        in_progress = client.hgetall(in_progress_key)
        
        if in_progress:
            print("\nJobs in progress:")
            for worker_id, job_id in in_progress.items():
                print(f"  Worker: {worker_id.decode()}, Job: {job_id.decode()}")
        else:
            print("No jobs in progress")
            
        return queue_len
    except Exception as e:
        print(f"❌ Error checking queued jobs: {str(e)}")
        return 0

async def check_db_jobs():
    """Check job status in database"""
    try:
        db = next(get_db())
        pending_jobs = db.query(OptimizationJob).filter(OptimizationJob.status == "pending").all()
        processing_jobs = db.query(OptimizationJob).filter(OptimizationJob.status == "processing").all()
        
        if pending_jobs:
            print(f"\nPending jobs in database ({len(pending_jobs)}):")
            for job in pending_jobs:
                created = job.created_at.strftime('%Y-%m-%d %H:%M:%S')
                print(f"  Job {job.id}: Created {created}, Input: {job.input_file}")
        
        if processing_jobs:
            print(f"\nProcessing jobs in database ({len(processing_jobs)}):")
            for job in processing_jobs:
                created = job.created_at.strftime('%Y-%m-%d %H:%M:%S')
                print(f"  Job {job.id}: Created {created}, Input: {job.input_file}")
                
        stuck_jobs = []
        for job in processing_jobs:
            # If job has been processing for more than 5 minutes, it might be stuck
            time_diff = datetime.utcnow() - job.updated_at
            if time_diff.total_seconds() > 300:  # 5 minutes
                stuck_jobs.append(job)
        
        if stuck_jobs:
            print(f"\n⚠️ Potentially stuck jobs ({len(stuck_jobs)}):")
            for job in stuck_jobs:
                time_diff = datetime.utcnow() - job.updated_at
                minutes = int(time_diff.total_seconds() / 60)
                print(f"  Job {job.id}: Processing for {minutes} minutes")
                print(f"  To fix: python scripts/fix_job.py {job.id}")
        
        return pending_jobs, processing_jobs
    except Exception as e:
        print(f"❌ Error checking database jobs: {str(e)}")
        return [], []

async def main():
    """Main function"""
    print("\n===== Worker Diagnostic Tool =====\n")
    
    # Check Redis
    redis_ok = await check_redis_connection()
    
    if redis_ok:
        # Check queued jobs
        print("\n----- Queued Jobs -----")
        await check_queued_jobs()
    
    # Check worker process
    print("\n----- Worker Process -----")
    worker_ok = check_worker_process()
    
    # Check database jobs
    print("\n----- Database Jobs -----")
    pending_jobs, processing_jobs = await check_db_jobs()
    
    # Summary
    print("\n----- Summary -----")
    if redis_ok and worker_ok:
        print("✅ Redis and worker appear to be running correctly")
        
        if pending_jobs and not processing_jobs:
            print("⚠️ There are pending jobs but none processing. Check worker logs.")
    else:
        print("❌ There are issues with your setup:")
        if not redis_ok:
            print("  - Redis is not running or accessible")
        if not worker_ok:
            print("  - ARQ worker is not running")
    
    print("\nFor stuck jobs, run: python scripts/fix_job.py JOB_ID")
    print("To restart worker: python scripts/run_worker.py")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 