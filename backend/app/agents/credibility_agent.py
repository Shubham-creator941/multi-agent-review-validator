import re
import datetime
from sqlalchemy.orm import Session
from .base_agent import BaseAgent
from ..models import User, Review

class CredibilityAgent(BaseAgent):
    def __init__(self):
        super().__init__("Reviewer Credibility Agent")

    async def analyze(self, review: dict, db: Session) -> dict:
        user_id = review.get("user_id")
        user = db.query(User).filter(User.id == user_id).first()
        
        reasons = []
        suspicious_factors = 0
        confidence = 100.0

        if not user:
            # If user is not found, treat as brand new guest (suspicious/unregistered)
            verdict = "SUSPICIOUS"
            confidence = 80.0
            reasons.append("Unregistered or untracked user ID")
            return {
                "agent_name": self.name,
                "verdict": verdict,
                "confidence": confidence,
                "reasons": reasons
            }

        # Rule 0: Auto-ban check
        if user.is_banned:
            return {
                "agent_name": self.name,
                "verdict": "FAKE",
                "confidence": 100.0,
                "reasons": ["User is on the system ban list"]
            }

        # Rule 1: Account Age Check
        # Let's say user.created_at is datetime
        now = datetime.datetime.utcnow()
        account_age_days = (now - user.created_at).days
        
        if account_age_days < 1:
            suspicious_factors += 35
            reasons.append(f"Brand new account: created today")
        elif account_age_days < 7:
            suspicious_factors += 20
            reasons.append(f"New account: created {account_age_days} days ago")
        elif account_age_days > 180:
            # Established account
            suspicious_factors -= 15

        # Rule 2: Username Pattern Check
        # Check if username looks like a random hash or bot string
        username = user.username or ""
        # Examples: "user_12345_new", "bot99827", "ab12cd34ef56"
        if re.search(r"^[a-zA-Z]+_\d{4,}_[a-zA-Z]+$", username) or re.search(r"\d{5,}$", username):
            suspicious_factors += 25
            reasons.append(f"Bot-like username pattern detected: '{username}'")
        elif re.search(r"^[a-zA-Z0-9]{15,}$", username) and len(re.findall(r"\d", username)) > 6:
            suspicious_factors += 20
            reasons.append(f"Highly suspicious alphanumeric username: '{username}'")

        # Rule 3: Past Review Volume & Frequency (Velocity)
        past_reviews = db.query(Review).filter(Review.user_id == user_id).all()
        past_reviews_count = len(past_reviews)

        # Check for burst reviews in last 1 hour
        one_hour_ago = now - datetime.timedelta(hours=1)
        recent_reviews = [r for r in past_reviews if r.created_at > one_hour_ago]
        
        if len(recent_reviews) >= 3:
            suspicious_factors += 30
            reasons.append(f"High review velocity: posted {len(recent_reviews)} reviews in the last hour")

        # Rule 4: Extreme rating distribution
        if past_reviews_count >= 5:
            ratings = [r.rating for r in past_reviews]
            five_star_ratio = ratings.count(5) / past_reviews_count
            one_star_ratio = ratings.count(1) / past_reviews_count
            
            if five_star_ratio > 0.8:
                suspicious_factors += 15
                reasons.append(f"Bias review behavior: {five_star_ratio:.0%} of past reviews are 5-star")
            elif one_star_ratio > 0.8:
                suspicious_factors += 20
                reasons.append(f"Negative bias behavior: {one_star_ratio:.0%} of past reviews are 1-star")

        # Determine Verdict and Confidence
        # Normalize score
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
            reasons.append("Account shows healthy organic user activity patterns")

        return {
            "agent_name": self.name,
            "verdict": verdict,
            "confidence": confidence,
            "reasons": reasons
        }
