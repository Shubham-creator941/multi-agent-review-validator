import asyncio
import logging
from sqlalchemy.orm import Session
from .agents.credibility_agent import CredibilityAgent
from .agents.content_agent import ContentAgent
from .agents.purchase_agent import PurchaseAgent
from .utils.confidence_normalizer import normalize_confidence

logger = logging.getLogger(__name__)

# Instantiate global agent instances
credibility_agent = CredibilityAgent()
content_agent = ContentAgent()
purchase_agent = PurchaseAgent()

async def run_agent_with_timeout(agent, review: dict) -> dict:
    """
    Runs an individual agent with a strict 1.5-second timeout.
    Returns a fallback configuration if the agent times out or raises an exception.
    Uses a clean database session local connection to prevent session sharing locks.
    """
    import time
    from .database import SessionLocal
    start_time = time.perf_counter()
    
    # Yield control to event loop to allow socket processing
    await asyncio.sleep(0.001)
    
    local_db = SessionLocal()
    try:
        # Wrap agent analysis with 1.5s timeout
        result = await asyncio.wait_for(agent.analyze(review, local_db), timeout=1.5)
        
        # Apply confidence normalization
        raw_conf = result.get("confidence", 50.0)
        result["confidence"] = normalize_confidence(agent.name, result["verdict"], raw_conf)
        
        duration = int((time.perf_counter() - start_time) * 1000)
        result["latency_ms"] = duration
        return result
        
    except asyncio.TimeoutError:
        logger.error(f"Agent {agent.name} timed out after 1.5s.")
        duration = int((time.perf_counter() - start_time) * 1000)
        return {
            "agent_name": agent.name,
            "verdict": "SUSPICIOUS",
            "confidence": 50.0,
            "reasons": ["Agent execution timed out (exceeded 1.5s)"],
            "latency_ms": duration
        }
    except Exception as e:
        logger.exception(f"Agent {agent.name} failed with exception: {str(e)}")
        duration = int((time.perf_counter() - start_time) * 1000)
        return {
            "agent_name": agent.name,
            "verdict": "SUSPICIOUS",
            "confidence": 50.0,
            "reasons": [f"Agent encountered internal error: {str(e)}"],
            "latency_ms": duration
        }
    finally:
        local_db.close()

async def validate_review(review: dict, db: Session = None) -> list:
    """
    Orchestrates parallel execution of the three credibility agents.
    Uses asyncio.gather with return_exceptions=True to protect orchestrator thread execution.
    """
    agents = [credibility_agent, content_agent, purchase_agent]
    
    # Run all agents in parallel (each manages its own SessionLocal internally)
    results = await asyncio.gather(
        *[run_agent_with_timeout(agent, review) for agent in agents],
        return_exceptions=True
    )
    
    # Process results, handling any unexpected raw exception instances returned from gather
    processed_results = []
    for idx, res in enumerate(results):
        agent_name = agents[idx].name
        if isinstance(res, Exception):
            logger.error(f"Critical unhandled exception in gather for {agent_name}: {str(res)}")
            processed_results.append({
                "agent_name": agent_name,
                "verdict": "SUSPICIOUS",
                "confidence": 50.0,
                "reasons": ["Critical thread execution failure in orchestrator"]
            })
        else:
            processed_results.append(res)
            
    return processed_results
