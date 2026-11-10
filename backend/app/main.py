from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import get_db

from app.api.v1.auth import router as auth_router

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router



app = FastAPI(title="Retail AI Data Analytics Platform")

app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")



@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/health/db")
def database_health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))

    return {"database": "connected"}