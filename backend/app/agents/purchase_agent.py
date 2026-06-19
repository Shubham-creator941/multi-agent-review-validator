import datetime
from sqlalchemy.orm import Session
from .base_agent import BaseAgent
from ..models import Order, Review

class PurchaseAgent(BaseAgent):
    def __init__(self):
        super().__init__("Purchase Authenticity Agent")

    async def analyze(self, review: dict, db: Session) -> dict:
        user_id = review.get("user_id")
        product_id = review.get("product_id")
        review_time = review.get("created_at") or datetime.datetime.utcnow()
        
        reasons = []
        suspicious_factors = 0
        confidence = 100.0

        # Query order history for this user and product
        order = db.query(Order).filter(
            Order.user_id == user_id,
            Order.product_id == product_id
        ).first()

        # Rule 1: Existence of purchase order
        if not order:
            suspicious_factors += 75
            reasons.append("No purchase record found: Reviewer has not ordered this product")
            return {
                "agent_name": self.name,
                "verdict": "FAKE",
                "confidence": 95.0,
                "reasons": reasons
            }

        # Rule 2: Order Status Check
        if order.status == "CANCELLED":
            suspicious_factors += 60
            reasons.append("Order was cancelled before delivery")
        elif order.status in ("SHIPPED", "PLACED"):
            # Review before delivery
            suspicious_factors += 40
            reasons.append(f"Product not yet delivered (order status: '{order.status}')")

        # Rule 3: Time gap between delivery and review
        if order.status == "DELIVERED" and order.delivered_at:
            time_gap = review_time - order.delivered_at
            
            # Review posted before delivery timestamp (e.g. delivery date modification discrepancy)
            if time_gap.total_seconds() < 0:
                suspicious_factors += 50
                reasons.append("Review posted before product delivery timestamp")
            
            # Review posted within 2 minutes of delivery
            elif time_gap.total_seconds() < 120:
                suspicious_factors += 35
                reasons.append(f"Review posted within {int(time_gap.total_seconds())} seconds of delivery: unlikely to have tested product")
            
            # Healthy organic gap (e.g. 1 to 14 days)
            elif datetime.timedelta(days=1) <= time_gap <= datetime.timedelta(days=30):
                suspicious_factors -= 10
                # Normal review window

        # Rule 4: Cross-product mass review checks (Velocity across orders)
        user_orders = db.query(Order).filter(Order.user_id == user_id).all()
        user_reviews = db.query(Review).filter(Review.user_id == user_id).all()
        
        if len(user_reviews) > 2:
            # Check review time spacing
            review_timestamps = sorted([r.created_at for r in user_reviews])
            gaps = []
            for i in range(1, len(review_timestamps)):
                gap = (review_timestamps[i] - review_timestamps[i-1]).total_seconds()
                gaps.append(gap)
            
            # If review timestamps are all within minutes (burst reviewing everything purchased)
            if gaps and any(g < 180 for g in gaps):
                suspicious_factors += 20
                reasons.append("Burst order-review behavior: user reviewing multiple orders in rapid succession")

        # Final verdict mapping
        suspicious_factors = max(0, suspicious_factors)
        if suspicious_factors >= 60:
            verdict = "FAKE"
            confidence = float(min(100.0, 50.0 + (suspicious_factors - 60) * 1.25))
        elif suspicious_factors >= 20:
            verdict = "SUSPICIOUS"
            confidence = float(min(95.0, 40.0 + suspicious_factors))
        else:
            verdict = "REAL"
            confidence = float(max(70.0, 95.0 - suspicious_factors))

        if not reasons:
            reasons.append("Verified Purchase: Product delivered and reviewed within a normal window")

        return {
            "agent_name": self.name,
            "verdict": verdict,
            "confidence": confidence,
            "reasons": reasons
        }
