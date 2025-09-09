import logging
from typing import Dict

import requests

from config.config_manager import ConfigManager


class Notifier:
    """Notification service for trading system (Singleton)"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Notifier, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.webhook_url = ConfigManager.get_config("notify_url")
            self._initialized = True

    def send_message(self, title: str, content: str, msg_type: str = "text") -> bool:
        """Send message to Feishu"""
        if not self.webhook_url:
            logging.warning("Webhook URL not configured, cannot send notification")
            return False

        try:
            payload = {
                "msg_type": msg_type,
                "content": {
                    # msg_type: content + "\n<at user_id=\"all\">all</at>"
                    msg_type: content
                },
                "at": {
                    "is_at_all": True
                }
            }

            if title:
                payload["content"]["title"] = title

            response = requests.post(
                self.webhook_url,
                headers={'Content-Type': 'application/json'},
                json=payload
            )

            response.raise_for_status()

            result = response.json()
            if result.get('code') == 0:
                logging.info("Notification sent successfully")
                return True
            else:
                logging.error(f"Failed to send notification: {result}")
                return False

        except Exception as e:
            logging.error(f"Error sending notification: {e}")
            return False

    def send_price_alert(self, price_info: Dict, symbol: str, percent_change: float = None) -> bool:
        """Send price alert notification with percentage change information"""
        try:
            if percent_change is not None:
                direction = "surged" if percent_change > 0 else "dropped"
                title = f"💰 {symbol} Price {direction.upper()} {abs(percent_change):.2f}%"
                content = f"{symbol} Price Alert\n\nCurrent Price: ${price_info.get('price', 0):.8f}\nMarket Cap: ${price_info.get('market_cap', 0):,.2f}\nChange: {direction} {abs(percent_change):.2f}% from last check"
            else:
                title = f"📊 {symbol} Price Update"
                content = f"{symbol} Price Update\n\nCurrent Price: ${price_info.get('price', 0):.8f}\nMarket Cap: ${price_info.get('market_cap', 0):,.2f}"

            return self.send_message(title, content)
        except Exception as e:
            logging.error(f"Failed to send price alert: {e}")
            return False

    def send_trade_notification(self, tx_hash: str, amount: float, estimated_usd_value: float,
                                symbol: str, token_symbol: str = None, action_type: str = 'sell') -> bool:
        """Send trade notification, action_type: 'buy' or 'sell'"""
        try:
            action_emoji = "🟢" if action_type == 'buy' else "🔴"
            action_text = "BUY" if action_type == 'buy' else "SELL"

            title = f"{action_emoji} {symbol} {action_text} Order Completed!"
            content = f"""{symbol} {action_text} Transaction Completed

Amount: {amount:.6f} {token_symbol or 'tokens'}
Estimated Value: ${estimated_usd_value:.2f} USD
Transaction Hash: {tx_hash}
View Transaction: https://app.hyperliquid.xyz/trade/{symbol}"""

            return self.send_message(title, content)
        except Exception as e:
            logging.error(f"Failed to send trade notification: {e}")
            return False

    def send_error_notification(self, error_msg: str, symbol: str = None) -> bool:
        """Send error notification"""
        try:
            if symbol:
                title = f"❌ {symbol} System Error"
                content = f"{symbol} Trading System Error\n\nError Details: {error_msg}"
            else:
                title = "❌ System Error"
                content = f"Trading System Error\n\nError Details: {error_msg}"

            return self.send_message(title, content)

        except Exception as e:
            logging.error(f"Failed to send error notification: {e}")
            return False

    def send_startup_notification(self, symbol: str = None) -> bool:
        """Send system startup notification"""
        try:
            if symbol:
                title = f"🚀 {symbol} Trading System Started"
                content = f"{symbol} Trading System Startup\n\nThe trading system has been successfully started and is now monitoring price changes..."
            else:
                title = "🚀 Trading System Started"
                content = "Trading System Startup\n\nThe trading system has been successfully started and is now monitoring market changes..."

            return self.send_message(title, content)

        except Exception as e:
            logging.error(f"Failed to send startup notification: {e}")
            return False

    def send_strategy_execution_notification(self, strategy_name: str, symbol: str, action: str,
                                           details: str = None, status: str = "started") -> bool:
        """Send strategy execution notification"""
        try:
            status_emoji = {"started": "⚡", "completed": "✅", "failed": "❌"}.get(status, "⚡")
            status_text = status.upper()

            title = f"{status_emoji} {symbol} Strategy {status_text}"
            content = f"{symbol} Strategy Execution\n\nStrategy: {strategy_name}\nAction: {action}\nStatus: {status_text}"

            if details:
                content += f"\nDetails: {details}"

            return self.send_message(title, content)
        except Exception as e:
            logging.error(f"Failed to send strategy execution notification: {e}")
            return False
