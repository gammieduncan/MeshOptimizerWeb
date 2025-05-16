#!/usr/bin/env python
import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.append(str(Path(__file__).parent.parent))

from app.deps import Base, engine
from app.models import UserPlan, OptimizationJob

def init_db():
    """Initialize the database by creating all tables"""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    init_db() 