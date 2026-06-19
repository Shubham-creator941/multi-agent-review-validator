import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import User, Product, Order, Review
from app.agents.credibility_agent import CredibilityAgent
from app.agents.content_agent import ContentAgent
from app.agents.purchase_agent import PurchaseAgent

# Create in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.mark.asyncio
async def test_credibility_agent_banned_user(db_session):
    agent = CredibilityAgent()
    
    # Setup: Create a banned user
    banned_user = User(
        id="usr_banned_test",
        username="banned_user",
        email="banned@test.com",
        trust_score=0.0,
        is_banned=True
    )
    db_session.add(banned_user)
    db_session.commit()
    
    review_payload = {"user_id": "usr_banned_test", "review_text": "Nice!", "rating": 5}
    
    result = await agent.analyze(review_payload, db_session)
    assert result["verdict"] == "FAKE"
    assert result["confidence"] == 100.0
    assert "ban list" in result["reasons"][0]

@pytest.mark.asyncio
async def test_content_agent_spam_detection(db_session):
    agent = ContentAgent()
    
    review_payload = {
        "user_id": "usr_test",
        "review_text": "Join our telegram channel bit.ly/giveaway for free cash!",
        "rating": 5
    }
    
    result = await agent.analyze(review_payload, db_session)
    assert result["verdict"] in ("FAKE", "SUSPICIOUS")
    assert any("spam" in r.lower() or "telegram" in r.lower() for r in result["reasons"])

@pytest.mark.asyncio
async def test_purchase_agent_no_purchase(db_session):
    agent = PurchaseAgent()
    
    review_payload = {
        "user_id": "usr_test_no_buy",
        "product_id": "prod_phone_test",
        "review_text": "Bad battery life, do not buy this garbage!",
        "rating": 1
    }
    
    result = await agent.analyze(review_payload, db_session)
    assert result["verdict"] == "FAKE"
    assert any("no purchase" in r.lower() for r in result["reasons"])

@pytest.mark.asyncio
async def test_purchase_agent_verified_purchase(db_session):
    agent = PurchaseAgent()
    
    # Setup: create user, product, order
    user = User(id="usr_buyer", username="buyer", email="buyer@test.com", created_at=datetime.datetime.utcnow())
    product = Product(id="prod_test", name="Test Product", price=10.0)
    order = Order(
        id="ord_test", 
        user_id="usr_buyer", 
        product_id="prod_test", 
        status="DELIVERED", 
        delivered_at=datetime.datetime.utcnow() - datetime.timedelta(days=2)
    )
    db_session.add_all([user, product, order])
    db_session.commit()
    
    review_payload = {
        "user_id": "usr_buyer",
        "product_id": "prod_test",
        "review_text": "Very cool product, highly functional and durable.",
        "rating": 5,
        "created_at": datetime.datetime.utcnow()
    }
    
    result = await agent.analyze(review_payload, db_session)
    assert result["verdict"] == "REAL"
    assert any("verified purchase" in r.lower() for r in result["reasons"])
