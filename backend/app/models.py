import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    trust_score = Column(Float, default=100.0)
    is_banned = Column(Boolean, default=False)
    ip_address = Column(String, nullable=True)

    reviews = relationship("Review", back_populates="user")
    orders = relationship("Order", back_populates="user")

class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String, index=True)
    price = Column(Float)
    average_rating = Column(Float, default=0.0)
    image_url = Column(String, nullable=True)

    reviews = relationship("Review", back_populates="product")

class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    product_id = Column(String, ForeignKey("products.id"))
    status = Column(String, default="DELIVERED")  # DELIVERED, SHIPPED, CANCELLED
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="orders")

class Review(Base):
    __tablename__ = "reviews"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    product_id = Column(String, ForeignKey("products.id"))
    review_text = Column(Text)
    rating = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    ip_address = Column(String, nullable=True)

    user = relationship("User", back_populates="reviews")
    product = relationship("Product", back_populates="reviews")
    flag = relationship("ReviewFlag", back_populates="review", uselist=False)

class ReviewFlag(Base):
    __tablename__ = "review_flags"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    review_id = Column(String, ForeignKey("reviews.id"))
    verdict = Column(String)  # APPROVE, REJECT, MANUAL_REVIEW
    confidence_score = Column(Float)
    reasons = Column(Text)  # JSON-encoded array of reasons
    agent_outputs = Column(Text)  # JSON-encoded dictionary of agent results
    flagged_at = Column(DateTime, default=datetime.datetime.utcnow)

    review = relationship("Review", back_populates="flag")

class FraudHistory(Base):
    __tablename__ = "fraud_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"))
    review_id = Column(String, ForeignKey("reviews.id"))
    fraud_score = Column(Float)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    action_taken = Column(String)  # BAN, FLAG, NONE

class ReviewExecutionLog(Base):
    __tablename__ = "review_execution_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    review_id = Column(String, ForeignKey("reviews.id"))
    agent_name = Column(String)
    input_snapshot = Column(Text)  # JSON snapshot of inputs
    output = Column(Text)  # JSON snapshot of output
    latency_ms = Column(Integer)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_action = Column(String)  # e.g., ADMIN_OVERRIDE, AUTO_BAN
    review_id = Column(String, nullable=True)
    target_user = Column(String, nullable=True)
    description = Column(Text)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
