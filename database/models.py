from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean

from .session import Base


class Config(Base):
    __tablename__ = "configs"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(Text)
    description = Column(String)
    config_type = Column(String, default="string")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class StrategyRecord(Base):
    __tablename__ = "strategy_records"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # 策略名称
    coin = Column(String, index=True)  # 交易币种
    interval = Column(String, index=True)  # 时间间隔
    account_alias = Column(String, index=True)  # 账户别名
    is_running = Column(Boolean, default=False)  # 是否正在运行
    subscription_id = Column(String, index=True, nullable=True)  # 运行时的订阅ID
    subscription_type = Column(String, index=True, nullable=True)  # 订阅类型
    params = Column(JSON, nullable=True)  # 参数
    status = Column(String, index=True, default="created")  # 状态: created, running, stopped, error
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    alias = Column(String, unique=True, index=True)
    account_address = Column(String, index=True)
    api_wallet_address = Column(String, index=True)
    secret_key = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    account_alias = Column(String, index=True)
    strategy_name = Column(String, index=True)
    event_type = Column(String, index=True)
    event_content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


