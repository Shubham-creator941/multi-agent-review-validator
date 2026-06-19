import datetime
import uuid
import json
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models import User, Product, Order, Review, ReviewFlag, FraudHistory, ReviewExecutionLog, AuditLog
from ..schemas import ReviewCreate
from ..orchestrator import validate_review
from ..aggregator import aggregate_decisions

async def validate_and_save_review(review_data: ReviewCreate, db: Session) -> dict:
    """
    Service layer to validate review, run multi-agent evaluations, 
    persist records, log executions, update trust scores, and apply auto-ban rules.
    """
    user_id = review_data.user_id
    product_id = review_data.product_id

    # 1. Fetch or create User and Product to prevent foreign key issues
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        # Create a default guest user created today (triggers new account flag)
        user = User(
            id=user_id,
            username=f"guest_{user_id[:6] if len(user_id) > 6 else user_id}",
            email=f"{user_id}@marketplace.com",
            created_at=datetime.datetime.utcnow(),
            trust_score=100.0,
            is_banned=False,
            ip_address=review_data.ip_address
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        # Create default product
        product = Product(
            id=product_id,
            name=f"Product {product_id}",
            category="General",
            price=299.0,
            average_rating=0.0
        )
        db.add(product)
        db.commit()
        db.refresh(product)

    # 2. Block evaluation if user is already banned
    if user.is_banned:
        banned_review_id = f"rev_{uuid.uuid4().hex[:8]}"
        dummy_review = Review(
            id=banned_review_id,
            user_id=user.id,
            product_id=product.id,
            review_text=review_data.review_text,
            rating=review_data.rating,
            created_at=datetime.datetime.utcnow(),
            ip_address=review_data.ip_address
        )
        db.add(dummy_review)
        
        flag = ReviewFlag(
            review_id=banned_review_id,
            verdict="REJECT",
            confidence_score=100.0,
            reasons=json.dumps(["User is blacklisted"]),
            agent_outputs=json.dumps({})
        )
        db.add(flag)
        db.commit()
        
        return {
            "review_id": banned_review_id,
            "final_verdict": "REJECT",
            "confidence_score": 100.0,
            "reasoning": "This user is banned from posting reviews on the marketplace.",
            "agent_outputs": {},
            "is_auto_banned": True
        }

    # 3. Generate review ID and dict metadata (no DB add/flush yet to avoid transaction lock deadlocks)
    review_id = f"rev_{uuid.uuid4().hex[:8]}"
    review_dict = {
        "id": review_id,
        "user_id": user.id,
        "product_id": product.id,
        "review_text": review_data.review_text,
        "rating": review_data.rating,
        "created_at": datetime.datetime.utcnow(),
        "ip_address": review_data.ip_address
    }

    # 4. Trigger parallel agent validation via orchestrator
    agent_results = await validate_review(review_dict)

    # 5. Create and add Review record to database now
    review = Review(
        id=review_id,
        user_id=user.id,
        product_id=product.id,
        review_text=review_dict["review_text"],
        rating=review_dict["rating"],
        created_at=review_dict["created_at"],
        ip_address=review_dict["ip_address"]
    )
    db.add(review)

    # 5. Log execution metrics to ReviewExecutionLog
    for res in agent_results:
        log = ReviewExecutionLog(
            review_id=review_id,
            agent_name=res["agent_name"],
            input_snapshot=json.dumps(review_dict, default=str),
            output=json.dumps(res),
            latency_ms=res.get("latency_ms", 0)
        )
        db.add(log)

    # 6. Aggregate scores
    agg_result = aggregate_decisions(agent_results)
    final_verdict = agg_result["final_verdict"]
    confidence_score = agg_result["confidence_score"]
    reasoning = agg_result["explanation"]

    # 7. Write ReviewFlag record
    flag = ReviewFlag(
        review_id=review_id,
        verdict=final_verdict,
        confidence_score=confidence_score,
        reasons=json.dumps(agg_result["explanation"].split("\n")),
        agent_outputs=json.dumps(agg_result["agent_outputs"])
    )
    db.add(flag)

    # 8. Record FraudHistory entry
    fraud_score = round(100.0 - confidence_score, 2)
    history_entry = FraudHistory(
        user_id=user.id,
        review_id=review_id,
        fraud_score=fraud_score,
        timestamp=datetime.datetime.utcnow(),
        action_taken="BAN" if final_verdict == "REJECT" else "FLAG" if final_verdict == "MANUAL_REVIEW" else "NONE"
    )
    db.add(history_entry)

    # 9. Update user trust score based on dynamic scoring:
    # - Reject: -30 trust score
    # - Manual Review: -10 trust score
    # - Approve: +5 trust score (max 100)
    current_trust = user.trust_score
    if final_verdict == "REJECT":
        user.trust_score = max(0.0, current_trust - 30.0)
    elif final_verdict == "MANUAL_REVIEW":
        user.trust_score = max(0.0, current_trust - 10.0)
    else:
        user.trust_score = min(100.0, current_trust + 5.0)

    # 10. Auto-Ban Verification Engine
    # IF:
    # - FraudHistory average score > 75 (for the user)
    # AND
    # - 3+ rejected reviews in last 7 days
    # AND
    # - TrustScore < 15
    # THEN -> Auto-ban user, reject all reviews, audit trail logging.
    seven_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    
    # Calculate average fraud score
    avg_fraud = db.query(func.avg(FraudHistory.fraud_score)).filter(
        FraudHistory.user_id == user.id
    ).scalar() or 0.0
    
    # Count rejected reviews in last 7 days
    recent_rejected_count = db.query(ReviewFlag).join(Review).filter(
        Review.user_id == user.id,
        ReviewFlag.verdict == "REJECT",
        ReviewFlag.flagged_at >= seven_days_ago
    ).count()

    is_auto_banned = False
    if avg_fraud > 75.0 and recent_rejected_count >= 3 and user.trust_score < 15.0:
        is_auto_banned = True
        user.is_banned = True
        
        # Override all their previous review flags to REJECT
        user_reviews = db.query(Review).filter(Review.user_id == user.id).all()
        for ur in user_reviews:
            if ur.flag:
                ur.flag.verdict = "REJECT"
                ur.flag.confidence_score = 100.0
                
        # Write to Audit Log
        audit = AuditLog(
            user_action="AUTO_BAN",
            target_user=user.id,
            review_id=review_id,
            description=f"User auto-banned: Avg Fraud Score {avg_fraud:.1f}% (>75%), {recent_rejected_count} rejects in last 7d, Trust Score {user.trust_score:.1f} (<15)."
        )
        db.add(audit)
    
    # Log regular audit log for manual/rejected flags
    if final_verdict in ("REJECT", "MANUAL_REVIEW") and not is_auto_banned:
        audit = AuditLog(
            user_action="SYSTEM_FLAG",
            target_user=user.id,
            review_id=review_id,
            description=f"Review flagged as {final_verdict} (Score: {confidence_score:.1f}/100)."
        )
        db.add(audit)

    db.commit()
    db.refresh(user)

    return {
        "review_id": review_id,
        "final_verdict": "REJECT" if is_auto_banned or final_verdict == "REJECT" else final_verdict,
        "confidence_score": confidence_score,
        "reasoning": reasoning,
        "agent_outputs": agg_result["agent_outputs"],
        "is_auto_banned": is_auto_banned
    }
