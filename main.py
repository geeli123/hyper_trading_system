from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

from perps_api import PerpsAPI
from perps_helper import list_dex_names, coin_mark_prices
from ws_client import demo_run as ws_demo_run


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True))


def _safe(label: str, func):
    try:
        obj = func()
        _print(obj)
    except Exception as e:
        _print({"error": f"{label} failed", "detail": str(e)})


def run_demo() -> int:
    api = PerpsAPI()

    print("Perp DEX names:")
    _safe("list_dex_names", lambda: list_dex_names(api))

    print("\nMeta (first dex) universe excerpt:")
    def _meta_excerpt():
        meta = api.get_meta()
        universe = meta.get("universe", []) if isinstance(meta, dict) else []
        return universe[:5]

    _safe("get_meta", _meta_excerpt)

    print("\nCoin mark prices (from metaAndAssetCtxs):")
    _safe("coin_mark_prices", lambda: coin_mark_prices(api))

    print("\nPredicted fundings (first 3 entries):")
    def _predicted_excerpt():
        predicted = api.get_predicted_fundings()
        return predicted[:3] if isinstance(predicted, list) else predicted

    _safe("get_predicted_fundings", _predicted_excerpt)

    print("\nPerps at open interest cap:")
    _safe("get_perps_at_open_interest_cap", lambda: api.get_perps_at_open_interest_cap())

    print("\nPerp deploy auction status:")
    _safe("get_perp_deploy_auction_status", lambda: api.get_perp_deploy_auction_status())

    # Optional: if a user address is provided via env, show their clearinghouse state and activeAssetData for ETH
    user = os.environ.get("HL_USER_ADDRESS")
    if user:
        print("\nUser clearinghouse state (summary):")
        def _ch_summary():
            ch_state = api.get_clearinghouse_state(user)
            keys = [
                "marginSummary",
                "crossMarginSummary",
                "assetPositions",
                "withdrawable",
            ]
            if isinstance(ch_state, dict):
                return {k: ch_state.get(k) for k in keys}
            return ch_state

        _safe("get_clearinghouse_state", _ch_summary)

        print("\nUser active asset data for ETH:")
        _safe("get_active_asset_data", lambda: api.get_active_asset_data(user=user, coin="ETH"))

        # Show last 24h funding and non-funding ledger updates
        now = datetime.now(timezone.utc)
        start = int((now - timedelta(days=1)).timestamp() * 1000)
        print("\nUser funding updates (24h):")
        _safe("get_user_funding", lambda: api.get_user_funding(user=user, start_time_ms=start))
        print("\nUser non-funding ledger updates (24h):")
        _safe("get_user_non_funding_ledger_updates", lambda: api.get_user_non_funding_ledger_updates(user=user, start_time_ms=start))

    return 0


if __name__ == "__main__":
    ws_demo_run(10.0)
    