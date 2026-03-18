from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    PATIENT = "patient"
    CAREGIVER = "caregiver"
    NURSE = "nurse"
    CLINICIAN = "clinician"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class RecipientType(str, Enum):
    PATIENT = "patient"
    CAREGIVER = "caregiver"
    NURSE = "nurse"
    CLINICIAN = "clinician"
    INTERNAL_QUEUE = "internal_queue"


class ProposalType(str, Enum):
    REMINDER = "reminder"
    CHECK_IN = "check_in"
    EDUCATION = "education"
    CAREGIVER_TASK_CARD = "caregiver_task_card"
    CLINICIAN_SUMMARY = "clinician_summary"
    ESCALATION_REQUEST = "escalation_request"
    TRIAGE_NOTE = "triage_note"
    FOLLOW_UP_TASK = "follow_up_task"


class ProposalStatus(str, Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REVISED = "revised"
    REROUTED = "rerouted"
    ESCALATED = "escalated"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    DELIVERED = "delivered"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewDecisionType(str, Enum):
    APPROVE = "APPROVE"
    REVISE = "REVISE"
    REROUTE = "REROUTE"
    ESCALATE = "ESCALATE"
    REJECT_AND_REGENERATE = "REJECT_AND_REGENERATE"


class ReviewSeverity(str, Enum):
    INFORMATIONAL = "informational"
    CAUTION = "caution"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class EscalationStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class HumanReviewStatus(str, Enum):
    OPEN = "open"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class EventCategory(str, Enum):
    PHYSIOLOGICAL = "physiological"
    BEHAVIORAL = "behavioral"
    AMBIENT = "ambient"
    CONVERSATIONAL = "conversational"


class DeliveryChannel(str, Enum):
    IN_APP = "in_app"

