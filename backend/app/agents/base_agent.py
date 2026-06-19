from sqlalchemy.orm import Session

class BaseAgent:
    def __init__(self, name: str):
        self.name = name

    async def analyze(self, review: dict, db: Session) -> dict:
        """
        Analyze a review and return details.
        Output format MUST be:
        {
            "agent_name": str,
            "verdict": "REAL" | "FAKE" | "SUSPICIOUS",
            "confidence": 0-100 (float),
            "reasons": list[str]
        }
        """
        raise NotImplementedError("Each agent must implement the analyze method.")
