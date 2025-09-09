import logging
from datetime import datetime
from enum import Enum
from typing import Dict

from database.models import Log
from database.session import SessionLocal
from utils.notifier import Notifier


class EventType(str, Enum):
    INFO = "INFO"
    SYSTEM_START = "SYSTEM_START"
    STRATEGY_START = "STRATEGY_START"
    STRATEGY_STOP = "STRATEGY_STOP"
    STRATEGY_EXECUTION = "STRATEGY_EXECUTION"
    TRADE = "TRADE"
    PRICE_ALERT = "PRICE_ALERT"
    ERROR = "ERROR"


class LogLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class NotificationLogger:
    """Unified notification and logging service (Singleton)"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NotificationLogger, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.notifier = Notifier()
            self.logger = logging.getLogger(__name__)
            self._initialized = True

    def _save_log(self, account_alias: str = None, strategy_name: str = None,
                  symbol: str = None, event_type: EventType = EventType.INFO,
                  level: LogLevel = LogLevel.INFO, event_content: str = "",
                  extra_data: Dict = None):
        """Save log to database"""
        try:
            with SessionLocal() as db:
                log_entry = Log(
                    account_alias=account_alias,
                    strategy_name=strategy_name,
                    symbol=symbol,
                    event_type=event_type.value,
                    level=level.value,
                    event_content=event_content,
                    extra_data=extra_data,
                    created_at=datetime.utcnow()
                )
                db.add(log_entry)
                db.commit()
                self.logger.info(f"Log saved: {event_type.value} - {event_content}")
        except Exception as e:
            self.logger.error(f"Failed to save log: {e}")

    def notify_and_log_system_startup(self, symbol: str = None):
        """System startup notification and logging"""
        try:
            # Send notification
            self.notifier.send_startup_notification(symbol)

            # Save log
            self._save_log(
                event_type=EventType.SYSTEM_START,
                level=LogLevel.INFO,
                symbol=symbol,
                event_content=f"Trading system started{f' for {symbol}' if symbol else ''}",
                extra_data={"timestamp": datetime.utcnow().isoformat()}
            )
        except Exception as e:
            self.logger.error(f"Failed to notify and log system startup: {e}")

    def notify_and_log_strategy_execution(self, strategy_name: str, symbol: str,
                                        action: str, account_alias: str = None,
                                        details: str = None, status: str = "started"):
        """Strategy execution notification and logging"""
        try:
            # Send notification
            self.notifier.send_strategy_execution_notification(
                strategy_name=strategy_name,
                symbol=symbol,
                action=action,
                details=details,
                status=status
            )

            # Determine event type and level
            if action in ["START"]:
                event_type = EventType.STRATEGY_START
            elif action in ["STOP"]:
                event_type = EventType.STRATEGY_STOP
            else:
                event_type = EventType.STRATEGY_EXECUTION

            level = LogLevel.ERROR if status == "failed" else LogLevel.INFO

            # Save log
            self._save_log(
                account_alias=account_alias,
                strategy_name=strategy_name,
                symbol=symbol,
                event_type=event_type,
                level=level,
                event_content=f"Strategy {action}: {details or 'No details'}",
                extra_data={
                    "action": action,
                    "status": status,
                    "details": details,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            self.logger.error(f"Failed to notify and log strategy execution: {e}")

    def notify_and_log_trade(self, tx_hash: str, amount: float, estimated_usd_value: float,
                           symbol: str, token_symbol: str = None, action_type: str = 'sell',
                           account_alias: str = None, strategy_name: str = None):
        """Trade notification and logging"""
        try:
            # Send notification
            self.notifier.send_trade_notification(
                tx_hash=tx_hash,
                amount=amount,
                estimated_usd_value=estimated_usd_value,
                symbol=symbol,
                token_symbol=token_symbol,
                action_type=action_type
            )

            # Save log
            self._save_log(
                account_alias=account_alias,
                strategy_name=strategy_name,
                symbol=symbol,
                event_type=EventType.TRADE,
                level=LogLevel.INFO,
                event_content=f"Trade executed: {action_type.upper()} {amount:.6f} {token_symbol or symbol} for ${estimated_usd_value:.2f}",
                extra_data={
                    "tx_hash": tx_hash,
                    "amount": amount,
                    "estimated_usd_value": estimated_usd_value,
                    "action_type": action_type,
                    "token_symbol": token_symbol,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            self.logger.error(f"Failed to notify and log trade: {e}")

    def notify_and_log_price_alert(self, price_info: Dict, symbol: str,
                                 percent_change: float = None,
                                 account_alias: str = None, strategy_name: str = None):
        """Price alert notification and logging"""
        try:
            # Send notification
            self.notifier.send_price_alert(
                price_info=price_info,
                symbol=symbol,
                percent_change=percent_change
            )

            # Save log
            direction = "surged" if percent_change > 0 else "dropped" if percent_change else "updated"
            content = f"Price {direction}"
            if percent_change:
                content += f" {abs(percent_change):.2f}%"
            content += f" - Current: ${price_info.get('price', 0):.8f}"

            self._save_log(
                account_alias=account_alias,
                strategy_name=strategy_name,
                symbol=symbol,
                event_type=EventType.PRICE_ALERT,
                level=LogLevel.WARNING if abs(percent_change or 0) >= 10 else LogLevel.INFO,
                event_content=content,
                extra_data={
                    "price": price_info.get('price', 0),
                    "market_cap": price_info.get('market_cap', 0),
                    "percent_change": percent_change,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            self.logger.error(f"Failed to notify and log price alert: {e}")

    def notify_and_log_error(self, error_msg: str, symbol: str = None,
                           account_alias: str = None, strategy_name: str = None):
        """Error notification and logging"""
        try:
            # Send notification
            self.notifier.send_error_notification(error_msg, symbol)

            # Save log
            self._save_log(
                account_alias=account_alias,
                strategy_name=strategy_name,
                symbol=symbol,
                event_type=EventType.ERROR,
                level=LogLevel.ERROR,
                event_content=f"System error: {error_msg}",
                extra_data={
                    "error_message": error_msg,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            self.logger.error(f"Failed to notify and log error: {e}")

    def log_only(self, account_alias: str = None, strategy_name: str = None,
                 symbol: str = None, event_type: EventType = EventType.INFO,
                 level: LogLevel = LogLevel.INFO, event_content: str = "",
                 extra_data: Dict = None):
        """Log only without notification"""
        self._save_log(
            account_alias=account_alias,
            strategy_name=strategy_name,
            symbol=symbol,
            event_type=event_type,
            level=level,
            event_content=event_content,
            extra_data=extra_data
        )
