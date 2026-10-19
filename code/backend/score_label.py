def inspection_score_label(score: int) -> str:
    """Return a short label for an inspection score from 0 to 100."""
    if score < 0 or score > 100:
        raise ValueError("score must be between 0 and 100")
    if score >= 90:
        return "good"
    if score >= 70:
        return "fair"
    return "poor"
