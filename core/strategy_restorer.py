"""
Strategy Restorer for Hyperliquid Trading System

Handles restoration of active strategies after service restart.
"""

import logging
from datetime import datetime

from core.subscription_manager import SubscriptionManager

logger = logging.getLogger(__name__)


class StrategyRestorer:
    """负责恢复服务重启前的active策略"""

    def __init__(self, subscription_manager: SubscriptionManager):
        self.subscription_manager = subscription_manager

    async def restore_active_strategies(self) -> dict:
        """恢复服务重启前的active策略

        Returns:
            dict: 包含恢复结果的统计信息
        """
        try:
            from database.session import SessionLocal
            from database.models import StrategyRecord, Account

            db = SessionLocal()
            try:
                # 查询所有正在运行的策略
                active_strategies = db.query(StrategyRecord).filter(
                    (StrategyRecord.is_running == True) | (StrategyRecord.status == "running")
                ).all()

                if not active_strategies:
                    logger.info("No active strategies found to restore")
                    return {"restored": 0, "failed": 0, "total": 0}

                logger.info(f"Found {len(active_strategies)} active strategies to restore")

                restored_count = 0
                failed_count = 0

                for strategy in active_strategies:
                    try:
                        success = await self._restore_single_strategy(strategy, db)
                        if success:
                            restored_count += 1
                            logger.info(f"Restored strategy {strategy.id} ({strategy.name}) for {strategy.coin}")
                        else:
                            failed_count += 1

                    except Exception as e:
                        logger.error(f"Failed to restore strategy {strategy.id}: {e}")
                        self._mark_strategy_as_failed(strategy, f"Failed to restore: {str(e)}")
                        failed_count += 1

                # 批量提交数据库更改
                db.commit()

                result = {"restored": restored_count, "failed": failed_count, "total": len(active_strategies)}
                logger.info(f"Strategy restoration completed: {restored_count} restored, {failed_count} failed")

                return result

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to restore active strategies: {e}")
            return {"restored": 0, "failed": 0, "total": 0, "error": str(e)}

    async def _restore_single_strategy(self, strategy, db) -> bool:
        """恢复单个策略

        Args:
            strategy: StrategyRecord实例
            db: 数据库会话

        Returns:
            bool: 是否成功恢复
        """
        from database.models import Account

        # 获取账户信息
        account = db.query(Account).filter_by(alias=strategy.account_alias).first()
        if not account:
            logger.error(f"Account '{strategy.account_alias}' not found for strategy {strategy.id}")
            self._mark_strategy_as_failed(strategy, f"Account '{strategy.account_alias}' not found")
            return False

        # 准备订阅参数
        params = {
            "coin": strategy.coin,
            "interval": strategy.interval,
            "account_alias": strategy.account_alias,
            "strategy_name": strategy.name,
            "user": account.account_address,
            "user_secret_key": account.secret_key
        }

        # 创建策略订阅
        subscription_ids = self.subscription_manager.add_strategy_subscriptions(params)

        # 更新策略记录的订阅ID
        strategy.candle_subscription_id = subscription_ids["candle"]
        strategy.userfills_subscription_id = subscription_ids["userFills"]
        strategy.subscription_id = subscription_ids["candle"]  # 向后兼容
        strategy.subscription_type = "strategy"
        strategy.params = params
        strategy.is_running = True
        strategy.status = "running"
        strategy.error_message = None
        strategy.updated_at = datetime.utcnow()

        return True

    def _mark_strategy_as_failed(self, strategy, error_message: str):
        """标记策略为失败状态

        Args:
            strategy: StrategyRecord实例
            error_message: 错误信息
        """
        strategy.is_running = False
        strategy.status = "error"
        strategy.error_message = error_message
        strategy.updated_at = datetime.utcnow()

    def get_restoration_status(self) -> dict:
        """获取策略恢复状态信息

        Returns:
            dict: 包含当前策略状态的统计信息
        """
        try:
            from database.session import SessionLocal
            from database.models import StrategyRecord

            db = SessionLocal()
            try:
                total_strategies = db.query(StrategyRecord).count()
                running_strategies = db.query(StrategyRecord).filter(
                    StrategyRecord.is_running == True
                ).count()
                error_strategies = db.query(StrategyRecord).filter(
                    StrategyRecord.status == "error"
                ).count()

                return {
                    "total": total_strategies,
                    "running": running_strategies,
                    "error": error_strategies,
                    "stopped": total_strategies - running_strategies - error_strategies
                }

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to get restoration status: {e}")
            return {"error": str(e)}
