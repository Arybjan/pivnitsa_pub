from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api import router
from app.config import get_settings
from app.database import get_db

app = FastAPI(title="Pivnitsa Venue Service", version="1.0.0")
# Токен передаётся в заголовке Authorization, поэтому allow_credentials не нужен
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "venue-service"}


@app.get("/health/ready", tags=["Health"])
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT id FROM halls LIMIT 1"))
    except SQLAlchemyError:
        raise HTTPException(
            503, "Database is unavailable or migrations are missing"
        ) from None
    return {"status": "ok"}
