from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.enums import ReviewSeverity
from app.schemas import ProposalView, ReviewDraft
from app.services.governance import evaluate_governance


class RiskReviewAgent(BaseAgent):
    name = "RiskReviewAgent"

    def review_proposal(self, db: Session, proposal: ProposalView, patient_state: dict) -> ReviewDraft:
        deterministic_review = evaluate_governance(db, proposal, patient_state)
        if not self.provider.is_live() or deterministic_review.decision != "APPROVE":
            return deterministic_review
        try:
            system_prompt = (
                "You are the mandatory safety review layer for an eldercare coordination system. "
                "Never override deterministic hard-stop rules. Tighten tone, uncertainty, and role appropriateness."
            )
            user_prompt = (
                "Proposal:\n"
                f"{proposal.model_dump_json(indent=2)}\n\n"
                "Patient State:\n"
                f"{patient_state}\n\n"
                "If the proposal is safe, return APPROVE with concise review feedback."
            )
            model_name = getattr(self.provider, "risk_model", None) or "gpt-5.2"
            live_review = self.provider.generate_structured(
                model=model_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=ReviewDraft,
            )
            if live_review.decision == "APPROVE" and live_review.severity == ReviewSeverity.INFORMATIONAL:
                return live_review
        except Exception:
            pass
        return deterministic_review

