def normalize_confidence(agent_name: str, verdict: str, raw_confidence: float) -> float:
    """
    Normalizes confidence scores across different agents to prevent bias.
    - Purchase agent is highly objective: keep confidence high.
    - Credibility agent relies on account parameters: medium reliability.
    - Content agent is based on text analysis/lexicons: apply slight damping to prevent noise dominance.
    """
    # Clamp raw confidence to [0, 100]
    clamped = max(0.0, min(100.0, float(raw_confidence)))

    if agent_name == "Purchase Authenticity Agent":
        # Purchase status is factual. No damping.
        normalized = clamped
    elif agent_name == "Reviewer Credibility Agent":
        # Credibility relies on heuristics. Apply minor scaling.
        normalized = clamped * 0.95
    elif agent_name == "Review Content Agent":
        # Content NLP analysis can have high noise. Dampen the signal slightly.
        # This prevents aggressive sentiment flags from dominating the verdict.
        normalized = clamped * 0.85
    else:
        normalized = clamped

    return round(normalized, 2)
