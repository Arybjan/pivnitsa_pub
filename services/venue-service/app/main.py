from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api import router
from app.database import get_db

app = FastAPI(title="Pivnitsa Venue Service", version="1.0.0")
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
