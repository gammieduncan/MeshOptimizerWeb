from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.routes import public, api
from app.deps import get_db

app = FastAPI(title="Poly Slimmer", description="Polygon reducer for 3D models")

# Mount static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(public.router)
app.include_router(api.router, prefix="/api")

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}

# Add Stripe webhook route
@app.post("/stripe/webhook")
async def stripe_webhook(request: Request, db=Depends(get_db)):
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    
    from app.deps import get_stripe
    stripe = get_stripe()
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, stripe.webhook_secret
        )
    except ValueError:
        # Invalid payload
        return {"status": "error", "message": "Invalid payload"}
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        return {"status": "error", "message": "Invalid signature"}
    
    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        await process_successful_payment(session, db)
    
    return {"status": "success"}

async def process_successful_payment(session, db):
    """Process a successful payment from Stripe"""
    customer_email = session["customer_details"]["email"]
    product_id = session["metadata"].get("product_id")
    
    from datetime import datetime, timedelta
    
    # Get or create entitlement
    from app.models import UserPlan
    ent = db.query(UserPlan).filter(UserPlan.email == customer_email).first()
    
    if not ent:
        ent = UserPlan(email=customer_email)
        db.add(ent)
    
    # Update entitlement based on product
    now = datetime.utcnow()
    if product_id == "EXPORT_1":
        ent.quota += 1
    elif product_id == "CREATOR_MONTH":
        ent.expires_at = now + timedelta(days=30)
        ent.plan = "creator"
    
    db.commit() 