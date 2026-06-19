import asyncio
import datetime
import os
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func

from .database import engine, get_db, Base
from .models import User, Product, Order, Review, ReviewFlag, FraudHistory, ReviewExecutionLog, AuditLog
from .schemas import (
    ReviewCreate, ReviewResponse, ReviewValidateResponse, 
    AdminOverrideRequest, ReviewSimulateRequest, DashboardStats, AuditLogResponse
)
from .services import review_service

# Initialize Database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Multi-Agent Review Fraud Detection System API",
    description="Production-grade real-time product review validation system using parallelized AI agent verification.",
    version="1.0.0"
)

# Enable CORS for frontend dashboard communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    static_file_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    return FileResponse(static_file_path)

@app.post("/api/review/validate", response_model=ReviewValidateResponse)
async def validate_review(review: ReviewCreate, db: Session = Depends(get_db)):
    """
    Validate a single product review in real time using the multi-agent system.
    """
    try:
        result = await review_service.validate_and_save_review(review, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")

@app.post("/api/review/simulate", response_model=ReviewValidateResponse)
async def simulate_review(payload: ReviewSimulateRequest, db: Session = Depends(get_db)):
    """
    Simulates validation with optional latency to demonstrate visual step-by-step parallel reasoning in the frontend.
    """
    if payload.simulate_delay:
        # Inject artificial thinking latency for visualization
        await asyncio.sleep(1.2)
        
    user_id = payload.user_id or f"usr_sim_{datetime.datetime.utcnow().strftime('%s')[-6:]}"
    product_id = payload.product_id or "prod_iphone"
    
    review_data = ReviewCreate(
        user_id=user_id,
        product_id=product_id,
        review_text=payload.review_text,
        rating=payload.rating,
        ip_address=payload.ip_address
    )
    
    try:
        result = await review_service.validate_and_save_review(review_data, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")

@app.get("/api/reviews")
def get_reviews(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
    product_id: Optional[str] = None,
    user_id: Optional[str] = None,
    verdict: Optional[str] = None
):
    """
    Retrieve product reviews with dynamic status filtering.
    """
    query = db.query(Review)
    if product_id:
        query = query.filter(Review.product_id == product_id)
    if user_id:
        query = query.filter(Review.user_id == user_id)
    
    if verdict:
        query = query.join(ReviewFlag).filter(ReviewFlag.verdict == verdict)
        
    reviews = query.order_by(Review.created_at.desc()).offset(skip).limit(limit).all()
    
    results = []
    for r in reviews:
        flag = r.flag
        results.append({
            "id": r.id,
            "user_id": r.user_id,
            "product_id": r.product_id,
            "review_text": r.review_text,
            "rating": r.rating,
            "created_at": r.created_at,
            "ip_address": r.ip_address,
            "verdict": flag.verdict if flag else "PENDING",
            "confidence_score": flag.confidence_score if flag else 0.0,
            "reasons": json_parse(flag.reasons) if flag else []
        })
    return results

@app.get("/api/reviews/flagged")
def get_flagged_reviews(db: Session = Depends(get_db), skip: int = 0, limit: int = 50):
    """
    Retrieve high-risk reviews flagged for rejection or manual moderator attention.
    """
    query = db.query(Review).join(ReviewFlag).filter(ReviewFlag.verdict.in_(["REJECT", "MANUAL_REVIEW"]))
    reviews = query.order_by(Review.created_at.desc()).offset(skip).limit(limit).all()
    
    results = []
    for r in reviews:
        flag = r.flag
        results.append({
            "id": r.id,
            "user_id": r.user_id,
            "product_id": r.product_id,
            "review_text": r.review_text,
            "rating": r.rating,
            "created_at": r.created_at,
            "ip_address": r.ip_address,
            "verdict": flag.verdict,
            "confidence_score": flag.confidence_score,
            "reasons": json_parse(flag.reasons)
        })
    return results

@app.post("/api/admin/override")
def override_review_verdict(payload: AdminOverrideRequest, db: Session = Depends(get_db)):
    """
    Allows a human moderator to manually override agent-based automated decisions.
    Records audits of override logs for regulatory trail requirements.
    """
    review = db.query(Review).filter(Review.id == payload.review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
        
    flag = review.flag
    if not flag:
        # Create a new review flag if missing
        flag = ReviewFlag(review_id=review.id)
        db.add(flag)
        
    old_verdict = flag.verdict
    flag.verdict = payload.new_verdict
    flag.confidence_score = 100.0  # Manual overrides carry 100% human certainty
    
    # Audit log persistence
    audit = AuditLog(
        user_action="ADMIN_OVERRIDE",
        review_id=review.id,
        target_user=review.user_id,
        description=f"Moderator manual override: Verdict on '{review.id}' changed from '{old_verdict}' to '{payload.new_verdict}'. Reason: {payload.reason}"
    )
    db.add(audit)
    
    # Update dynamic User trust score for corrective loops
    user = db.query(User).filter(User.id == review.user_id).first()
    if user:
        if payload.new_verdict == "APPROVE" and old_verdict == "REJECT":
            # Correcting a false positive -> restore trust
            user.trust_score = min(100.0, user.trust_score + 40.0)
            if user.is_banned:
                user.is_banned = False
                audit_unban = AuditLog(
                    user_action="ADMIN_UNBAN",
                    target_user=user.id,
                    description=f"User unbanned after review manual override correction."
                )
                db.add(audit_unban)
        elif payload.new_verdict == "REJECT":
            user.trust_score = max(0.0, user.trust_score - 30.0)

    db.commit()
    return {"status": "success", "message": f"Verdict overridden to {payload.new_verdict}"}

@app.get("/api/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    Retrieve statistics, aggregated charts, recent flags, and fraud business savings.
    """
    total_reviews = db.query(Review).count()
    approved_reviews = db.query(ReviewFlag).filter(ReviewFlag.verdict == "APPROVE").count()
    rejected_reviews = db.query(ReviewFlag).filter(ReviewFlag.verdict == "REJECT").count()
    manual_reviews = db.query(ReviewFlag).filter(ReviewFlag.verdict == "MANUAL_REVIEW").count()
    banned_users = db.query(User).filter(User.is_banned == True).count()
    
    # Business metrics: Catching fake reviews saves sellers $100 per incident
    savings_usd = rejected_reviews * 100.0
    
    # Simple system accuracy rate calculation based on manual overrides
    # (Total actions - overrides) / Total actions
    overrides_count = db.query(AuditLog).filter(AuditLog.user_action == "ADMIN_OVERRIDE").count()
    accuracy_rate = 98.2  # Base target metric
    if total_reviews > 0 and overrides_count > 0:
        accuracy_rate = round(max(85.0, ((total_reviews - overrides_count) / total_reviews) * 100.0), 1)

    # Fetch 10 most recent flags
    recent_flags_raw = db.query(ReviewFlag).join(Review).order_by(ReviewFlag.flagged_at.desc()).limit(10).all()
    recent_flags = []
    for rf in recent_flags_raw:
        review_ref = db.query(Review).filter(Review.id == rf.review_id).first()
        recent_flags.append({
            "review_id": rf.review_id,
            "verdict": rf.verdict,
            "confidence_score": rf.confidence_score,
            "flagged_at": rf.flagged_at.isoformat(),
            "review_text": review_ref.review_text if review_ref else "",
            "rating": review_ref.rating if review_ref else 5
        })

    categories_raw = db.query(Product.category, func.count(ReviewFlag.id))\
        .select_from(Product)\
        .join(Review, Product.id == Review.product_id)\
        .join(ReviewFlag, Review.id == ReviewFlag.review_id)\
        .filter(ReviewFlag.verdict == "REJECT")\
        .group_by(Product.category).all()
    category_distribution = {cat or "General": cnt for cat, cnt in categories_raw}
    if not category_distribution:
        category_distribution = {"Electronics": 0, "Fashion": 0, "Home & Living": 0}

    # Daily trend statistics (Last 7 days)
    daily_trends = []
    for i in range(6, -1, -1):
        day = datetime.datetime.utcnow().date() - datetime.timedelta(days=i)
        start_dt = datetime.datetime.combine(day, datetime.time.min)
        end_dt = datetime.datetime.combine(day, datetime.time.max)
        
        day_total = db.query(Review).filter(Review.created_at.between(start_dt, end_dt)).count()
        day_rejected = db.query(ReviewFlag).filter(
            ReviewFlag.flagged_at.between(start_dt, end_dt), 
            ReviewFlag.verdict == "REJECT"
        ).count()
        
        daily_trends.append({
            "date": day.strftime("%b %d"),
            "reviews": day_total,
            "frauds": day_rejected
        })

    return {
        "total_reviews": total_reviews,
        "approved_reviews": approved_reviews,
        "rejected_reviews": rejected_reviews,
        "manual_reviews": manual_reviews,
        "banned_users": banned_users,
        "accuracy_rate": accuracy_rate,
        "savings_usd": savings_usd,
        "recent_flags": recent_flags,
        "category_distribution": category_distribution,
        "daily_trends": daily_trends
    }

@app.get("/api/audit/logs", response_model=List[AuditLogResponse])
def get_audit_logs(db: Session = Depends(get_db), limit: int = 50):
    """
    Fetch system transparency logs.
    """
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()

@app.get("/api/review/{review_id}/logs")
def get_review_execution_logs(review_id: str, db: Session = Depends(get_db)):
    """
    Returns step-by-step agent outputs and latency metrics for validation trace replays.
    """
    logs = db.query(ReviewExecutionLog).filter(ReviewExecutionLog.review_id == review_id).all()
    results = []
    for l in logs:
        results.append({
            "agent_name": l.agent_name,
            "input_snapshot": json_parse(l.input_snapshot),
            "output": json_parse(l.output),
            "latency_ms": l.latency_ms
        })
    return results

# Helper utilities
def json_parse(value):
    if not value:
        return {}
    try:
        return json.loads(value)
    except:
        try:
            # Check if it was double-encoded
            import json
            return json.loads(json.loads(value))
        except:
            return value
