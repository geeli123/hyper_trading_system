from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from database.models import StrategyRecord
from database.session import SessionLocal
from utils.response import ApiResponse

router = APIRouter(prefix="/strategy-records", tags=["strategy-records"])


class StrategyRecordOut(BaseModel):
    id: int
    subscription_id: str
    subscription_type: str
    params: dict
    status: str
    error_message: str
    model_config = ConfigDict(from_attributes=True)


@router.get("/")
def list_strategy_records():
    db = SessionLocal()
    try:
        items = db.query(StrategyRecord).order_by(StrategyRecord.id.desc()).limit(500).all()
        return ApiResponse.success([StrategyRecordOut.model_validate(i).model_dump() for i in items])
    finally:
        db.close()


