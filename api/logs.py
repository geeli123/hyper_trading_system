from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from database.models import Log
from database.session import SessionLocal
from utils.response import ApiResponse

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
    model_config = ConfigDict(from_attributes=True)


@router.get("/")
def list_logs():
    db = SessionLocal()
    try:
        items = db.query(Log).order_by(Log.id.desc()).limit(500).all()
        return ApiResponse.success([LogOut.model_validate(i).model_dump() for i in items])
    finally:
        db.close()


@router.post("/")
def create_log(payload: LogIn):
    db = SessionLocal()
    try:
        obj = Log(**payload.dict())
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return ApiResponse.success(LogOut.model_validate(obj).model_dump(), "created")
    finally:
        db.close()


