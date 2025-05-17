import os
import uuid
import tempfile
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from jose import JWTError
from pathlib import Path

from app.deps import get_db, get_b2, get_redis, decode_token, B2_BUCKET
from app.models import OptimizationJob, UserPlan
from worker.gltf_worker import queue_optimize_job

router = APIRouter()
security = HTTPBearer()

# Constants
ALLOWED_EXTENSIONS = {".glb", ".fbx", ".gltf"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Get current user from JWT token"""
    try:
        token = credentials.credentials
        payload = decode_token(token)
        
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        # Verify if user exists in db
        user = db.query(UserPlan).filter(UserPlan.email == email).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Check if subscription is valid
        if user.plan == "creator" and user.expires_at and user.expires_at < datetime.utcnow():
            raise HTTPException(status_code=403, detail="Subscription expired")
        
        # Check if quota is available for single plan
        if user.plan == "single" and user.quota <= 0:
            raise HTTPException(status_code=403, detail="No export credits remaining")
        
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

@router.post("/preview")
async def create_preview(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    b2_api = Depends(get_b2)
):
    """Upload a model and create a preview without optimization"""
    print(f"Processing preview request for file: {file.filename}")
    
    # Validate file type
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}")
    
    # Read file
    contents = await file.read()
    
    # Check file size
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB")
    
    # Generate unique filename
    unique_id = str(uuid.uuid4())
    file_key = f"uploads/{unique_id}{file_ext}"
    
    # For local testing - save to a local directory
    local_uploads_dir = Path("uploads")
    local_uploads_dir.mkdir(exist_ok=True)
    local_file_path = local_uploads_dir / f"{unique_id}{file_ext}"
    
    with open(local_file_path, "wb") as f:
        f.write(contents)
    
    print(f"Saved local file: {local_file_path}")
    
    # Save file to temp directory for B2 upload (if configured)
    b2_upload_success = False
    
    if os.getenv("B2_KEY_ID") and os.getenv("B2_KEY"):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        
        try:
            # Try to upload to B2 if credentials are available
            bucket = b2_api.get_bucket_by_name(B2_BUCKET)
            with open(tmp_path, 'rb') as file_data:
                bucket.upload_local_file(
                    local_file=tmp_path,
                    file_name=file_key
                )
            b2_upload_success = True
            print(f"Uploaded file to B2: {file_key}")
            
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception as e:
            # Log the B2 error but continue using local file
            print(f"B2 upload error: {str(e)}")
            b2_upload_success = False
    else:
        print("Skipping B2 upload - no credentials configured")
    
    # For development testing, use mock data for vertex counts
    mock_vertex_before = 100000
    mock_vertex_after = 10000
    
    # Create job record for preview only
    job = OptimizationJob(
        user_email="anonymous",  # Preview doesn't require authentication
        input_file=file_key if b2_upload_success else str(local_file_path),
        target_triangles=10000,  # Default for preview
        status="pending",
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )
    db.add(job)
    db.commit()
    print(f"Created job record with ID: {job.id}, input file: {job.input_file}")
    
    # Queue preview generation job or mark as completed for testing
    redis_error = False
    try:
        # Try to use Redis if configured
        if os.getenv("REDIS_URL"):
            print(f"Attempting to queue job {job.id} in Redis")
            redis_client = await get_redis()
            job_id = await queue_optimize_job(redis_client, job.id, preview_only=True)
            print(f"Job queued in Redis with ID: {job_id}")
        else:
            print("Redis URL not configured - skipping job queue")
            redis_error = True
    except Exception as e:
        # Handle Redis connection error - will mark as completed for local development
        print(f"Redis error or not configured: {str(e)} - using local development mode")
        redis_error = True
    
    # If Redis failed or is not configured, handle it locally
    if redis_error:
        print(f"Using local development mode for job {job.id}")
        # Update job status directly for testing
        job.status = "completed"
        job.preview_file = str(local_file_path)
        job.vertex_count_before = mock_vertex_before
        job.vertex_count_after = mock_vertex_after
        db.commit()
        print(f"Job marked as completed: {job.id}, preview: {job.preview_file}")
    
    # Double check the job status
    db.refresh(job)
    print(f"Final job status: {job.status} (ID: {job.id})")
    
    return {
        "job_id": job.id,
        "status": job.status,  # Return current status which might be 'completed' for local dev
        "message": "Preview generation in progress" if job.status == "pending" else "Preview ready"
    }

@router.post("/optimize")
async def optimize_model(
    file: UploadFile = File(...),
    target_triangles: int = Form(...),
    user: UserPlan = Depends(get_current_user),
    db: Session = Depends(get_db),
    b2_api = Depends(get_b2)
):
    """Upload and optimize a 3D model"""
    # Validate file type
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}")
    
    # Validate target triangles
    if target_triangles < 1000 or target_triangles > 100000:
        raise HTTPException(status_code=400, detail="Target triangles must be between 1,000 and 100,000")
    
    # Read file
    contents = await file.read()
    
    # Check file size
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB")
    
    # Generate unique filename
    unique_id = str(uuid.uuid4())
    file_key = f"uploads/{user.email}/{unique_id}{file_ext}"
    
    # Save file to temp directory
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name
    
    try:
        # Upload to B2
        bucket = b2_api.get_bucket_by_name(B2_BUCKET)
        with open(tmp_path, 'rb') as file_data:
            bucket.upload_local_file(
                local_file=tmp_path,
                file_name=file_key
            )
        
        # Create job record
        job = OptimizationJob(
            user_email=user.email,
            input_file=file_key,
            target_triangles=target_triangles,
            status="pending",
            is_paid=True,  # User is authenticated, so job is paid
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db.add(job)
        
        # Reduce user quota for single-export plan
        if user.plan == "single":
            user.quota -= 1
        
        db.commit()
        
        # Queue optimization job
        redis_client = await get_redis()
        job_id = await queue_optimize_job(redis_client, job.id)
        
        return {
            "job_id": job.id,
            "status": "pending",
            "message": "Optimization job queued"
        }
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@router.get("/status/{job_id}")
async def get_job_status(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Check the status of an optimization job"""
    job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    response = {
        "status": job.status,
        "created_at": job.created_at.isoformat(),
    }
    
    if job.status == "completed":
        # Add vertex counts if available
        response["vertex_count_before"] = job.vertex_count_before or 100000  # Default for mock data
        response["vertex_count_after"] = job.vertex_count_after or 10000     # Default for mock data
        
        # Check if the preview file is a local file path or a B2 key
        if job.preview_file:
            if os.path.exists(job.preview_file):
                # Local file for development
                file_path = Path(job.preview_file)
                
                # Ensure the file is accessible through the mounted uploads directory
                if "uploads" in str(file_path):
                    # Extract just the filename
                    filename = file_path.name
                    response["preview_url"] = f"/uploads/{filename}"
                else:
                    # Try to copy to uploads if it's elsewhere
                    uploads_dir = Path("uploads")
                    uploads_dir.mkdir(exist_ok=True)
                    
                    target_path = uploads_dir / file_path.name
                    try:
                        import shutil
                        shutil.copy2(file_path, target_path)
                        response["preview_url"] = f"/uploads/{file_path.name}"
                    except Exception as e:
                        print(f"Error copying file: {e}")
                        response["preview_url"] = "#"
            else:
                # B2 file
                try:
                    b2_api = get_b2()
                    bucket = b2_api.get_bucket_by_name(B2_BUCKET)
                    
                    # Get download authorization
                    download_auth = b2_api.get_download_authorization(
                        bucket_name=B2_BUCKET,
                        file_name_prefix=job.preview_file,
                        valid_duration_in_seconds=3600
                    )
                    
                    # Get the download URL with authorization
                    download_url = b2_api.get_download_url_with_auth(
                        download_auth=download_auth,
                        file_name=job.preview_file
                    )
                    
                    response["preview_url"] = download_url
                except Exception as e:
                    # If B2 download fails, fallback to a placeholder
                    print(f"Error generating B2 download URL: {str(e)}")
                    response["preview_url"] = "#"
        else:
            # No preview file, create a placeholder for testing
            response["preview_url"] = "#"
    
    elif job.status == "failed":
        response["error_message"] = job.error_message or "Unknown error"
    
    # Debug information
    print(f"Returning status for job {job_id}: {response}")
    
    return response

@router.get("/download/{job_id}")
async def download_optimized_model(
    job_id: int,
    user: UserPlan = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download an optimized model"""
    job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check job ownership
    if job.user_email != user.email:
        raise HTTPException(status_code=403, detail="You don't have permission to access this job")
    
    # Check if job is completed
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job is not ready for download. Current status: {job.status}")
    
    # Check if output file exists
    if not job.output_file:
        raise HTTPException(status_code=400, detail="Output file not available")
    
    # Generate signed URL for download
    b2_api = get_b2()
    bucket = b2_api.get_bucket_by_name(B2_BUCKET)
    
    # Get download authorization
    download_auth = b2_api.get_download_authorization(
        bucket_name=B2_BUCKET,
        file_name_prefix=job.output_file,
        valid_duration_in_seconds=3600
    )
    
    # Get the download URL with authorization
    download_url = b2_api.get_download_url_with_auth(
        download_auth=download_auth,
        file_name=job.output_file
    )
    
    return RedirectResponse(url=download_url) 