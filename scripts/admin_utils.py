#!/usr/bin/env python
"""
Admin utilities for development and debugging purposes.
These functions help manage jobs when testing the application locally.
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent))

# Import models and database setup
from app.deps import get_db
from app.models import OptimizationJob

def list_jobs():
    """List all jobs in the database"""
    db = next(get_db())
    try:
        jobs = db.query(OptimizationJob).all()
        if not jobs:
            print("No jobs found in the database.")
            return
            
        print(f"Found {len(jobs)} jobs:")
        print("--------------------------------------------------")
        for job in jobs:
            print(f"ID: {job.id}")
            print(f"Status: {job.status}")
            print(f"Created: {job.created_at}")
            print(f"Input file: {job.input_file}")
            print(f"Preview file: {job.preview_file or 'None'}")
            print("--------------------------------------------------")
    finally:
        db.close()

def complete_job(job_id):
    """Force-complete a job that is stuck in processing"""
    db = next(get_db())
    try:
        job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
        if not job:
            print(f"Job with ID {job_id} not found.")
            return False
            
        # Get the file path
        if job.input_file:
            preview_path = job.input_file
        else:
            print(f"Job has no input file.")
            return False
            
        # Update job with mock data for testing
        job.status = "completed"
        job.preview_file = preview_path
        job.vertex_count_before = 100000
        job.vertex_count_after = 10000
        job.updated_at = datetime.utcnow()
        
        db.commit()
        print(f"Job {job_id} marked as completed successfully.")
        print(f"Preview file set to: {preview_path}")
        return True
    except Exception as e:
        db.rollback()
        print(f"Error completing job: {str(e)}")
        return False
    finally:
        db.close()

def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Admin utilities for development and debugging")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List jobs command
    list_parser = subparsers.add_parser("list", help="List all jobs")
    
    # Complete job command
    complete_parser = subparsers.add_parser("complete", help="Force-complete a job")
    complete_parser.add_argument("job_id", type=int, help="ID of the job to complete")
    
    args = parser.parse_args()
    
    if args.command == "list":
        list_jobs()
    elif args.command == "complete":
        complete_job(args.job_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 