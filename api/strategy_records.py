import logging
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
logger = logging.getLogger(__name__)


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
    candle_subscription_id: Optional[str] = None
    userfills_subscription_id: Optional[str] = None
    # Keep old fields for backward compatibility
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
        
        # 检查是否已存在相同的coin+interval+account_alias组合
        existing_strategy = db.query(StrategyRecord).filter_by(
            coin=request.coin,
            interval=request.interval,
            account_alias=request.account_alias
        ).first()
        
        if existing_strategy:
            raise HTTPException(
                status_code=400, 
                detail=f"Strategy with coin '{request.coin}', interval '{request.interval}' and account '{request.account_alias}' already exists"
            )
        
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
        
        # 准备新的值（如果没有更新则使用现有值）
        new_coin = update_data.get('coin', strategy.coin)
        new_interval = update_data.get('interval', strategy.interval)
        new_account_alias = update_data.get('account_alias', strategy.account_alias)
        
        # 检查更新后的组合是否与其他策略重复
        if new_coin or new_interval or new_account_alias:
            existing_strategy = db.query(StrategyRecord).filter(
                StrategyRecord.coin == new_coin,
                StrategyRecord.interval == new_interval,
                StrategyRecord.account_alias == new_account_alias,
                StrategyRecord.id != strategy_id  # 排除当前策略本身
            ).first()
            
            if existing_strategy:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Strategy with coin '{new_coin}', interval '{new_interval}' and account '{new_account_alias}' already exists"
                )
        
        # 应用更新
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

        # 创建策略订阅 - 这会同时创建candle和userFills两个订阅
        subscription_ids = subscription_manager.add_strategy_subscriptions(params)
        
        # 更新策略记录状态
        strategy.is_running = True
        strategy.status = "running"
        strategy.candle_subscription_id = subscription_ids["candle"]
        strategy.userfills_subscription_id = subscription_ids["userFills"]
        # Keep backward compatibility
        strategy.subscription_id = subscription_ids["candle"]  # Use candle as primary for compatibility
        strategy.subscription_type = "strategy"
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

        # 停止所有订阅
        subscription_ids = {}
        if strategy.candle_subscription_id:
            subscription_ids["candle"] = strategy.candle_subscription_id
        if strategy.userfills_subscription_id:
            subscription_ids["userFills"] = strategy.userfills_subscription_id
        
        # Fallback to old single subscription if new fields are not set
        if not subscription_ids and strategy.subscription_id:
            subscription_ids["legacy"] = strategy.subscription_id
        
        if subscription_ids:
            success = subscription_manager.remove_strategy_subscriptions(subscription_ids)
            if not success:
                logger.warning(f"Failed to remove some subscriptions for strategy {strategy_id}")
                # Continue with database update even if some subscriptions failed to remove
        
        # 更新策略记录状态
        strategy.is_running = False
        strategy.status = "stopped"
        strategy.candle_subscription_id = None
        strategy.userfills_subscription_id = None
        # Clear old fields too
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
