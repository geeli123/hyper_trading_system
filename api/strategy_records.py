from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from database.models import StrategyRecord
from database.session import SessionLocal

router = APIRouter(prefix="/strategy-records", tags=["strategy-records"])


class StrategyRecordOut(BaseModel):
    id: int
    subscription_id: str
    subscription_type: str
    params: dict
    status: str
    error_message: str
    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=List[StrategyRecordOut])
def list_strategy_records():
    db = SessionLocal()
    try:
        return db.query(StrategyRecord).order_by(StrategyRecord.id.desc()).limit(500).all()
    finally:
        db.close()


