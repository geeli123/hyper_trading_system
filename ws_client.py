from __future__ import annotations

import json
import threading
import time
import typing as _t
from itertools import count
import os

from websocket import WebSocketApp
import ssl
import certifi


JsonDict = dict[str, _t.Any]


class HLWebSocketClient:
    """Hyperliquid WebSocket client supporting subscribe/unsubscribe/post and handlers.

    Default endpoint: wss://api.hyperliquid.xyz/ws
    """

    def __init__(
        self,
        url: str | None = None,
        auto_reconnect: bool = True,
    ) -> None:
        self._url = url or os.environ.get("HL_WS_URL", "wss://api.hyperliquid.xyz/ws")
        self._auto_reconnect = auto_reconnect
        self._app: WebSocketApp | None = None
        self._thread: threading.Thread | None = None
        self._send_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._opened_event = threading.Event()

        # Handlers per channel, and a wildcard handler for all messages
        self._channel_handlers: dict[str, list[_t.Callable[[JsonDict], None]]] = {}
        self._wildcard_handlers: list[_t.Callable[[JsonDict], None]] = []

        # Post request correlation tracking
        self._id_counter = count(start=1)
        self._pending_posts: dict[int, JsonDict | None] = {}
        self._pending_cv = threading.Condition()

    # -----------------------
    # Public API
    # -----------------------
    def connect(self, wait_open_seconds: float = 5.0) -> None:
        if self._app is not None:
            return

        self._stop_event.clear()
        self._app = WebSocketApp(
            self._url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        def _run() -> None:
            # Build ssl options; prefer explicit ca_certs for compatibility
            verify_env = os.environ.get("HL_WS_VERIFY", "1").strip()
            if verify_env in {"0", "false", "False", "no"}:
                sslopt = {"cert_reqs": ssl.CERT_NONE}
            else:
                sslopt = {"cert_reqs": ssl.CERT_REQUIRED, "ca_certs": certifi.where()}
            while not self._stop_event.is_set():
                try:
                    # run_forever will return when closed or on error
                    self._app.run_forever(
                        ping_interval=30,
                        ping_timeout=10,
                        sslopt=sslopt,
                    )
                except Exception:
                    # Best-effort swallow errors to allow reconnect loop
                    pass
                if not self._auto_reconnect or self._stop_event.is_set():
                    break
                time.sleep(1.0)

        self._thread = threading.Thread(target=_run, name="HLWebSocketClient", daemon=True)
        self._thread.start()

        # Wait briefly for connection open so callers can subscribe immediately
        self._opened_event.wait(timeout=wait_open_seconds)

    def close(self) -> None:
        self._stop_event.set()
        if self._app is not None:
            try:
                self._app.close()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._app = None
        self._thread = None

    def add_handler(self, channel: str, handler: _t.Callable[[JsonDict], None]) -> None:
        self._channel_handlers.setdefault(channel, []).append(handler)

    def add_wildcard_handler(self, handler: _t.Callable[[JsonDict], None]) -> None:
        self._wildcard_handlers.append(handler)

    def subscribe(self, subscription: JsonDict) -> None:
        self._send({"method": "subscribe", "subscription": subscription})

    def unsubscribe(self, subscription: JsonDict) -> None:
        self._send({"method": "unsubscribe", "subscription": subscription})

    def ping(self) -> None:
        self._send({"method": "ping"})

    def post_info(self, payload: JsonDict, request_id: int | None = None) -> int:
        return self._post_generic("info", payload, request_id=request_id)

    def post_action(self, payload: JsonDict, request_id: int | None = None) -> int:
        return self._post_generic("action", payload, request_id=request_id)

    def await_post(self, request_id: int, timeout: float | None = 10.0) -> JsonDict | None:
        with self._pending_cv:
            if request_id not in self._pending_posts:
                return None
            end = None if timeout is None else time.time() + timeout
            while self._pending_posts[request_id] is None:
                remaining = None if end is None else max(0.0, end - time.time())
                if remaining == 0.0:
                    return None
                self._pending_cv.wait(timeout=remaining)
            return self._pending_posts.pop(request_id)

    # -----------------------
    # Internals
    # -----------------------
    def _post_generic(self, req_type: str, payload: JsonDict, request_id: int | None = None) -> int:
        if request_id is None:
            request_id = next(self._id_counter)
        with self._pending_cv:
            self._pending_posts[request_id] = None
        msg = {
            "method": "post",
            "id": request_id,
            "request": {
                "type": req_type,
                "payload": payload,
            },
        }
        self._send(msg)
        return request_id

    def _send(self, obj: JsonDict) -> None:
        data = json.dumps(obj, separators=(",", ":"))
        with self._send_lock:
            if self._app is None:
                raise RuntimeError("WebSocketApp not initialized. Call connect() first.")
            # If not yet opened, wait a short grace period
            if not self._opened_event.wait(timeout=5.0):
                raise RuntimeError("WebSocket not open; unable to send message.")
            self._app.send(data)

    # -----------------------
    # WebSocket callbacks
    # -----------------------
    def _on_open(self, _ws):  # noqa: ANN001
        self._opened_event.set()

    def _on_close(self, _ws, _code, _msg):  # noqa: ANN001
        self._opened_event.clear()

    def _on_error(self, _ws, _error):  # noqa: ANN001
        # Errors are reported via wildcard handlers if any want to listen for them
        err_msg = {"channel": "error", "data": str(_error)}
        for handler in list(self._wildcard_handlers):
            try:
                handler(err_msg)
            except Exception:
                pass

    def _on_message(self, _ws, message: str):  # noqa: ANN001
        try:
            obj = json.loads(message)
        except Exception:
            return

        # Correlate post responses
        if isinstance(obj, dict) and obj.get("channel") == "post":
            try:
                data = obj.get("data", {})
                req_id = int(data.get("id"))
            except Exception:
                req_id = None
            if req_id is not None:
                with self._pending_cv:
                    if req_id in self._pending_posts:
                        self._pending_posts[req_id] = data
                        self._pending_cv.notify_all()

        # Dispatch to channel-specific handlers
        channel = obj.get("channel") if isinstance(obj, dict) else None
        if isinstance(channel, str):
            for handler in list(self._channel_handlers.get(channel, [])):
                try:
                    handler(obj)
                except Exception:
                    pass

        # Wildcard handlers see everything
        for handler in list(self._wildcard_handlers):
            try:
                handler(obj)
            except Exception:
                pass


def demo_run(duration_seconds: float = 10.0) -> None:
    """Small demo: subscribe to allMids and ETH trades, print a few updates."""
    ws = HLWebSocketClient()

    def print_selected(msg: JsonDict) -> None:
        channel = msg.get("channel")
        if channel in {"subscriptionResponse", "pong"}:
            return
        if channel == "allMids":
            data = msg.get("data", {})
            mids = data.get("mids", {}) if isinstance(data, dict) else {}
            for coin in ("BTC", "ETH"):
                if coin in mids:
                    print(f"mid {coin} = {mids[coin]}")
        elif channel == "trades":
            data = msg.get("data")
            if isinstance(data, list) and data:
                t0 = data[-1]
                coin = t0.get("coin")
                px = t0.get("px")
                sz = t0.get("sz")
                side = t0.get("side")
                print(f"trade {coin} {side} px={px} sz={sz}")

    def print_any(msg: JsonDict) -> None:
        channel = msg.get("channel")
        if channel == "error":
            print(f"ws error: {msg.get('data')}")

    ws.add_handler("allMids", print_selected)
    ws.add_handler("trades", print_selected)
    ws.add_wildcard_handler(print_any)

    ws.connect()
    ws.subscribe({"type": "allMids"})
    ws.subscribe({"type": "trades", "coin": "ETH"})

    end = time.time() + duration_seconds
    try:
        while time.time() < end:
            time.sleep(0.2)
    finally:
        ws.unsubscribe({"type": "trades", "coin": "ETH"})
        ws.unsubscribe({"type": "allMids"})
        ws.close()


