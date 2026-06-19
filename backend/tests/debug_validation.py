import traceback
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, Base, engine

def test_debug():
    # Make sure tables exist
    Base.metadata.create_all(bind=engine)
    
    client = TestClient(app)
    
    payload = {
        "user_id": "usr_priya",
        "product_id": "prod_iphone",
        "review_text": "This is a great iPhone review, battery is amazing!",
        "rating": 5,
        "ip_address": "127.0.0.1"
    }
    
    print("Sending validation request via TestClient...")
    try:
        response = client.post("/api/review/validate", json=payload)
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.text}")
    except Exception as e:
        print("Exception occurred during request:")
        traceback.print_exc()

if __name__ == "__main__":
    test_debug()
