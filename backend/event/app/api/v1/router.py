from fastapi import APIRouter
from app.api.v1.endpoints import events

router = APIRouter()

router.include_router(events.router)
