import asyncio
import time
import random
import sys
import subprocess
import httpx

# Sample payloads representing both real and fake review variants
TEST_REVIEW_TEXTS = [
    "Perfect product! Extremely durable, fast shipping, and excellent design.",
    "Worst quality ever. Broke in exactly two days. Save your money and buy a competitor's option instead.",
    "Join our promotional telegram channel: bit.ly/spam-gift for a free giveaway!",
    "It works okay. Color was slightly different than the photo, but it performs reasonably well.",
    "Terrible customer service. The packaging arrived crushed and the box was completely empty.",
    "Excellent value for money. Very sturdy build quality and nice material.",
    "Get rich quick today by clicking click here to earn Rs 10000 instantly!",
    "Good, does the job. Would recommend to friends and family."
]

async def simulate_user_session(user_idx: int, client: httpx.AsyncClient) -> list:
    """
    Simulates a single user posting 10 reviews with random pacing delays of 0-300ms.
    Uses pre-created user accounts.
    """
    latencies = []
    user_id = f"load_user_{user_idx}"
    
    for i in range(10):
        # Pace the requests to mimic organic client traffic
        await asyncio.sleep(random.uniform(0.0, 0.3))
        
        payload = {
            "user_id": user_id,
            "product_id": "prod_iphone",
            "review_text": random.choice(TEST_REVIEW_TEXTS),
            "rating": random.choice([1, 2, 3, 4, 5]),
            "ip_address": f"192.168.10.{user_idx}"
        }
        
        start = time.perf_counter()
        try:
            response = await client.post("http://127.0.0.1:8000/api/review/validate", json=payload, timeout=30.0)
            latency = (time.perf_counter() - start) * 1000.0  # in ms
            if response.status_code == 200:
                latencies.append(latency)
            else:
                latencies.append(-1)  # failed request
        except Exception as e:
            # Only print the first few exceptions to avoid log flooding
            if user_idx == 0 and i == 0:
                print(f"Sample connection error details: {repr(e)}")
            latencies.append(-2)  # exception
            
    return latencies

async def run_load_test():
    print("Initializing load test client...")
    
    start_time = time.perf_counter()
    
    # Configure connection pool limits to handle 100 concurrent clients
    limits = httpx.Limits(max_keepalive_connections=50, max_connections=150)
    async with httpx.AsyncClient(limits=limits) as client:
        # Spawn 100 user session tasks in parallel
        tasks = [simulate_user_session(i, client) for i in range(100)]
        
        print("Starting load simulation: 100 concurrent users x 10 reviews each (1000 total)...")
        results = await asyncio.gather(*tasks)
        
    total_time = time.perf_counter() - start_time
    
    # Flatten latencies
    all_latencies = [lat for user_res in results for lat in user_res]
    
    successful_runs = [l for l in all_latencies if l > 0]
    failed_runs = [l for l in all_latencies if l == -1]
    errors = [l for l in all_latencies if l == -2]
    
    print("\n" + "="*50)
    print("                 LOAD TEST REPORT")
    print("="*50)
    print(f"Total reviews processed  : {len(all_latencies)}")
    print(f"Success rate             : {len(successful_runs) / len(all_latencies):.2%}")
    print(f"Failed requests (non-200): {len(failed_runs)}")
    print(f"Exceptions (timeouts)    : {len(errors)}")
    print(f"Total execution time     : {total_time:.2f} seconds")
    
    if successful_runs:
        sorted_runs = sorted(successful_runs)
        n = len(sorted_runs)
        min_val = sorted_runs[0]
        mean_val = sum(successful_runs) / n
        median_val = sorted_runs[n // 2] if n % 2 != 0 else (sorted_runs[n // 2 - 1] + sorted_runs[n // 2]) / 2.0
        p95_val = sorted_runs[int(n * 0.95)] if n > 0 else 0.0
        p99_val = sorted_runs[int(n * 0.99)] if n > 0 else 0.0

        print("-"*50)
        print("LATENCY STATISTICS (Milliseconds)")
        print(f"Minimum latency        : {min_val:.1f} ms")
        print(f"Mean (Average) latency : {mean_val:.1f} ms")
        print(f"Median latency         : {median_val:.1f} ms")
        print(f"95th Percentile (p95)  : {p95_val:.1f} ms")
        print(f"99th Percentile (p99)  : {p99_val:.1f} ms")
    print("="*50)

def pre_create_users_and_orders():
    from app.database import SessionLocal
    from app.models import User, Order
    import datetime
    db = SessionLocal()
    try:
        now = datetime.datetime.utcnow()
        print("Pre-seeding 100 users and orders for load test in SQLite...")
        for i in range(100):
            user_id = f"load_user_{i}"
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                user = User(
                    id=user_id,
                    username=f"load_user_name_{i}",
                    email=f"load_user_{i}@test.com",
                    created_at=now - datetime.timedelta(days=10),
                    trust_score=100.0,
                    is_banned=False
                )
                db.add(user)
                db.flush()
                
            order = db.query(Order).filter(Order.user_id == user_id, Order.product_id == "prod_iphone").first()
            if not order:
                order = Order(
                    id=f"ord_load_{i}",
                    user_id=user_id,
                    product_id="prod_iphone",
                    status="DELIVERED",
                    delivered_at=now - datetime.timedelta(days=2)
                )
                db.add(order)
        db.commit()
        print("Seeding finished successfully.")
    except Exception as e:
        db.rollback()
        print(f"Seeding failed: {str(e)}")
    finally:
        db.close()

def main():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    is_running = False
    try:
        s.bind(("127.0.0.1", 8000))
        s.close()
    except socket.error:
        is_running = True
        print("Port 8000 is already in use. Assuming FastAPI server is running...")

    server_process = None
    log_file = None
    if not is_running:
        print("Starting background FastAPI server for load test...")
        # Start the FastAPI server using the virtual environment python
        python_exe = sys.executable
        log_file = open("C:/Users/priya/.gemini/antigravity-ide/scratch/multi-agent-review-validator/backend/uvicorn.log", "w")
        server_process = subprocess.Popen(
            [python_exe, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"],
            cwd="C:/Users/priya/.gemini/antigravity-ide/scratch/multi-agent-review-validator/backend",
            stdout=log_file,
            stderr=log_file
        )
        
        # Wait for server to boot
        time.sleep(3)
        
        # Check if server process crashed immediately
        if server_process.poll() is not None:
            print("FastAPI server failed to start immediately.")
            return

    # Pre-create users and orders before client load test
    pre_create_users_and_orders()
        
    try:
        # Run async load test loop
        asyncio.run(run_load_test())
    finally:
        if server_process:
            print("Stopping background FastAPI server...")
            server_process.terminate()
            server_process.wait()
            print("Server shutdown completed.")
        if log_file:
            log_file.close()

if __name__ == "__main__":
    main()
