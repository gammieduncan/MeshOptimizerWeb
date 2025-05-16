import os
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session

from app.deps import get_db, get_stripe, create_access_token
from app.models import UserPlan

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Landing page with file upload zone"""
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/checkout/{product_id}")
async def create_checkout_session(
    product_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Create a Stripe checkout session"""
    stripe = get_stripe()
    
    # Define products
    products = {
        "EXPORT_1": {
            "name": "Single Export",
            "price": 400,  # $4.00
            "metadata": {"product_id": "EXPORT_1"}
        },
        "CREATOR_MONTH": {
            "name": "Creator Plan (30 days)",
            "price": 2500,  # $25.00
            "metadata": {"product_id": "CREATOR_MONTH"}
        }
    }
    
    if product_id not in products:
        return {"error": "Invalid product ID"}
    
    product = products[product_id]
    
    # Create price
    price = stripe.Price.create(
        unit_amount=product["price"],
        currency="usd",
        product_data={"name": product["name"]}
    )
    
    # Create checkout session
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price": price.id,
                "quantity": 1,
            },
        ],
        metadata=product["metadata"],
        mode="payment",
        success_url=f"{request.url_for('checkout_success')}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=request.url_for("checkout_cancel"),
    )
    
    return RedirectResponse(url=session.url)

@router.get("/checkout/success", response_class=HTMLResponse)
async def checkout_success(
    request: Request,
    session_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """Checkout success page"""
    stripe = get_stripe()
    
    try:
        # Retrieve session
        session = stripe.checkout.Session.retrieve(session_id)
        
        # Get customer email
        customer_email = session.customer_details.email
        
        # Get product details
        product_id = session.metadata.get("product_id")
        
        # Create or get user plan
        user_plan = db.query(UserPlan).filter(UserPlan.email == customer_email).first()
        
        if not user_plan:
            user_plan = UserPlan(email=customer_email)
            db.add(user_plan)
        
        # Create JWT token for authentication
        token = create_access_token(
            email=customer_email,
            plan="creator" if product_id == "CREATOR_MONTH" else "single",
            quota=1 if product_id == "EXPORT_1" else 0
        )
        
        # Render success page with token
        return templates.TemplateResponse(
            "checkout_success.html", 
            {
                "request": request, 
                "email": customer_email,
                "product_id": product_id,
                "token": token
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": str(e)}
        )

@router.get("/checkout/cancel", response_class=HTMLResponse)
async def checkout_cancel(request: Request):
    """Checkout cancelled page"""
    return templates.TemplateResponse("checkout_cancel.html", {"request": request}) 