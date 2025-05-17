import os
from functools import lru_cache
from typing import Generator
import stripe
import redis.asyncio as redis
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from datetime import datetime, timedelta
from jose import jwt

# Environment settings
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./poly_slimmer.db")
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_KEY = os.getenv("B2_KEY")
B2_BUCKET = os.getenv("B2_BUCKET", "poly-slimmer")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key")  # Change in production!
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Database setup
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """Get a database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@lru_cache()
def get_stripe():
    """Get Stripe client"""
    stripe.api_key = STRIPE_API_KEY
    stripe.webhook_secret = STRIPE_WEBHOOK_SECRET
    return stripe

@lru_cache()
def get_b2():
    """Get Backblaze B2 client"""
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    
    if not B2_KEY_ID or not B2_KEY:
        print("WARNING: B2 credentials not configured. File storage will not work.")
        # Create dummy B2 API client for testing
        return b2_api
    
    try:
        b2_api.authorize_account("production", B2_KEY_ID, B2_KEY)
        return b2_api
    except Exception as e:
        print(f"Error authorizing B2 account: {str(e)}")
        # Return unauthorized client - operations will fail but won't crash immediately
        return b2_api

@lru_cache()
def get_redis():
    """Get Redis client"""
    return redis.from_url(REDIS_URL, decode_responses=True)

# JWT functions
def create_access_token(email: str, plan: str = "single", quota: int = 1, expires_delta: timedelta = None):
    """Create a JWT access token"""
    if expires_delta is None:
        expires_delta = timedelta(hours=JWT_EXPIRATION_HOURS)
        
    to_encode = {
        "sub": email,
        "p": plan,  # Plan type: single, creator
        "q": quota,  # Quota remaining
        "exp": datetime.utcnow() + expires_delta
    }
    
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str):
    """Decode a JWT token"""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM]) 