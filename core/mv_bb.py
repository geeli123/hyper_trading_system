import datetime as dt
import logging
from copy import copy
from enum import Enum

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

from utils import round_values
from utils.notification_logger import NotificationLogger
from .candle_helpers import aggregate_ohlcv
from .events import OHLCVEvent, FillEvent
from .indicators import BollingerBands
from .order_system import BasicOrderSystem


class MVBBState(Enum):
    NEUTRAL = 1
    LONG = 2
    SHORT = 3

    def __eq__(self, other):
        return self.value == other.value


class MeanReversionBB:

    def __init__(
            self,
            exchange: Exchange,
            info: Info,
            address: str,
            symbol: str,
            strategy_name: str = "MeanReversionBB",
            account_alias: str = None,
            trade_size_usd: float = 12.0,
            ma_lookback_periods=20,
            bb_std_dev=2.5,
            stop_loss_multiplier=0.5,
            take_profit_multiplier=0.5,
            input_candle_periods: int = 1,
            input_candle_unit: str = "m",
            target_candle_periods: int = 1,
            target_candle_unit: str = "h",
            max_decimals_sz: int = 4,
            max_decimals_px: int = 1,
            min_trade_size_usd: float = 5.0,
    ):
        self.hl_info = info
        self.hl_exchange = exchange
        self.address = address
        self.max_decimals_sz = max_decimals_sz
        self.max_decimals_px = max_decimals_px
        self.min_trade_size_usd = min_trade_size_usd
        self.order_system = BasicOrderSystem(self.hl_info, self.hl_exchange, self.address)

        self.symbol = symbol
        self.strategy_name = strategy_name
        self.account_alias = account_alias
        self.bollinger_bands = BollingerBands(ma_lookback_periods, bb_std_dev)
        self.current_candle = None
        self.last_full_candle = None
        self.latest_candle_watermark = dt.datetime(1970, 1, 1)

        self.trade_size_usd = trade_size_usd

        self.startup_complete = False
        self.open_orders = {}

        self.stop_loss_multiplier = stop_loss_multiplier
        self.take_profit_multiplier = take_profit_multiplier

        self.strategy_state = MVBBState.NEUTRAL

        self.input_candle_periods = input_candle_periods
        self.input_candle_unit = input_candle_unit
        self.target_candle_periods = target_candle_periods
        self.target_candle_unit = target_candle_unit

        # Initialize notification logger and price tracking
        self.notification_logger = NotificationLogger()
        self.last_price = None

        self._start_up()

    @classmethod
    def from_params(
            cls,
            exchange: Exchange,
            info: Info,
            address: str,
            symbol: str,
            strategy_name: str = "MeanReversionBB",
            account_alias: str = None,
            strategy_params: dict = None
    ):
        """从参数字典创建策略实例"""
        if strategy_params is None:
            strategy_params = {}

        # 默认参数
        defaults = {
            'trade_size_usd': 12.0,
            'ma_lookback_periods': 20,
            'bb_std_dev': 2.5,
            'stop_loss_multiplier': 0.5,
            'take_profit_multiplier': 0.5,
            'input_candle_periods': 1,
            'input_candle_unit': 'm',
            'target_candle_periods': 1,
            'target_candle_unit': 'h',
            'max_decimals_sz': 4,
            'max_decimals_px': 1
        }

        # 合并用户参数和默认参数
        params = {**defaults, **strategy_params}

        return cls(
            exchange=exchange,
            info=info,
            address=address,
            symbol=symbol,
            strategy_name=strategy_name,
            account_alias=account_alias,
            trade_size_usd=params['trade_size_usd'],
            ma_lookback_periods=params['ma_lookback_periods'],
            bb_std_dev=params['bb_std_dev'],
            stop_loss_multiplier=params['stop_loss_multiplier'],
            take_profit_multiplier=params['take_profit_multiplier'],
            input_candle_periods=params['input_candle_periods'],
            input_candle_unit=params['input_candle_unit'],
            target_candle_periods=params['target_candle_periods'],
            target_candle_unit=params['target_candle_unit'],
            max_decimals_sz=params['max_decimals_sz'],
            max_decimals_px=params['max_decimals_px']
        )

    def _get_state(self, timestamp):
        return {
            "timestamp": timestamp,
            "strategy_state": self.strategy_state,
            "bb_upper": self.bollinger_bands.upper_band,
            "bb_middle": self.bollinger_bands.middle_band,
            "bb_lower": self.bollinger_bands.lower_band,
        }

    def _get_current_asset_quantity(self):
        position = self.order_system.get_position(self.symbol)
        if position is None:
            return 0
        return position['size']

    def _get_entry_asset_value(self):
        position = self.order_system.get_position(self.symbol)
        if position is None:
            return 0.0
        return position['entry_value']

    def _start_up(self):
        startup_candles = self.hl_info.candles_snapshot(
            self.symbol,
            f"{self.input_candle_periods}{self.input_candle_unit}",
            int((dt.datetime.now() - dt.timedelta(hours=24)).timestamp() * 1000),
            int(dt.datetime.now().timestamp() * 1000)
        )
        for candle in startup_candles[:-1]:  # Skip the last candle as it is incomplete
            event = OHLCVEvent.from_hyperliquid_message(candle)
            if event.start_time <= self.latest_candle_watermark:
                logging.info("Skipping candle with start time before latest watermark.")
                continue
            self.latest_candle_watermark = event.start_time
            is_complete, self.current_candle = aggregate_ohlcv(event, self.current_candle, self.target_candle_periods,
                                                               self.target_candle_unit)

            if is_complete:
                self.bollinger_bands.update(self.current_candle.close)
                self.last_full_candle = copy(self.current_candle)
        self.startup_complete = True
        logging.info("Startup complete. Bollinger Bands initialized.")
        logging.info(f"Current Bollinger Bands: {self.bollinger_bands.bands}")
        logging.info(f"Latest message: {self.latest_candle_watermark}")
        self.order_system.cancel_all_orders(self.symbol)

        positions = self.order_system.get_position(self.symbol)
        logging.info(f"show positions: {positions}")
        self._determine_strategy_state()

        self.order_system.cancel_all_orders(self.symbol)

        if self.strategy_state == MVBBState.NEUTRAL:
            logging.info("Strategy state is NEUTRAL. Placing initial limit orders at Bollinger Bands.")
            self._set_resting_open_orders(self.trade_size_usd - positions["entry_value"])
        elif self.strategy_state == MVBBState.LONG:
            bb_range_half = (-self.bollinger_bands.lower_band + self.bollinger_bands.middle_band)
            self.order_system.cancel_all_orders(self.symbol)

            self._set_resting_open_orders()

            # Place a stop order
            stop_order_type = {
                "trigger": {
                    "triggerPx": round_values(
                        self.bollinger_bands.lower_band - (bb_range_half * self.stop_loss_multiplier),
                        self.max_decimals_px
                    ),
                    "isMarket": True,
                    "tpsl": "sl"
                }
            }
            self.hl_exchange.order(
                name=self.symbol,
                is_buy=False,
                sz=self._get_current_asset_quantity(),
                limit_px=round_values(
                    self.bollinger_bands.lower_band - (bb_range_half * self.stop_loss_multiplier),
                    self.max_decimals_px
                ),
                order_type=stop_order_type,
            )

            # Place a tp order
            tp_order_type = {
                "trigger": {
                    "triggerPx": round_values(
                        self.bollinger_bands.lower_band + (bb_range_half * self.take_profit_multiplier),
                        self.max_decimals_px
                    ),
                    "isMarket": True,
                    "tpsl": "tp"
                }
            }
            self.hl_exchange.order(
                name=self.symbol,
                is_buy=False,
                sz=self._get_current_asset_quantity(),
                limit_px=round_values(
                    self.bollinger_bands.lower_band + (bb_range_half * self.take_profit_multiplier),
                    self.max_decimals_px
                ),
                order_type=tp_order_type,
            )

        # handle case where we are short - set limit / stop loss orders
        elif self.strategy_state == MVBBState.SHORT:
            bb_range_half = (self.bollinger_bands.upper_band - self.bollinger_bands.middle_band)

            self.order_system.cancel_all_orders(self.symbol)

            self._set_resting_open_orders()

            # Place a stop order
            stop_order_type = {
                "trigger": {
                    "triggerPx": round_values(
                        self.bollinger_bands.upper_band + (bb_range_half * self.stop_loss_multiplier),
                        self.max_decimals_px
                    ),
                    "isMarket": True,
                    "tpsl": "sl"
                }
            }
            self.hl_exchange.order(
                name=self.symbol,
                is_buy=True,
                sz=abs(self._get_current_asset_quantity()),
                limit_px=round_values(
                    self.bollinger_bands.upper_band + (bb_range_half * self.stop_loss_multiplier),
                    self.max_decimals_px),
                order_type=stop_order_type,
            )

            # Place a tp order
            tp_order_type = {
                "trigger": {
                    "triggerPx": round_values(
                        self.bollinger_bands.upper_band - (bb_range_half * self.take_profit_multiplier)
                    ),
                    "isMarket": True,
                    "tpsl": "tp"
                }
            }
            self.hl_exchange.order(
                name=self.symbol,
                is_buy=True,
                sz=abs(self._get_current_asset_quantity()),
                limit_px=round_values(
                    self.bollinger_bands.upper_band - (bb_range_half * self.take_profit_multiplier),
                    self.max_decimals_px),
                order_type=tp_order_type,
        )

    def process_message(self, message: dict):
        """
        Processes a new market event.
        """
        logging.info('%s-receive: %s', self.symbol, message)
        logging.info("%s-get existing open orders: %s", self.symbol, self.order_system.get_open_orders(self.symbol))
        if message['channel'] == 'candle':
            self._process_candle_message(message)
        elif message['channel'] == 'userFills':
            self._process_fill_message(message)
        else:
            raise ValueError(f"Message type {message['channel']} not supported.")

    def _process_candle_message(self, message: dict):
        """Process K-line data message"""
        event = OHLCVEvent.from_hyperliquid_message(message['data'])

        # data validation
        if not self._validate_candle_event(event):
            return

        # Update K-line data
        self.latest_candle_watermark = event.start_time
        is_complete, self.current_candle = aggregate_ohlcv(
            event, self.current_candle, self.target_candle_periods, self.target_candle_unit
        )

        if is_complete:
            print(self.strategy_state)

            # Check for significant price changes before updating bollinger bands
            if hasattr(self, 'last_price') and self.last_price is not None:
                price_change = ((self.current_candle.close - self.last_price) / self.last_price) * 100
                if abs(price_change) >= 5.0:  # Alert on 5%+ price changes
                    price_info = {
                        'price': self.current_candle.close,
                        'market_cap': 0  # Market cap not available in this context
                    }
                    self.notification_logger.notify_and_log_price_alert(
                        price_info=price_info,
                        symbol=self.symbol,
                        percent_change=price_change,
                        account_alias=self.account_alias,
                        strategy_name=self.strategy_name
                    )

            self.last_price = self.current_candle.close
            self.bollinger_bands.update(self.current_candle.close)

            if self.bollinger_bands.is_ready:
                self.startup_complete = True

            if self.startup_complete:
                self._execute_strategy_logic()

    def _process_fill_message(self, message: dict):
        """Process transaction data messages"""
        if message['data']['isSnapshot']:
            return

        event = FillEvent.from_hyperliquid_message(message['data']['fills'])
        self._handle_fill_event(event)

    def _validate_candle_event(self, event: OHLCVEvent) -> bool:
        """Verify the validity of the K-line event"""
        if event.start_time <= self.latest_candle_watermark:
            logging.info(event.symbol + "-Skipping candle with start time before latest watermark.")
            return False
        if event.end_time >= dt.datetime.now():
            logging.info(event.symbol + "-Skipping incomplete candle.")
            return False
        return True

    def _execute_strategy_logic(self):
        """Enforcement Strategy Logic"""
        if self.strategy_state == MVBBState.NEUTRAL:
            self._handle_neutral_state()
        elif self.strategy_state == MVBBState.LONG:
            self._handle_long_state()
        elif self.strategy_state == MVBBState.SHORT:
            self._handle_short_state()
        else:
            raise ValueError(f"Unknown strategy state: {self.strategy_state}")

    def _set_resting_open_orders(self, trade_size_usd: float | None = None):
        """Set place limit orders to open positions"""
        if trade_size_usd is None:
            existing_position_value = self._get_entry_asset_value()
            useable_trade_size_usd = self.trade_size_usd - existing_position_value
        else:
            useable_trade_size_usd = trade_size_usd

        if useable_trade_size_usd < self.min_trade_size_usd:
            logging.info(f"Trade size USD {useable_trade_size_usd} is below minimum threshold {self.min_trade_size_usd}. No orders placed.")
            return

        # 在布林带下轨放置买入限价单
        buy_result = self.hl_exchange.order(
            name=self.symbol,
            is_buy=True,
            sz=round_values(useable_trade_size_usd / self.bollinger_bands.lower_band, self.max_decimals_sz),
            limit_px=round_values(self.bollinger_bands.lower_band, self.max_decimals_px),
            order_type={"limit": {"tif": "Gtc"}},
        )
        print(f"Buy order result: {buy_result}")

        # 在布林带上轨放置卖出限价单
        sell_result = self.hl_exchange.order(
            name=self.symbol,
            is_buy=False,
            sz=round_values(useable_trade_size_usd / self.bollinger_bands.upper_band, self.max_decimals_sz),
            limit_px=round_values(self.bollinger_bands.upper_band, self.max_decimals_px),
            order_type={"limit": {"tif": "Gtc"}},
        )
        print(f"Sell order result: {sell_result}")

        # Notify orders placed and log
        if buy_result.get("status") == "ok" and sell_result.get("status") == "ok":
            self.notification_logger.notify_and_log_strategy_execution(
                strategy_name=self.strategy_name,
                symbol=self.symbol,
                action="PLACE_NEUTRAL_ORDERS",
                account_alias=self.account_alias,
                details="Both buy and sell limit orders placed successfully",
                status="completed"
            )


    def _handle_neutral_state(self):
        """处理中性状态 - 在布林带上下轨放置限价单"""
        self.order_system.cancel_all_orders(self.symbol)

        # Send strategy execution notification and log
        self.notification_logger.notify_and_log_strategy_execution(
            strategy_name=self.strategy_name,
            symbol=self.symbol,
            action="PLACE_NEUTRAL_ORDERS",
            account_alias=self.account_alias,
            details=f"Placing buy order at {self.bollinger_bands.lower_band:.4f} and sell order at {self.bollinger_bands.upper_band:.4f}",
            status="started"
        )

        self._set_resting_open_orders()

    def _handle_long_state(self):
        """处理多头状态 - 设置止损止盈订单"""
        bb_range_half = (-self.bollinger_bands.lower_band + self.bollinger_bands.middle_band)
        self.order_system.cancel_all_orders(self.symbol)

        self._set_resting_open_orders()

        # Setting Stop Loss Orders
        self._place_stop_loss_order(bb_range_half, is_long=True)

        # Setting Take Profit Orders
        self._place_take_profit_order(bb_range_half, is_long=True)

    def _handle_short_state(self):
        """处理空头状态 - 设置止损止盈订单"""
        bb_range_half = (self.bollinger_bands.upper_band - self.bollinger_bands.middle_band)
        self.order_system.cancel_all_orders(self.symbol)

        self._set_resting_open_orders()

        # Setting Stop Loss Orders
        self._place_stop_loss_order(bb_range_half, is_long=False)

        # Setting Take Profit Orders
        self._place_take_profit_order(bb_range_half, is_long=False)

    def _place_stop_loss_order(self, bb_range_half: float, is_long: bool):
        """Placing Stop Loss Orders"""
        if is_long:
            trigger_price = self.bollinger_bands.lower_band - (bb_range_half * self.stop_loss_multiplier)
            is_buy = False
        else:
            trigger_price = self.bollinger_bands.upper_band + (bb_range_half * self.stop_loss_multiplier)
            is_buy = True

        stop_order_type = {
            "trigger": {
                "triggerPx": round_values(trigger_price, self.max_decimals_px),
                "isMarket": True,
                "tpsl": "sl"
            }
        }

        self.hl_exchange.order(
            name=self.symbol,
            is_buy=is_buy,
            sz=abs(self._get_current_asset_quantity()),
            limit_px=round_values(trigger_price, self.max_decimals_px),
            order_type=stop_order_type,
        )

    def _place_take_profit_order(self, bb_range_half: float, is_long: bool):
        """Placement of Take Profit Orders"""
        if is_long:
            trigger_price = self.bollinger_bands.lower_band + (bb_range_half * self.take_profit_multiplier)
            is_buy = False
        else:
            trigger_price = self.bollinger_bands.upper_band - (bb_range_half * self.take_profit_multiplier)
            is_buy = True

        tp_order_type = {
            "trigger": {
                "triggerPx": round_values(trigger_price, self.max_decimals_px),
                "isMarket": True,
                "tpsl": "tp"
            }
        }

        self.hl_exchange.order(
            name=self.symbol,
            is_buy=is_buy,
            sz=abs(self._get_current_asset_quantity()),
            limit_px=round_values(trigger_price, self.max_decimals_px),
            order_type=tp_order_type,
        )

    def _handle_fill_event(self, event: FillEvent):
        """Handling of closing events"""
        self.notification_logger.notify_and_log_trade(
            tx_hash=str(event.order.transaction_id) if hasattr(event.order, 'transaction_id') else "N/A",
            amount=abs(event.order.quantity),
            estimated_usd_value=abs(event.order.quantity * event.order.price),
            symbol=self.symbol,
            token_symbol=self.symbol,
            action_type=event.side,
            account_alias=self.account_alias,
            strategy_name=self.strategy_name
        )

        self._determine_strategy_state()
        self._execute_strategy_logic()

    def _determine_strategy_state(self):
        """Determine the current strategy state based on existing positions"""
        positions = self.order_system.get_position(self.symbol)
        if positions is None or positions['size'] == 0:
            self.strategy_state = MVBBState.NEUTRAL
        elif positions['side'] == 'long':
            self.strategy_state = MVBBState.LONG
        elif positions['side'] == 'short':
            self.strategy_state = MVBBState.SHORT