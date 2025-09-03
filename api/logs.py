from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from database.models import Log
from database.session import SessionLocal

router = APIRouter(prefix="/logs", tags=["logs"])


class LogIn(BaseModel):
    account_alias: str
    strategy_name: str
    event_type: str
    event_content: str


class LogOut(BaseModel):
    id: int
    account_alias: str
    strategy_name: str
    event_type: str
    event_content: str

    class Config:
        orm_mode = True


@router.get("/", response_model=List[LogOut])
def list_logs():
    db = SessionLocal()
    try:
        return db.query(Log).order_by(Log.id.desc()).limit(500).all()
    finally:
        db.close()


@router.post("/", response_model=LogOut)
def create_log(payload: LogIn):
    db = SessionLocal()
    try:
        obj = Log(**payload.dict())
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj
    finally:
        db.close()


