from typing import List, Dict, Any

def aggregate_decisions(agent_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Combines outputs from the three agents:
    - Weights: Credibility (40%), Content (30%), Purchase (30%)
    - Penalties:
        - No purchase: -40
        - New account (< 7 days): -25
        - Spam text detected: -30
    Formula:
        final_score = max(0, min(100, weighted_score - abs(penalty_score)))
    Verdict Mapping:
        final_score >= 70 -> APPROVE
        40 <= final_score < 70 -> MANUAL_REVIEW
        final_score < 40 -> REJECT
    
    Safe Mode Trigger:
    If any agent fails or times out, switch to Fallback Safe Mode and force MANUAL_REVIEW.
    """
    agent_outputs_dict = {}
    credibility_score = 100.0
    content_score = 100.0
    purchase_score = 100.0
    
    penalties = 0
    penalty_reasons = []
    
    fallback_active = False
    fallback_reasons = []

    for res in agent_results:
        name = res["agent_name"]
        agent_outputs_dict[name] = res
        
        # Check if agent experienced fallback/error
        reasons_str = " ".join(res.get("reasons", [])).lower()
        if "timed out" in reasons_str or "internal error" in reasons_str or "thread execution failure" in reasons_str:
            fallback_active = True
            fallback_reasons.append(f"{name} failed/timed out")

        # Map agent results to scores [0-100]
        # High score = authentic, Low score = suspicious/fake
        verdict = res["verdict"]
        confidence = res["confidence"]
        
        if verdict == "REAL":
            score = confidence
        elif verdict == "FAKE":
            score = 100.0 - confidence
        else:  # SUSPICIOUS
            score = 50.0

        if name == "Reviewer Credibility Agent":
            credibility_score = score
            # Check for New Account penalty
            if any("new account" in r.lower() or "brand new" in r.lower() for r in res.get("reasons", [])):
                penalties += 25
                penalty_reasons.append("New account (< 7 days) detected [-25]")
                
        elif name == "Review Content Agent":
            content_score = score
            # Check for Spam text penalty
            if any("spam" in r.lower() or "promotional" in r.lower() for r in res.get("reasons", [])):
                penalties += 30
                penalty_reasons.append("Spam/promotional content detected [-30]")
                
        elif name == "Purchase Authenticity Agent":
            purchase_score = score
            # Check for No Purchase penalty
            if any("no purchase record" in r.lower() or "unregistered" in r.lower() for r in res.get("reasons", [])):
                penalties += 40
                penalty_reasons.append("No verified purchase record found [-40]")

    # Weighted Score calculation
    weighted_score = (credibility_score * 0.40) + (content_score * 0.30) + (purchase_score * 0.30)
    
    # Apply penalties
    final_score = weighted_score - abs(penalties)
    final_score = max(0.0, min(100.0, final_score))

    # Fallback Safe Mode Enforcement
    if fallback_active:
        verdict = "MANUAL_REVIEW"
        reasoning = (
            "FALLBACK SAFE MODE ACTIVE: " + ", ".join(fallback_reasons) + ". "
            "Review flagged for manual moderation to guarantee security."
        )
    else:
        # Standard verdict mapping
        if final_score >= 70:
            verdict = "APPROVE"
            reasoning = "Review approved. Passed credibility, content authenticity, and purchase verification."
        elif final_score >= 40:
            verdict = "MANUAL_REVIEW"
            reasoning = "Review flagged for manual review due to borderline risk metrics."
        else:
            verdict = "REJECT"
            reasoning = "Review rejected due to high probability of fraud / malicious patterns."

    # Compile explanations for explainability
    explanation_bullets = []
    for res in agent_results:
        bullet = f"{res['agent_name']}: {res['verdict']} ({res['confidence']:.0f}% confidence)"
        explanation_bullets.append(bullet)
        
    if penalty_reasons:
        explanation_bullets.append("Penalties applied:")
        for pr in penalty_reasons:
            explanation_bullets.append(f" - {pr}")

    explanation_bullets.append(f"Final Score: {final_score:.1f}/100 (Thresholds: <40 Reject, >=70 Approve)")
    
    if fallback_active:
        explanation_bullets.append("⚠️ System fell back to rule-based safe mode due to agent timing/exceptions.")

    reasoning_explanation = "\n".join(explanation_bullets)

    return {
        "final_verdict": verdict,
        "confidence_score": round(final_score, 2),
        "reasoning": reasoning,
        "explanation": reasoning_explanation,
        "agent_outputs": agent_outputs_dict,
        "is_fallback": fallback_active
    }
