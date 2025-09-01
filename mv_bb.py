from copy import copy
from enum import Enum
import datetime as dt

from hyperliquid.info import Info
from hyperliquid.exchange import Exchange

from candle_helpers import aggregate_ohlcv
from events import OHLCVEvent, FillEvent
from indicators import BollingerBands
from order_system import BasicOrderSystem
from utils import round_values

import logging

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
            event = OHLCVEvent.from_hyperliquid_message(message['data'])
            if event.start_time <= self.latest_candle_watermark:
                print("Skipping candle with start time before latest watermark.")
                return
            if event.end_time >= dt.datetime.now():
                print("Skipping incomplete candle.")
                return
            self.latest_candle_watermark = event.start_time
            is_complete, self.current_candle = aggregate_ohlcv(event, self.current_candle, self.target_candle_periods,
                                                               self.target_candle_unit)

            if is_complete:
                print(self.strategy_state)
                self.bollinger_bands.update(self.current_candle.close)

                if self.bollinger_bands.is_ready:
                    self.startup_complete = True

                if self.startup_complete:
                    # handle case where we have no open positions - set limit orders
                    if self.strategy_state == MVBBState.NEUTRAL:
                        self.order_system.cancel_all_orders(self.symbol)

                        print(self.hl_exchange.order(
                            name=self.symbol,
                            is_buy=True,
                            sz=round_values(self.trade_size_usd / self.bollinger_bands.lower_band, self.max_decimals_sz),
                            limit_px=round_values(self.bollinger_bands.lower_band, self.max_decimals_px),
                            order_type={"limit": {"tif": "Gtc"}},
                        ))
                        print(self.hl_exchange.order(
                            name=self.symbol,
                            is_buy=False,
                            sz=round_values(self.trade_size_usd / self.bollinger_bands.upper_band, self.max_decimals_sz),
                            limit_px=round_values(self.bollinger_bands.upper_band, self.max_decimals_px),
                            order_type={"limit": {"tif": "Gtc"}},
                        ))

                    # handle case where we are long - set limit orders / stop loss orders
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
                    else:
                        raise ValueError(f"Unknown strategy state: {self.strategy_state}")
        elif message['channel'] == 'userFills':
            if not message['data']['isSnapshot']:
                event = FillEvent.from_hyperliquid_message(message['data']['fills'])

                # if strategy neutral
                if self.strategy_state == MVBBState.NEUTRAL:
                    if event.order.quantity > 0:
                        self.strategy_state = MVBBState.LONG

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

                    elif event.order.quantity < 0:
                        self.strategy_state = MVBBState.SHORT

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
                    else:
                        raise ValueError(f"Fill event with zero quantity: {event}")
                # if strategy long
                elif self.strategy_state == MVBBState.LONG:
                    self.strategy_state = MVBBState.NEUTRAL
                    self.order_system.cancel_all_orders(self.symbol)
                # if strategy short
                elif self.strategy_state == MVBBState.SHORT:
                    self.strategy_state = MVBBState.NEUTRAL
                    self.order_system.cancel_all_orders(self.symbol)
                else:
                    raise ValueError(f"Unknown strategy state: {self.strategy_state}")
        else:
            raise ValueError(f"Message type {message['channel']} not supported.")
