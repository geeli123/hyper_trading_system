import eth_account
from eth_account.signers.local import LocalAccount
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

from database.session import Environment


def setup(base_url=None, skip_ws=False, perp_dexs=None, environment=None, secret_key=None, account_address=None):
    if base_url == None:
        base_url = constants.TESTNET_API_URL if environment == Environment.dev else constants.MAINNET_API_URL
    account: LocalAccount = eth_account.Account.from_key(secret_key)
    print("Running with account address:", account_address)
    if account_address != account.address:
        print("Running with agent address:", account.address)
    info = Info(base_url, skip_ws, perp_dexs=perp_dexs)
    user_state = info.user_state(account_address)
    spot_user_state = info.spot_user_state(account_address)
    margin_summary = user_state["marginSummary"]
    print(margin_summary)
    if float(margin_summary["accountValue"]) == 0 and len(spot_user_state["balances"]) == 0:
        print("Not running the example because the provided account has no equity.")
        url = info.base_url.split(".", 1)[1]
        error_string = f"No accountValue:\nIf you think this is a mistake, make sure that {account_address} has a balance on {url}.\nIf address shown is your API wallet address, update the config to specify the address of your account, not the address of the API wallet."
        raise Exception(error_string)
    exchange = Exchange(account, base_url, account_address=account_address, perp_dexs=perp_dexs)
    return account_address, info, exchange
