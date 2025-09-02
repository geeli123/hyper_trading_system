import datetime as dt
import logging
from copy import copy
from enum import Enum

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

from candle_helpers import aggregate_ohlcv
from events import OHLCVEvent, FillEvent
from indicators import BollingerBands
from order_system import BasicOrderSystem
from utils import round_values


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
    ):
        self.hl_info = info
        self.hl_exchange = exchange
        self.address = address
        self.max_decimals_sz = max_decimals_sz
        self.max_decimals_px = max_decimals_px
        self.order_system = BasicOrderSystem(self.hl_info, self.hl_exchange, self.address)

        self.symbol = symbol
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

        self._start_up()

    def _get_state(self, timestamp):
        return {
            "timestamp": timestamp,
            "strategy_state": self.strategy_state,
            "bb_upper": self.bollinger_bands.upper_band,
            "bb_middle": self.bollinger_bands.middle_band,
            "bb_lower": self.bollinger_bands.lower_band,
        }

    def _get_current_asset_quantity(self):
        return self.order_system.get_position(self.symbol)['size']

    def _start_up(self):
        startup_candles = self.hl_info.candles_snapshot(
            self.symbol,
            f"{self.input_candle_periods}{self.input_candle_unit}",
            int((dt.datetime.now() - dt.timedelta(hours=24)).timestamp() * 1000),
            int(dt.datetime.now().timestamp() * 1000)
        )
        print(len(startup_candles))
        for candle in startup_candles[:-1]:  # Skip the last candle as it is incomplete
            event = OHLCVEvent.from_hyperliquid_message(candle)
            if event.start_time <= self.latest_candle_watermark:
                print("Skipping candle with start time before latest watermark.")
                continue
            self.latest_candle_watermark = event.start_time
            is_complete, self.current_candle = aggregate_ohlcv(event, self.current_candle, self.target_candle_periods,
                                                               self.target_candle_unit)

            if is_complete:
                self.bollinger_bands.update(self.current_candle.close)
                self.last_full_candle = copy(self.current_candle)
        self.startup_complete = True
        print("Startup complete. Bollinger Bands initialized.")
        print(f"Current Bollinger Bands: {self.bollinger_bands.bands}")
        print(f"Latest message: {self.latest_candle_watermark}")
        self.order_system.cancel_all_orders(self.symbol)

        positions = self.order_system.get_position("ETH")
        print("show positions", positions)
        if positions is None or positions['size'] == 0:
            self.strategy_state = MVBBState.NEUTRAL
        elif positions['side'] == 'long':
            self.strategy_state = MVBBState.LONG
        elif positions['side'] == 'short':
            self.strategy_state = MVBBState.SHORT

        self.order_system.cancel_all_orders(self.symbol)

        if self.strategy_state == MVBBState.NEUTRAL:
            logging.info("Strategy state is NEUTRAL. Placing initial limit orders at Bollinger Bands.")
            result = self.hl_exchange.order(
                name=self.symbol,
                is_buy=True,
                sz=round_values(self.trade_size_usd / self.bollinger_bands.lower_band, self.max_decimals_sz),
                limit_px=round_values(self.bollinger_bands.lower_band, self.max_decimals_px),
                order_type={"limit": {"tif": "Gtc"}},
            )
            logging.info(f"Initial long order result: {result}")
            result = self.hl_exchange.order(
                name=self.symbol,
                is_buy=False,
                sz=round_values(self.trade_size_usd / self.bollinger_bands.upper_band, self.max_decimals_sz),
                limit_px=round_values(self.bollinger_bands.upper_band, self.max_decimals_px),
                order_type={"limit": {"tif": "Gtc"}},
            )
        elif self.strategy_state == MVBBState.LONG:
            bb_range_half = (-self.bollinger_bands.lower_band + self.bollinger_bands.middle_band)
            self.order_system.cancel_all_orders(self.symbol)

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
                sz=self._get_current_asset_quantity(),
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
                sz=self._get_current_asset_quantity(),
                limit_px=round_values(
                    self.bollinger_bands.upper_band - (bb_range_half * self.take_profit_multiplier),
                    self.max_decimals_px),
                order_type=tp_order_type,
        )

    def process_message(self, message: dict):
        """
        Processes a new market event.
        """
        print(self.order_system.get_open_orders(self.symbol))

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
            print("Skipping candle with start time before latest watermark.")
            return False
        if event.end_time >= dt.datetime.now():
            print("Skipping incomplete candle.")
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

    def _handle_neutral_state(self):
        """处理中性状态 - 在布林带上下轨放置限价单"""
        self.order_system.cancel_all_orders(self.symbol)

        # 在布林带下轨放置买入限价单
        buy_result = self.hl_exchange.order(
            name=self.symbol,
            is_buy=True,
            sz=round_values(self.trade_size_usd / self.bollinger_bands.lower_band, self.max_decimals_sz),
            limit_px=round_values(self.bollinger_bands.lower_band, self.max_decimals_px),
            order_type={"limit": {"tif": "Gtc"}},
        )
        print(f"Buy order result: {buy_result}")

        # 在布林带上轨放置卖出限价单
        sell_result = self.hl_exchange.order(
            name=self.symbol,
            is_buy=False,
            sz=round_values(self.trade_size_usd / self.bollinger_bands.upper_band, self.max_decimals_sz),
            limit_px=round_values(self.bollinger_bands.upper_band, self.max_decimals_px),
            order_type={"limit": {"tif": "Gtc"}},
        )
        print(f"Sell order result: {sell_result}")

    def _handle_long_state(self):
        """处理多头状态 - 设置止损止盈订单"""
        bb_range_half = (-self.bollinger_bands.lower_band + self.bollinger_bands.middle_band)
        self.order_system.cancel_all_orders(self.symbol)

        # Setting Stop Loss Orders
        self._place_stop_loss_order(bb_range_half, is_long=True)

        # Setting Take Profit Orders
        self._place_take_profit_order(bb_range_half, is_long=True)

    def _handle_short_state(self):
        """处理空头状态 - 设置止损止盈订单"""
        bb_range_half = (self.bollinger_bands.upper_band - self.bollinger_bands.middle_band)
        self.order_system.cancel_all_orders(self.symbol)

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
            sz=self._get_current_asset_quantity(),
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
            sz=self._get_current_asset_quantity(),
            limit_px=round_values(trigger_price, self.max_decimals_px),
            order_type=tp_order_type,
        )

    def _handle_fill_event(self, event: FillEvent):
        """Handling of closing events"""
        if self.strategy_state == MVBBState.NEUTRAL:
            self._handle_neutral_fill(event)
        elif self.strategy_state == MVBBState.LONG:
            self._handle_long_fill(event)
        elif self.strategy_state == MVBBState.SHORT:
            self._handle_short_fill(event)
        else:
            raise ValueError(f"Unknown strategy state: {self.strategy_state}")

    def _handle_neutral_fill(self, event: FillEvent):
        """Handling of neutral state transactions"""
        if event.order.quantity > 0:
            self.strategy_state = MVBBState.LONG
            self._setup_long_position()
        elif event.order.quantity < 0:
            self.strategy_state = MVBBState.SHORT
            self._setup_short_position()
        else:
            raise ValueError(f"Fill event with zero quantity: {event}")

    def _handle_long_fill(self, event: FillEvent):
        """Handling transactions in a long position"""
        self.strategy_state = MVBBState.NEUTRAL
        self.order_system.cancel_all_orders(self.symbol)

    def _handle_short_fill(self, event: FillEvent):
        """Handling of transactions in a short position"""
        self.strategy_state = MVBBState.NEUTRAL
        self.order_system.cancel_all_orders(self.symbol)

    def _setup_long_position(self):
        """Setting up a long position"""
        bb_range_half = (-self.bollinger_bands.lower_band + self.bollinger_bands.middle_band)
        self.order_system.cancel_all_orders(self.symbol)
        self._place_stop_loss_order(bb_range_half, is_long=True)
        self._place_take_profit_order(bb_range_half, is_long=True)

    def _setup_short_position(self):
        """Setting up a short position"""
        bb_range_half = (self.bollinger_bands.upper_band - self.bollinger_bands.middle_band)
        self.order_system.cancel_all_orders(self.symbol)
        self._place_stop_loss_order(bb_range_half, is_long=False)
        self._place_take_profit_order(bb_range_half, is_long=False)
