import datetime
import uuid
import json
from sqlalchemy.orm import Session
from .database import engine, SessionLocal, Base
from .models import User, Product, Order, Review, ReviewFlag, FraudHistory, AuditLog, ReviewExecutionLog

def seed_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Seeding database...")

        # 1. Seed Products
        products = [
            Product(id="prod_iphone", name="iPhone 15 Pro Max (256GB)", category="Electronics", price=1299.00, average_rating=4.7),
            Product(id="prod_headphones", name="Noise Cancelling Wireless Headphones", category="Electronics", price=199.99, average_rating=4.2),
            Product(id="prod_tshirt", name="Premium Cotton Crewneck T-Shirt", category="Fashion", price=25.00, average_rating=4.5),
            Product(id="prod_bottle", name="Insulated Stainless Steel Water Bottle", category="Home & Living", price=34.99, average_rating=4.8),
            Product(id="prod_watch", name="Fitness Tracker Smartwatch", category="Electronics", price=89.50, average_rating=3.9),
            Product(id="prod_backpack", name="Waterproof Travel Backpack", category="Fashion", price=49.99, average_rating=4.6)
        ]
        for p in products:
            db.add(p)

        # 2. Seed Users
        now = datetime.datetime.utcnow()
        users = [
            # Trustworthy established users
            User(id="usr_priya", username="TechReviewer_Priya", email="priya@marketplace.com", created_at=now - datetime.timedelta(days=730), trust_score=100.0, is_banned=False, ip_address="192.168.1.10"),
            User(id="usr_amit", username="Amit_Sharma_Del", email="amit@marketplace.com", created_at=now - datetime.timedelta(days=450), trust_score=95.0, is_banned=False, ip_address="192.168.1.11"),
            User(id="usr_john", username="JohnDoeReviews", email="john@marketplace.com", created_at=now - datetime.timedelta(days=120), trust_score=85.0, is_banned=False, ip_address="203.0.113.5"),
            # Suspicious/new users
            User(id="usr_bot_01", username="user_12345_new", email="bot1@spam.com", created_at=now - datetime.timedelta(hours=10), trust_score=50.0, is_banned=False, ip_address="198.51.100.22"),
            User(id="usr_bot_02", username="bot_promoter_99", email="bot2@spam.com", created_at=now - datetime.timedelta(hours=2), trust_score=10.0, is_banned=False, ip_address="198.51.100.23"),
            User(id="usr_competitor", username="anonymous_buyer_11", email="comp@competitor.com", created_at=now - datetime.timedelta(days=1), trust_score=35.0, is_banned=False, ip_address="185.220.101.5"),
            # Dynamic banned user
            User(id="usr_spammer", username="spam_king_999", email="spammer@spam.com", created_at=now - datetime.timedelta(days=5), trust_score=0.0, is_banned=True, ip_address="103.24.11.89")
        ]
        for u in users:
            db.add(u)

        # Commit so we can link orders and reviews
        db.commit()

        # 3. Seed Orders (Verified Purchases)
        orders = [
            # Priya bought iPhone & Headphones (delivered)
            Order(id="ord_001", user_id="usr_priya", product_id="prod_iphone", status="DELIVERED", delivered_at=now - datetime.timedelta(days=10), created_at=now - datetime.timedelta(days=12)),
            Order(id="ord_002", user_id="usr_priya", product_id="prod_headphones", status="DELIVERED", delivered_at=now - datetime.timedelta(days=4), created_at=now - datetime.timedelta(days=5)),
            
            # Amit bought Premium Cotton T-shirt & Smartwatch
            Order(id="ord_003", user_id="usr_amit", product_id="prod_tshirt", status="DELIVERED", delivered_at=now - datetime.timedelta(days=15), created_at=now - datetime.timedelta(days=16)),
            Order(id="ord_004", user_id="usr_amit", product_id="prod_watch", status="DELIVERED", delivered_at=now - datetime.timedelta(days=3), created_at=now - datetime.timedelta(days=4)),
            
            # John bought Water bottle
            Order(id="ord_005", user_id="usr_john", product_id="prod_bottle", status="DELIVERED", delivered_at=now - datetime.timedelta(days=2), created_at=now - datetime.timedelta(days=3)),
            
            # Suspicious competitor ordered backpack but CANCELLED it
            Order(id="ord_006", user_id="usr_competitor", product_id="prod_backpack", status="CANCELLED", delivered_at=None, created_at=now - datetime.timedelta(days=1)),
            
            # Spammer user has NO orders
        ]
        for o in orders:
            db.add(o)
        
        db.commit()

        # 4. Seed Reviews and Flags (Historical logs)
        # We will write these manually so they have realistic agent outputs
        historical_reviews = [
            # Real review from Priya
            {
                "id": "rev_001",
                "user_id": "usr_priya",
                "product_id": "prod_iphone",
                "text": "Great quality! The battery lasts 10+ hours easily. Extremely fast performance. Highly recommend this iPhone.",
                "rating": 5,
                "created_at": now - datetime.timedelta(days=8),
                "ip": "192.168.1.10",
                "verdict": "APPROVE",
                "score": 96.50,
                "reasons": ["Reviewer Credibility Agent: REAL (95% confidence)", "Review Content Agent: REAL (92% confidence)", "Purchase Authenticity Agent: REAL (99% confidence)", "Final Score: 96.5/100"],
                "agent_outputs": {
                    "Reviewer Credibility Agent": {"agent_name": "Reviewer Credibility Agent", "verdict": "REAL", "confidence": 95.0, "reasons": ["Account age: 730 days old", "Healthy rating history"]},
                    "Review Content Agent": {"agent_name": "Review Content Agent", "verdict": "REAL", "confidence": 92.0, "reasons": ["Natural syntax structure", "Good length"]},
                    "Purchase Authenticity Agent": {"agent_name": "Purchase Authenticity Agent", "verdict": "REAL", "confidence": 99.0, "reasons": ["Verified Purchase: delivered 2 days prior"]}
                }
            },
            # Real review from Amit
            {
                "id": "rev_002",
                "user_id": "usr_amit",
                "product_id": "prod_tshirt",
                "text": "Fits nicely. Very soft material. Stitching is superb. Worth the price.",
                "rating": 5,
                "created_at": now - datetime.timedelta(days=14),
                "ip": "192.168.1.11",
                "verdict": "APPROVE",
                "score": 95.00,
                "reasons": ["Reviewer Credibility Agent: REAL (95% confidence)", "Review Content Agent: REAL (90% confidence)", "Purchase Authenticity Agent: REAL (99% confidence)", "Final Score: 95.0/100"],
                "agent_outputs": {
                    "Reviewer Credibility Agent": {"agent_name": "Reviewer Credibility Agent", "verdict": "REAL", "confidence": 95.0, "reasons": ["Established user", "Consistent rating distribution"]},
                    "Review Content Agent": {"agent_name": "Review Content Agent", "verdict": "REAL", "confidence": 90.0, "reasons": ["Organic text length"]},
                    "Purchase Authenticity Agent": {"agent_name": "Purchase Authenticity Agent", "verdict": "REAL", "confidence": 99.0, "reasons": ["Verified Purchase"]}
                }
            },
            # Competitor negative spam attack (Fake)
            {
                "id": "rev_003",
                "user_id": "usr_competitor",
                "product_id": "prod_backpack",
                "text": "TERRIBLE PRODUCT!!! Broke on the first day. The zipper is cheap garbage. Save your money, do not buy!",
                "rating": 1,
                "created_at": now - datetime.timedelta(hours=18),
                "ip": "185.220.101.5",
                "verdict": "REJECT",
                "score": 12.00,
                "reasons": [
                    "Reviewer Credibility Agent: SUSPICIOUS (60% confidence)", 
                    "Review Content Agent: SUSPICIOUS (70% confidence)", 
                    "Purchase Authenticity Agent: FAKE (90% confidence)",
                    "Penalties applied:",
                    " - Order was cancelled before delivery [-30]",
                    "Final Score: 12.0/100"
                ],
                "agent_outputs": {
                    "Reviewer Credibility Agent": {"agent_name": "Reviewer Credibility Agent", "verdict": "SUSPICIOUS", "confidence": 60.0, "reasons": ["New account: created 1 day ago"]},
                    "Review Content Agent": {"agent_name": "Review Content Agent", "verdict": "SUSPICIOUS", "confidence": 70.0, "reasons": ["Excessive capitalization"]},
                    "Purchase Authenticity Agent": {"agent_name": "Purchase Authenticity Agent", "verdict": "FAKE", "confidence": 90.0, "reasons": ["Order cancelled by buyer"]}
                }
            },
            # Spam promotion review (Fake)
            {
                "id": "rev_004",
                "user_id": "usr_bot_02",
                "product_id": "prod_iphone",
                "text": "Earn Rs 5000 daily! Join our telegram channel now: tinyurl.com/fake-cash. Guaranteed payout immediately!",
                "rating": 5,
                "created_at": now - datetime.timedelta(hours=1),
                "ip": "198.51.100.23",
                "verdict": "REJECT",
                "score": 5.00,
                "reasons": [
                    "Reviewer Credibility Agent: FAKE (90% confidence)",
                    "Review Content Agent: FAKE (98% confidence)",
                    "Purchase Authenticity Agent: FAKE (99% confidence)",
                    "Penalties applied:",
                    " - Spam/promotional content detected [-30]",
                    " - No verified purchase record found [-40]",
                    "Final Score: 5.0/100"
                ],
                "agent_outputs": {
                    "Reviewer Credibility Agent": {"agent_name": "Reviewer Credibility Agent", "verdict": "FAKE", "confidence": 90.0, "reasons": ["Account age: created today", "Bot-like username"]},
                    "Review Content Agent": {"agent_name": "Review Content Agent", "verdict": "FAKE", "confidence": 98.0, "reasons": ["Promotional links found (Telegram, Tinyurl)"]},
                    "Purchase Authenticity Agent": {"agent_name": "Purchase Authenticity Agent", "verdict": "FAKE", "confidence": 99.0, "reasons": ["No purchase record found"]}
                }
            },
            # Suspicious borderline review (Manual Review)
            {
                "id": "rev_005",
                "user_id": "usr_john",
                "product_id": "prod_bottle",
                "text": "The bottle keeps water cold but the color started peeling. Rating it lower, hope seller fixes.",
                "rating": 2,
                "created_at": now - datetime.timedelta(days=1),
                "ip": "203.0.113.5",
                "verdict": "MANUAL_REVIEW",
                "score": 55.00,
                "reasons": [
                    "Reviewer Credibility Agent: REAL (85% confidence)",
                    "Review Content Agent: SUSPICIOUS (60% confidence)",
                    "Purchase Authenticity Agent: REAL (90% confidence)",
                    "Final Score: 55.0/100"
                ],
                "agent_outputs": {
                    "Reviewer Credibility Agent": {"agent_name": "Reviewer Credibility Agent", "verdict": "REAL", "confidence": 85.0, "reasons": ["Established history"]},
                    "Review Content Agent": {"agent_name": "Review Content Agent", "verdict": "SUSPICIOUS", "confidence": 60.0, "reasons": ["Slightly negative tone but verified purchase"]},
                    "Purchase Authenticity Agent": {"agent_name": "Purchase Authenticity Agent", "verdict": "REAL", "confidence": 90.0, "reasons": ["Verified Order Delivered"]}
                }
            }
        ]

        # Seed reviews
        for hr in historical_reviews:
            # 1. Create Review
            review_obj = Review(
                id=hr["id"],
                user_id=hr["user_id"],
                product_id=hr["product_id"],
                review_text=hr["text"],
                rating=hr["rating"],
                created_at=hr["created_at"],
                ip_address=hr["ip"]
            )
            db.add(review_obj)
            db.flush()

            # 2. Create ReviewFlag
            flag = ReviewFlag(
                review_id=hr["id"],
                verdict=hr["verdict"],
                confidence_score=hr["score"],
                reasons=json.dumps(hr["reasons"]),
                agent_outputs=json.dumps(hr["agent_outputs"]),
                flagged_at=hr["created_at"]
            )
            db.add(flag)

            # 3. Create FraudHistory entry
            f_score = round(100.0 - hr["score"], 2)
            fh = FraudHistory(
                user_id=hr["user_id"],
                review_id=hr["id"],
                fraud_score=f_score,
                timestamp=hr["created_at"],
                action_taken="BAN" if hr["verdict"] == "REJECT" and hr["user_id"] == "usr_spammer" else "FLAG" if hr["verdict"] in ("REJECT", "MANUAL_REVIEW") else "NONE"
            )
            db.add(fh)

            # 4. Create Execution Logs for traceability
            for agent_name, agent_out in hr["agent_outputs"].items():
                # Inject dummy latency
                latency = 120 if "Content" in agent_name else 45 if "Credibility" in agent_name else 80
                
                log = ReviewExecutionLog(
                    review_id=hr["id"],
                    agent_name=agent_name,
                    input_snapshot=json.dumps({
                        "id": hr["id"],
                        "user_id": hr["user_id"],
                        "product_id": hr["product_id"],
                        "review_text": hr["text"],
                        "rating": hr["rating"],
                        "created_at": str(hr["created_at"]),
                        "ip_address": hr["ip"]
                    }),
                    output=json.dumps(agent_out),
                    latency_ms=latency
                )
                db.add(log)

        # 5. Add a historical ban entry for the user_spammer
        spammer_review = Review(
            id="rev_spam_old",
            user_id="usr_spammer",
            product_id="prod_watch",
            review_text="BUY CHEAP COIN NOW!!! fast cash payout link at spam.com",
            rating=5,
            created_at=now - datetime.timedelta(days=2),
            ip_address="103.24.11.89"
        )
        db.add(spammer_review)
        db.flush()

        db.add(ReviewFlag(
            review_id="rev_spam_old",
            verdict="REJECT",
            confidence_score=5.0,
            reasons=json.dumps(["Promotional spam content"]),
            agent_outputs=json.dumps({}),
            flagged_at=now - datetime.timedelta(days=2)
        ))
        
        db.add(FraudHistory(
            user_id="usr_spammer",
            review_id="rev_spam_old",
            fraud_score=95.0,
            timestamp=now - datetime.timedelta(days=2),
            action_taken="BAN"
        ))

        # Add Audit Logs for dashboard history
        audits = [
            AuditLog(user_action="AUTO_BAN", target_user="usr_spammer", review_id="rev_spam_old", description="User 'usr_spammer' banned after posting high-risk review campaign (Avg fraud score 95.0%).", timestamp=now - datetime.timedelta(days=2)),
            AuditLog(user_action="SYSTEM_FLAG", target_user="usr_bot_02", review_id="rev_004", description="Review 'rev_004' flagged as REJECT due to promotional spam patterns.", timestamp=now - datetime.timedelta(hours=1)),
            AuditLog(user_action="ADMIN_OVERRIDE", review_id="rev_005", target_user="usr_john", description="Moderator human override: Verdict on 'rev_005' confirmed as MANUAL_REVIEW to monitor user color-peeling returns.", timestamp=now - datetime.timedelta(minutes=30))
        ]
        for a in audits:
            db.add(a)

        db.commit()
        print("Database seeded successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {str(e)}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
