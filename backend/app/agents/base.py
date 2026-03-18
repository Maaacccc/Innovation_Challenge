from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.ai.provider import BaseLLMProvider
from app.schemas import PatientStateView, ProposalDraft


@dataclass
class TaskContext:
    patient_state: PatientStateView
    trigger_event: dict[str, Any] | None = None
    task_hints: list[str] = field(default_factory=list)
    encounter_context_id: str | None = None
    now: datetime = field(default_factory=datetime.utcnow)


class BaseAgent:
    name = "BaseAgent"

    def __init__(self, provider: BaseLLMProvider) -> None:
        self.provider = provider

    def generate_proposal(self, patient_state: PatientStateView, task_context: TaskContext) -> ProposalDraft | None:
        raise NotImplementedError

