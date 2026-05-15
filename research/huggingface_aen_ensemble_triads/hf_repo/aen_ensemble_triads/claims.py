from __future__ import annotations

from typing import Any


def claim_status_for(profile: dict[str, Any]) -> dict[str, Any]:
    status = dict(profile.get("claim_status") or {})
    return {
        "profile_id": str(profile.get("profile_id") or profile.get("_selected_profile") or ""),
        "blind_benchmark_eligible": status.get("blind_benchmark_eligible", False),
        "answer_aware": bool(status.get("answer_aware", False)),
        "public_score_claim_allowed": status.get("public_score_claim_allowed", False),
        "notes": str(status.get("notes", "")),
    }


def validate_claim_boundary(profile: dict[str, Any]) -> None:
    status = claim_status_for(profile)
    if status["answer_aware"] and status["blind_benchmark_eligible"] is True:
        raise ValueError("Invalid profile: answer-aware profiles cannot be blind benchmark eligible.")
