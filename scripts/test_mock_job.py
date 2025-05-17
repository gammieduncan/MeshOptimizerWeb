#!/usr/bin/env python
"""
Test script to create a mock optimization job without external dependencies.
This is useful for testing the frontend without Redis or B2 storage.
"""
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timedelta

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent))

# Import models and database setup
from app.deps import get_db
from app.models import OptimizationJob

def create_mock_job():
    """Create a mock optimization job for testing"""
    # Create uploads directory if it doesn't exist
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    
    # Create a mock input file
    unique_id = str(uuid.uuid4())
    mock_filename = f"{unique_id}.glb"
    mock_path = uploads_dir / mock_filename
    
    # Create empty file
    with open(mock_path, 'w') as f:
        f.write("# Mock GLB file for testing")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Create job record
        job = OptimizationJob(
            user_email="test@example.com",
            input_file=str(mock_path),
            preview_file=str(mock_path),  # Use same file for preview
            target_triangles=10000,
            status="completed",  # Mark as completed immediately
            vertex_count_before=100000,
            vertex_count_after=10000,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db.add(job)
        db.commit()
        
        print(f"Created mock job with ID: {job.id}")
        print(f"Job status: {job.status}")
        print(f"Mock file: {mock_path}")
        print(f"To test, visit: http://localhost:8000/api/status/{job.id}")
        
        return job.id
    except Exception as e:
        print(f"Error creating mock job: {str(e)}")
        db.rollback()
        return None
    finally:
        db.close()

if __name__ == "__main__":
    print("Creating mock optimization job...")
    job_id = create_mock_job()
    if job_id:
        print("\nSuccess! Use this job for testing the UI.")
    else:
        print("\nFailed to create mock job.") 