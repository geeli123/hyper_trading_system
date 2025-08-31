"""
Enhanced Order Management System for Hyperliquid Trading

Handles all order-related operations with async support and event-driven architecture.
"""

import json
import logging
import uuid
import time
import threading
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange

logger = logging.getLogger(__name__)

class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

@dataclass
class Intent:
    """Strategy intent - what we want to do"""
    symbol: str
    side: Side
    qty: float
    price: Optional[float] = None
    tif: str = "IOC"
    meta: Dict[str, Any] = field(default_factory=dict)
    intent_id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class OrderResult:
    """Result of order execution"""
    client_order_id: str
    success: bool
    filled_qty: float = 0.0
    fill_price: float = 0.0
    reason: Optional[str] = None


class BasicOrderSystem:
    """Minimal, essential order system for quick iteration.

    Provides:
    - Market/limit order placement
    - Open orders fetch and cancel (all or by symbol)
    - Account/user state fetch and simple polling callback
    - Position fetch by symbol
    """
    
    def __init__(self, info: Info, exchange: Exchange, address: str):
        self.info = info
        self.exchange = exchange
        self.address = address
        self._poll_thread: Optional[threading.Thread] = None
        self._poll_stop = threading.Event()
        logger.info("BasicOrderSystem initialized")


    # --- Orders ---    
    def place_limit_order(self, symbol: str, is_buy: bool, size: float, price: float, tif: str = "Gtc", reduce_only: bool = False) -> bool:
        try:
            if size <= 0 or price <= 0:
                logger.error("Invalid order params")
                return False
            result = self.exchange.order(
                name=symbol,
                is_buy=is_buy,
                sz=size,
                limit_px=price,
                order_type={"limit": {"tif": tif}},
                reduce_only=reduce_only,
            )
            ok = bool(result and result.get("status") == "ok")
            if not ok:
                logger.error(f"Limit order failed: {result}")
            return ok
        except Exception as e:
            logger.error(f"Limit order error: {e}")
            return False
    
    # --- Orders admin ---
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            orders = self.info.open_orders(self.address)
            if symbol:
                orders = [o for o in orders if o.get("coin") == symbol]
            return orders or []
        except Exception as e:
            logger.error(f"Get open orders error: {e}")
            return []
    
    def cancel_all_orders(self, symbol: Optional[str] = None) -> int:
        try:
            orders = self.get_open_orders(symbol)
            count = 0
            for o in orders:
                try:
                    res = self.exchange.cancel(o["coin"], o["oid"])
                    if res and res.get("status") == "ok":
                        count += 1
                except Exception as e:
                    logger.error(f"Cancel error for {o.get('oid')}: {e}")
            return count
        except Exception as e:
            logger.error(f"Cancel all orders error: {e}")
            return 0
    
    # --- Account / positions ---
    def get_user_state(self) -> Dict[str, Any]:
        try:
            return self.info.user_state(self.address)
        except Exception as e:
            logger.error(f"User state error: {e}")
            return {}

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            us = self.get_user_state()
            for ap in us.get("assetPositions", []):
                if ap.get("position", {}).get("coin") == symbol:
                    size = float(ap["position"].get("szi", 0))
                    if size == 0:
                        return None
                    return {
                        "symbol": symbol,
                        "size": size,
                        "entry_price": float(ap["position"].get("entryPx") or 0),
                        "unrealized_pnl": float(ap.get("unrealizedPnl") or 0),
                        "side": "long" if size > 0 else "short",
                    }
            return None
        except Exception as e:
            logger.error(f"Get position error: {e}")
            return None

    # --- Realtime subscriptions (Websocket) ---
    def start_user_streams(self) -> None:
        """Subscribe via Info websocket to user events, fills, and order updates.

        Uses internal handlers that print the incoming messages.
        """
        self._ws_subscriptions: List[Dict[str, Any]] = []
        self._ws_subscription_ids: List[int] = []

        def _cb_user_event(msg: Dict[str, Any]):
            try:
                print("[userEvents]", json.dumps(msg, indent=2))
            except Exception:
                print("[userEvents]", msg)

        def _cb_user_fill(msg: Dict[str, Any]):
            try:
                print("[userFills]", json.dumps(msg, indent=2))
            except Exception:
                print("[userFills]", msg)

        def _cb_order_update(msg: Dict[str, Any]):
            try:
                print("[orderUpdates]", json.dumps(msg, indent=2))
            except Exception:
                print("[orderUpdates]", msg)

        try:
            # userEvents (no user field required)
            sub = {"type": "userEvents"}
            sid = self.info.subscribe(sub, _cb_user_event)
            self._ws_subscriptions.append(sub)
            self._ws_subscription_ids.append(sid)

            # userFills (requires user address)
            sub = {"type": "userFills", "user": self.address}
            sid = self.info.subscribe(sub, _cb_user_fill)
            self._ws_subscriptions.append(sub)
            self._ws_subscription_ids.append(sid)

            # orderUpdates (global)
            sub = {"type": "orderUpdates"}
            sid = self.info.subscribe(sub, _cb_order_update)
            self._ws_subscriptions.append(sub)
            self._ws_subscription_ids.append(sid)

            logger.info("User streams started (websocket subscriptions active)")
        except Exception as e:
            logger.error(f"Failed to start user streams: {e}")

    def stop_user_streams(self) -> None:
        """Unsubscribe all previously started websocket subscriptions."""
        try:
            if not hasattr(self, "_ws_subscriptions"):
                return
            for sub, sid in zip(self._ws_subscriptions, self._ws_subscription_ids):
                try:
                    self.info.unsubscribe(sub, sid)
                except Exception as e:
                    logger.error(f"Unsubscribe error for {sub}: {e}")
            self._ws_subscriptions = []
            self._ws_subscription_ids = []
            logger.info("User streams stopped")
        except Exception as e:
            logger.error(f"Failed to stop user streams: {e}")

    def _get_reference_price(self, symbol: str) -> Optional[float]:
        """Get a simple reference price from recent 1m candles."""
        try:
            end_ms = int(time.time()) * 1000
            start_ms = end_ms - 60 * 60 * 1000
            snapshot = self.info.candles_snapshot(symbol, "1m", start_ms, end_ms)
            if not snapshot:
                return None
            symbol_candles = [c for c in snapshot if c.get("s") == symbol]
            if not symbol_candles:
                return None
            last = symbol_candles[-1]
            return float(last.get("c") or 0) or None
        except Exception as e:
            logger.error(f"Reference price error: {e}")
            return None

    # --- Polling subscription ---
    def start_user_state_polling(self, callback: Callable[[Dict[str, Any]], None], interval_sec: int = 5) -> None:
        if self._poll_thread and self._poll_thread.is_alive():
            return

        self._poll_stop.clear()

        def _loop():
            while not self._poll_stop.is_set():
                try:
                    state = self.get_user_state()
                    if state:
                        try:
                            callback(state)
                        except Exception as cb_err:
                            logger.error(f"User state callback error: {cb_err}")
                except Exception as e:
                    logger.error(f"Polling error: {e}")
                time.sleep(max(1, int(interval_sec)))

        self._poll_thread = threading.Thread(target=_loop, name="UserStatePoll", daemon=True)
        self._poll_thread.start()


    def stop_user_state_polling(self) -> None:
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_stop.set()
            # Avoid joining from within the polling thread itself
            if threading.current_thread() is not self._poll_thread:
                self._poll_thread.join(timeout=5)

