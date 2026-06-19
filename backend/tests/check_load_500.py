import asyncio
import traceback
import httpx
from app.main import app
from app.database import Base, engine

async def main():
    Base.metadata.create_all(bind=engine)

    # In httpx v0.28+, we must pass the app via ASGITransport
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payloads = [
            {
                "user_id": f"usr_diag_{i}",
                "product_id": "prod_iphone",
                "review_text": f"This is diagnostic review {i}!",
                "rating": 5
            }
            for i in range(5)
        ]
        
        print("Sending 5 concurrent in-process requests...")
        tasks = [
            client.post("/api/review/validate", json=payload)
            for payload in payloads
        ]
        
        try:
            responses = await asyncio.gather(*tasks)
            for idx, r in enumerate(responses):
                print(f"Request {idx} -> Status: {r.status_code}")
                print(f"Response body: {r.text}")
        except Exception as e:
            print("Concurrent request crashed:")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
