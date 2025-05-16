import os
import sys
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from app.main import app

client = TestClient(app)

def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_landing_page():
    """Test the landing page loads correctly"""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Poly Slimmer" in response.content

def test_api_preview_validation():
    """Test the preview API validates file types"""
    # Test with invalid file type
    with open("tests/test_api.py", "rb") as f:
        response = client.post(
            "/api/preview",
            files={"file": ("test.txt", f, "text/plain")}
        )
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

def test_checkout_route():
    """Test the checkout route parameters"""
    # Test with valid product ID
    response = client.get("/checkout/EXPORT_1")
    assert response.status_code in [200, 302]  # Redirect or success
    
    # Test with invalid product ID
    response = client.get("/checkout/INVALID")
    assert response.status_code in [400, 404]  # Bad request or not found

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 