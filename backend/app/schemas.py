from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class ReviewCreate(BaseModel):
    user_id: str
    product_id: str
    review_text: str
    rating: int = Field(..., ge=1, le=5)
    ip_address: Optional[str] = "127.0.0.1"

class ReviewResponse(BaseModel):
    id: str
    user_id: str
    product_id: str
    review_text: str
    rating: int
    created_at: datetime
    ip_address: Optional[str]
    verdict: Optional[str] = None
    confidence_score: Optional[float] = None
    reasons: Optional[List[str]] = []

    class Config:
        from_attributes = True

class AgentOutputSchema(BaseModel):
    agent_name: str
    verdict: str  # REAL, FAKE, SUSPICIOUS
    confidence: float
    reasons: List[str]

class ReviewValidateResponse(BaseModel):
    review_id: str
    final_verdict: str  # APPROVE, REJECT, MANUAL_REVIEW
    confidence_score: float
    reasoning: str
    agent_outputs: Dict[str, AgentOutputSchema]
    is_auto_banned: bool = False

class AdminOverrideRequest(BaseModel):
    review_id: str
    new_verdict: str  # APPROVE, REJECT, MANUAL_REVIEW
    reason: str

class ReviewSimulateRequest(BaseModel):
    user_id: Optional[str] = None
    product_id: Optional[str] = None
    review_text: str
    rating: int = Field(..., ge=1, le=5)
    ip_address: Optional[str] = "127.0.0.1"
    simulate_delay: Optional[bool] = True

class DashboardStats(BaseModel):
    total_reviews: int
    approved_reviews: int
    rejected_reviews: int
    manual_reviews: int
    banned_users: int
    accuracy_rate: float
    savings_usd: float
    recent_flags: List[Dict[str, Any]]
    category_distribution: Dict[str, int]
    daily_trends: List[Dict[str, Any]]

class AuditLogResponse(BaseModel):
    id: int
    user_action: str
    review_id: Optional[str]
    target_user: Optional[str]
    description: str
    timestamp: datetime

    class Config:
        from_attributes = True
