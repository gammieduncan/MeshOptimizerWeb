from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.deps import Base

class UserPlan(Base):
    """User plan/entitlement information"""
    __tablename__ = "user_plan"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    plan = Column(String, default="single")  # 'single' or 'creator'
    quota = Column(Integer, default=0)  # Credits for single export plan
    expires_at = Column(DateTime, nullable=True)  # For creator plan
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OptimizationJob(Base):
    """Represents a model optimization job"""
    __tablename__ = "optimization_job"
    
    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, index=True)
    input_file = Column(String)  # S3 key for input file
    output_file = Column(String, nullable=True)  # S3 key for output file
    preview_file = Column(String, nullable=True)  # S3 key for preview image
    target_triangles = Column(Integer)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    error_message = Column(String, nullable=True)
    vertex_count_before = Column(Integer, nullable=True)
    vertex_count_after = Column(Integer, nullable=True)
    is_paid = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime)  # When to delete file from storage 