import getpass
import json
import os

import eth_account
from eth_account.signers.local import LocalAccount
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

from config.config import load_config


def setup(base_url=None, skip_ws=False, perp_dexs=None, environment=None):
    # Load configuration
    config = load_config(environment)

    # Use config's base_url if not provided as parameter
    if base_url is None:
        base_url = config.get('base_url')
    account: LocalAccount = eth_account.Account.from_key(get_secret_key(config))
    address = config['account_address']
    if address == "":
        address = account.address
    print("Running with account address:", address)
    if address != account.address:
        print("Running with agent address:", account.address)
    info = Info(base_url, skip_ws, perp_dexs=perp_dexs)
    user_state = info.user_state(address)
    spot_user_state = info.spot_user_state(address)
    margin_summary = user_state["marginSummary"]
    print(margin_summary)
    if float(margin_summary["accountValue"]) == 0 and len(spot_user_state["balances"]) == 0:
        print("Not running the example because the provided account has no equity.")
        url = info.base_url.split(".", 1)[1]
        error_string = f"No accountValue:\nIf you think this is a mistake, make sure that {address} has a balance on {url}.\nIf address shown is your API wallet address, update the config to specify the address of your account, not the address of the API wallet."
        raise Exception(error_string)
    exchange = Exchange(account, base_url, account_address=address, perp_dexs=perp_dexs)
    return address, info, exchange


def get_secret_key(config):
    if config['secret_key']:
        secret_key = config['secret_key']
    else:
        keystore_path = config['keystore_path']
        keystore_path = os.path.expanduser(keystore_path)
        if not os.path.isabs(keystore_path):
            keystore_path = os.path.join(os.path.dirname(__file__), keystore_path)
        if not os.path.exists(keystore_path):
            raise FileNotFoundError(f"Keystore file not found: {keystore_path}")
        if not os.path.isfile(keystore_path):
            raise ValueError(f"Keystore path is not a file: {keystore_path}")
        with open(keystore_path) as f:
            keystore = json.load(f)
        password = getpass.getpass("Enter keystore password: ")
        secret_key = eth_account.Account.decrypt(keystore, password)
    return secret_key


def setup_multi_sig_wallets(environment=None):
    # Load configuration
    config = load_config(environment)

    # Multi-sig functionality removed from basic config structure
    # This would need to be implemented separately if needed
    authorized_user_wallets = []
    print("Multi-sig functionality not implemented in current config structure")
    return authorized_user_wallets
