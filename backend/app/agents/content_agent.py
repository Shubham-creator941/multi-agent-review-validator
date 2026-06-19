import re
import math
from sqlalchemy.orm import Session
from .base_agent import BaseAgent
from ..models import Review

# Lexicon lists for checking mismatch or spam
SPAM_KEYWORDS = [
    r"telegram", r"whatsapp", r"bit\.ly", r"tinyurl", r"click here", r"make money",
    r"free cash", r"earn rs", r"earn \$", r"cash back", r"subcribe", r"referral code",
    r"follow link", r"giveaway", r"gift card", r"review exchange", r"promo code"
]

POSITIVE_LEXICON = {"great", "excellent", "perfect", "amazing", "wonderful", "love", "best", "awesome", "good", "satisfied"}
NEGATIVE_LEXICON = {"worst", "terrible", "waste", "broken", "useless", "scam", "cheap", "fake", "hate", "horrible", "damaged"}

def calculate_cosine_similarity(text1: str, text2: str) -> float:
    # Tokenize and clean text into lowercase words
    words1 = re.findall(r"\b\w+\b", text1.lower())
    words2 = re.findall(r"\b\w+\b", text2.lower())
    
    if not words1 or not words2:
        return 0.0
        
    # Build vocabulary
    vocab = set(words1).union(set(words2))
    
    # Vectorize
    vec1 = {w: words1.count(w) for w in vocab}
    vec2 = {w: words2.count(w) for w in vocab}
    
    # Calculate dot product
    dot_product = sum(vec1[w] * vec2[w] for w in vocab)
    
    # Calculate magnitudes
    mag1 = math.sqrt(sum(v**2 for v in vec1.values()))
    mag2 = math.sqrt(sum(v**2 for v in vec2.values()))
    
    if mag1 == 0 or mag2 == 0:
        return 0.0
        
    return dot_product / (mag1 * mag2)

class ContentAgent(BaseAgent):
    def __init__(self):
        super().__init__("Review Content Agent")

    async def analyze(self, review: dict, db: Session) -> dict:
        text = review.get("review_text", "")
        rating = review.get("rating", 3)
        
        reasons = []
        suspicious_factors = 0
        
        # Rule 1: Text length & Quality check
        words = re.findall(r"\b\w+\b", text.lower())
        word_count = len(words)
        
        if word_count == 0:
            return {
                "agent_name": self.name,
                "verdict": "FAKE",
                "confidence": 99.0,
                "reasons": ["Empty review text submitted"]
            }
        
        if word_count < 4:
            suspicious_factors += 20
            reasons.append(f"Extremely short review ({word_count} words): likely generic feedback")
        elif word_count > 300:
            # Overly verbose reviews can sometimes be AI generated copy-pastes
            pass

        # Rule 2: Shouting Check (Excessive Capitalization)
        caps_letters = sum(1 for c in text if c.isupper())
        total_letters = sum(1 for c in text if c.isalpha())
        if total_letters > 10 and (caps_letters / total_letters) > 0.65:
            suspicious_factors += 25
            reasons.append("Excessive capitalization (shouting): might be spammy or bot-generated text")

        # Rule 3: Spam Keyword Check
        has_spam = False
        for pattern in SPAM_KEYWORDS:
            if re.search(pattern, text, re.IGNORECASE):
                suspicious_factors += 50
                has_spam = True
                reasons.append(f"Spam/promotional keyword pattern detected: '{pattern}'")
        
        # Rule 4: Sentiment vs Rating Mismatch
        pos_word_count = sum(1 for w in words if w in POSITIVE_LEXICON)
        neg_word_count = sum(1 for w in words if w in NEGATIVE_LEXICON)
        
        if rating >= 4 and neg_word_count > pos_word_count + 1:
            suspicious_factors += 35
            reasons.append(f"Rating-Sentiment mismatch: Review text contains negative terms ({neg_word_count}) but rating is high ({rating}/5)")
        elif rating <= 2 and pos_word_count > neg_word_count + 1:
            suspicious_factors += 35
            reasons.append(f"Rating-Sentiment mismatch: Review text contains positive terms ({pos_word_count}) but rating is low ({rating}/5)")

        # Rule 5: Copy-Paste Similarity Check against database
        # Compare with existing reviews in the DB
        # Optimize: select reviews of the same product first, fallback to all reviews
        product_id = review.get("product_id")
        existing_reviews = db.query(Review).filter(Review.product_id == product_id).limit(50).all()
        
        highest_sim = 0.0
        matched_review_id = None
        for er in existing_reviews:
            # Skip comparing with itself if it's already written to DB
            if review.get("id") and er.id == review.get("id"):
                continue
            sim = calculate_cosine_similarity(text, er.review_text)
            if sim > highest_sim:
                highest_sim = sim
                matched_review_id = er.id

        if highest_sim > 0.85:
            suspicious_factors += 45
            reasons.append(f"Semantic duplicate review: {highest_sim:.0%} cosine similarity match with review '{matched_review_id}'")
        elif highest_sim > 0.65:
            suspicious_factors += 15
            reasons.append(f"Suspiciously high similarity ({highest_sim:.0%}) to another review in the database")

        # Final Verdict Assessment
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
            reasons.append("Review text reads organically with natural sentiment and length")

        return {
            "agent_name": self.name,
            "verdict": verdict,
            "confidence": confidence,
            "reasons": reasons
        }
