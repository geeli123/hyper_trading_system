from hyperliquid.info import Info  
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
import example_utils
from hyperliquid.utils import constants
import time   
# Or explicitly enable WebSocket  
def callback(msg):  
    print("callback")
    print(f"Received: {msg}")  


address, info, exchange = example_utils.setup(base_url=constants.MAINNET_API_URL, skip_ws=False)

# Subscribe with the callback  
subscription = {"type": "allMids"}


while True:
    result= info.subscribe(subscription, callback)
    print(result)
    print("subscribed")
    print(info.ws_manager.active_subscriptions)
    print(info.ws_manager.ws_ready)
    time.sleep(1)






# user_state = info.user_state("0xB6001dDB4ecf684A226361812476f731CEA96d05")
# print(user_state)

# Place an order that should rest by setting the price very low
# order_result = exchange.order("ETH", True, 0.2, 1100, {"limit": {"tif": "Gtc"}})
# print(order_result)

# open_orders = info.open_orders(address)
# for open_order in open_orders:
#     print(f"cancelling order {open_order}")
#     exchange.cancel(open_order["coin"], open_order["oid"])

