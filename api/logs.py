from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from database.models import Log
from database.session import SessionLocal
from utils.response import ApiResponse

router = APIRouter(prefix="/logs", tags=["logs"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class LogIn(BaseModel):
    account_alias: str
    strategy_name: str
    event_type: str
    event_content: str


class LogOut(BaseModel):
    id: int
    account_alias: str
    strategy_name: str
    symbol: str
    event_type: str
    level: str
    event_content: str
    extra_data: Optional[dict] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


@router.get("/")
def list_logs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    strategy_name: Optional[str] = Query(None, description="Filter by strategy name"),
    account_alias: Optional[str] = Query(None, description="Filter by account alias"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    db: Session = Depends(get_db)
):
    """Get logs with pagination and filtering"""
    query = db.query(Log)

    # Apply filters
    if strategy_name:
        query = query.filter(Log.strategy_name == strategy_name)
    if account_alias:
        query = query.filter(Log.account_alias == account_alias)
    if symbol:
        query = query.filter(Log.symbol == symbol)
    if event_type:
        query = query.filter(Log.event_type == event_type)
    if level:
        query = query.filter(Log.level == level)

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    items = query.order_by(Log.id.desc()).offset(offset).limit(page_size).all()

    # Calculate pagination info
    total_pages = (total + page_size - 1) // page_size

    return ApiResponse.success({
        "items": [LogOut.model_validate(i).model_dump() for i in items],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    })


@router.get("/strategy/{strategy_name}")
def get_strategy_logs(
    strategy_name: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    account_alias: Optional[str] = Query(None, description="Filter by account alias"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    db: Session = Depends(get_db)
):
    """Get logs for a specific strategy with pagination and filtering"""
    query = db.query(Log).filter(Log.strategy_name == strategy_name)

    # Apply additional filters
    if account_alias:
        query = query.filter(Log.account_alias == account_alias)
    if event_type:
        query = query.filter(Log.event_type == event_type)
    if level:
        query = query.filter(Log.level == level)

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    items = query.order_by(Log.id.desc()).offset(offset).limit(page_size).all()

    # Calculate pagination info
    total_pages = (total + page_size - 1) // page_size

    return ApiResponse.success({
        "items": [LogOut.model_validate(i).model_dump() for i in items],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    })


@router.post("/")
def create_log(payload: LogIn, db: Session = Depends(get_db)):
    obj = Log(**payload.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return ApiResponse.success(LogOut.model_validate(obj).model_dump(), "created")


