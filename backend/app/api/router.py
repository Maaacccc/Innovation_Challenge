from __future__ import annotations

from fastapi import APIRouter

from app.api import audit, auth, escalations, events, human_review, metrics, orchestrations, patients, proposals, reviews


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(events.router)
api_router.include_router(patients.router)
api_router.include_router(orchestrations.router)
api_router.include_router(proposals.router)
api_router.include_router(reviews.router)
api_router.include_router(escalations.router)
api_router.include_router(audit.router)
api_router.include_router(human_review.router)
api_router.include_router(metrics.router)

