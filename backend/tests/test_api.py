import pytest
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.models import User, Product, Order, Review, ReviewFlag

# Configure separate SQLite test file
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_api.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        # Pre-seed minimal required product
        p = Product(id="prod_test_api", name="Test API Product", category="Electronics", price=100.0)
        db.add(p)
        db.commit()
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=engine)

# Override get_db dependency
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def test_validate_review_new_user_no_purchase():
    payload = {
        "user_id": "usr_new_test_api",
        "product_id": "prod_test_api",
        "review_text": "Awesome product, must buy!",
        "rating": 5,
        "ip_address": "127.0.0.1"
    }
    response = client.post("/api/review/validate", json=payload)
    assert response.status_code == 200
    json_data = response.json()
    assert "review_id" in json_data
    # Should flag as MANUAL_REVIEW or REJECT due to no purchase (-40) and new account (-25) penalties
    assert json_data["final_verdict"] in ("REJECT", "MANUAL_REVIEW")
    assert json_data["is_auto_banned"] is False

def test_admin_override():
    # 1. First post a review to override
    payload = {
        "user_id": "usr_override_user",
        "product_id": "prod_test_api",
        "review_text": "Average product, average packaging.",
        "rating": 3,
        "ip_address": "127.0.0.1"
    }
    post_res = client.post("/api/review/validate", json=payload)
    review_id = post_res.json()["review_id"]
    
    # 2. Perform override
    override_payload = {
        "review_id": review_id,
        "new_verdict": "APPROVE",
        "reason": "Verified manually by admin review team"
    }
    override_res = client.post("/api/admin/override", json=override_payload)
    assert override_res.status_code == 200
    assert override_res.json()["status"] == "success"
    
    # 3. Retrieve and assert new status
    reviews_res = client.get("/api/reviews")
    matched_review = next((r for r in reviews_res.json() if r["id"] == review_id), None)
    assert matched_review is not None
    assert matched_review["verdict"] == "APPROVE"

def test_dashboard_stats():
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    stats = res.json()
    assert "total_reviews" in stats
    assert "savings_usd" in stats
    assert "daily_trends" in stats

def test_audit_logs():
    res = client.get("/api/audit/logs")
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) >= 1
    assert any("ADMIN_OVERRIDE" in l["user_action"] for l in logs)
