from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from api.common import get_subscription_manager
from core.subscription_manager import SubscriptionManager
from database.models import StrategyRecord
from database.session import SessionLocal
from utils.response import ApiResponse

router = APIRouter(prefix="/strategy-records", tags=["strategy-records"])


class StrategyRecordCreate(BaseModel):
    name: str
    coin: str
    interval: str
    account_alias: str


class StrategyRecordUpdate(BaseModel):
    name: Optional[str] = None
    coin: Optional[str] = None
    interval: Optional[str] = None
    account_alias: Optional[str] = None


class StrategyRecordOut(BaseModel):
    id: int
    name: Optional[str] = None
    coin: Optional[str] = None
    interval: Optional[str] = None
    account_alias: Optional[str] = None
    is_running: Optional[bool] = False
    subscription_id: Optional[str] = None
    subscription_type: Optional[str] = None
    params: Optional[dict] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _sanitize_strategy_record(record: StrategyRecord) -> dict:
    """清理策略记录，移除敏感信息"""
    record_dict = StrategyRecordOut.model_validate(record).model_dump()

    # 为旧记录提供默认值
    if record_dict.get('name') is None:
        record_dict['name'] = f"Legacy Strategy {record_dict['id']}"
    if record_dict.get('coin') is None:
        record_dict['coin'] = "ETH"
    if record_dict.get('interval') is None:
        record_dict['interval'] = "1m"
    if record_dict.get('account_alias') is None:
        record_dict['account_alias'] = "default"
    if record_dict.get('is_running') is None:
        record_dict['is_running'] = False

    # 如果params包含敏感信息，则过滤掉
    if record_dict.get('params'):
        sanitized_params = {k: v for k, v in record_dict['params'].items()
                            if k not in ['user_secret_key', 'secret_key', 'private_key']}
        record_dict['params'] = sanitized_params

    return record_dict


@router.get("/")
def list_strategy_records(db: Session = Depends(get_db)):
    """获取所有策略记录"""
    items = db.query(StrategyRecord).order_by(StrategyRecord.id.desc()).limit(500).all()
    return ApiResponse.success([_sanitize_strategy_record(i) for i in items])


@router.post("/")
def create_strategy_record(request: StrategyRecordCreate, db: Session = Depends(get_db)):
    """创建策略记录（不启动）"""
    try:
        # 检查账户别名是否存在
        from database.models import Account
        account = db.query(Account).filter_by(alias=request.account_alias).first()
        if not account:
            raise HTTPException(status_code=400, detail=f"Account alias '{request.account_alias}' not found")

        # 创建策略记录
        strategy_record = StrategyRecord(
            name=request.name,
            coin=request.coin,
            interval=request.interval,
            account_alias=request.account_alias,
            is_running=False,
            status="created"
        )

        db.add(strategy_record)
        db.commit()
        db.refresh(strategy_record)

        return ApiResponse.success(_sanitize_strategy_record(strategy_record), "Strategy record created successfully")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{strategy_id}")
def get_strategy_record(strategy_id: int, db: Session = Depends(get_db)):
    """获取单个策略记录"""
    strategy = db.query(StrategyRecord).filter_by(id=strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略记录不存在")

    return ApiResponse.success(_sanitize_strategy_record(strategy))


@router.put("/{strategy_id}")
def update_strategy_record(strategy_id: int, request: StrategyRecordUpdate, db: Session = Depends(get_db)):
    """更新策略记录"""
    try:
        strategy = db.query(StrategyRecord).filter_by(id=strategy_id).first()
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy record not found")

        # 如果策略正在运行，不允许修改
        if strategy.is_running:
            raise HTTPException(status_code=400,
                                detail="Strategy is running, cannot modify. Please stop the strategy first")

        # 更新字段
        update_data = request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "account_alias" and value:
                # 检查账户别名是否存在
                from database.models import Account
                account = db.query(Account).filter_by(alias=value).first()
                if not account:
                    raise HTTPException(status_code=400, detail=f"Account alias '{value}' not found")
            setattr(strategy, field, value)

        strategy.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(strategy)

        return ApiResponse.success(_sanitize_strategy_record(strategy), "Strategy record updated successfully")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{strategy_id}")
def delete_strategy_record(strategy_id: int, db: Session = Depends(get_db)):
    """删除策略记录"""
    try:
        strategy = db.query(StrategyRecord).filter_by(id=strategy_id).first()
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy record not found")

        # 如果策略正在运行，不允许删除
        if strategy.is_running:
            raise HTTPException(status_code=400,
                                detail="Strategy is running, cannot delete. Please stop the strategy first")

        db.delete(strategy)
        db.commit()

        return ApiResponse.success({"message": f"Strategy record {strategy_id} deleted successfully"})

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{strategy_id}/start")
def start_strategy_record(strategy_id: int,
                          db: Session = Depends(get_db),
                          subscription_manager: SubscriptionManager = Depends(get_subscription_manager)):
    """启动策略记录"""
    try:
        strategy = db.query(StrategyRecord).filter_by(id=strategy_id).first()
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy record not found")

        # 如果策略已经在运行，不允许重复启动
        if strategy.is_running:
            raise HTTPException(status_code=400, detail="Strategy is already running")

        # 获取账户信息
        from database.models import Account
        account = db.query(Account).filter_by(alias=strategy.account_alias).first()
        if not account:
            raise HTTPException(status_code=400, detail=f"Account alias '{strategy.account_alias}' not found")

        # 准备订阅参数
        params = {
            "coin": strategy.coin,
            "interval": strategy.interval,
            "account_alias": strategy.account_alias,
            "strategy_name": strategy.name,
            "user": account.account_address,  # 添加用户地址
            "user_secret_key": account.secret_key  # 添加用户私钥
        }

        # 创建订阅 - 这会同时创建candle和userFills两个订阅
        subscription_id = subscription_manager.add_subscription("candle", params)

        # 更新策略记录状态
        strategy.is_running = True
        strategy.status = "running"
        strategy.subscription_id = subscription_id
        strategy.subscription_type = "candle"
        strategy.params = params
        strategy.error_message = None
        strategy.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(strategy)

        return ApiResponse.success(_sanitize_strategy_record(strategy), "Strategy started successfully")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        # 更新错误状态
        try:
            strategy = db.query(StrategyRecord).filter_by(id=strategy_id).first()
            if strategy:
                strategy.status = "error"
                strategy.error_message = str(e)
                strategy.updated_at = datetime.utcnow()
                db.commit()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to start strategy: {str(e)}")


@router.post("/{strategy_id}/stop")
def stop_strategy_record(strategy_id: int,
                         db: Session = Depends(get_db),
                         subscription_manager: SubscriptionManager = Depends(get_subscription_manager)):
    """停止策略记录"""
    try:
        strategy = db.query(StrategyRecord).filter_by(id=strategy_id).first()
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy record not found")

        # 如果策略没有在运行，不需要停止
        if not strategy.is_running:
            raise HTTPException(status_code=400, detail="Strategy is not running")

        # 停止订阅
        if strategy.subscription_id:
            success = subscription_manager.remove_subscription(strategy.subscription_id)
            if not success:
                # 即使停止订阅失败，也要更新数据库状态
                pass

        # 更新策略记录状态
        strategy.is_running = False
        strategy.status = "stopped"
        strategy.subscription_id = None
        strategy.subscription_type = None
        strategy.params = None
        strategy.error_message = None
        strategy.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(strategy)

        return ApiResponse.success(_sanitize_strategy_record(strategy), "Strategy stopped successfully")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to stop strategy: {str(e)}")
