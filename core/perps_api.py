from __future__ import annotations

import typing as _t

import requests


class PerpsAPI:
    """Thin wrapper over the Hyperliquid info API for perpetuals.

    Docs reference: POST https://api.hyperliquid.xyz/info
    """

    def __init__(self, base_url: str = "https://api.hyperliquid.xyz/info", timeout_seconds: float = 10.0):
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def _post(self, payload: dict) -> _t.Any:
        response = self._session.post(self._base_url, json=payload, timeout=self._timeout_seconds)
        response.raise_for_status()
        return response.json()

    # -------------------------------
    # Perps-specific info endpoints
    # -------------------------------
    def get_perp_dexs(self) -> _t.Any:
        """Retrieve all perpetual dexs."""
        return self._post({"type": "perpDexs"})

    def get_meta(self, dex: str = "") -> _t.Any:
        """Retrieve perpetuals metadata (universe and margin tables).

        Args:
            dex: Perp dex name. Empty string selects the first perp dex.
        """
        return self._post({"type": "meta", "dex": dex})

    def get_meta_and_asset_ctxs(self) -> _t.Any:
        """Retrieve perpetuals asset contexts along with meta."""
        return self._post({"type": "metaAndAssetCtxs"})

    def get_clearinghouse_state(self, user: str, dex: str = "") -> _t.Any:
        """Retrieve user's perpetuals account summary.

        Args:
            user: 42-character hex onchain address.
            dex: Perp dex name. Empty string selects the first perp dex.
        """
        return self._post({"type": "clearinghouseState", "user": user, "dex": dex})

    def get_user_funding(self, user: str, start_time_ms: int, end_time_ms: int | None = None) -> _t.Any:
        """Retrieve a user's funding history.

        Args:
            user: 42-character hex onchain address.
            start_time_ms: Inclusive start time (ms).
            end_time_ms: Inclusive end time (ms). Defaults to server current time.
        """
        payload: dict[str, _t.Any] = {"type": "userFunding", "user": user, "startTime": start_time_ms}
        if end_time_ms is not None:
            payload["endTime"] = end_time_ms
        return self._post(payload)

    def get_user_non_funding_ledger_updates(self, user: str, start_time_ms: int, end_time_ms: int | None = None) -> _t.Any:
        """Retrieve a user's non-funding ledger updates (deposits, transfers, withdrawals)."""
        payload: dict[str, _t.Any] = {"type": "userNonFundingLedgerUpdates", "user": user, "startTime": start_time_ms}
        if end_time_ms is not None:
            payload["endTime"] = end_time_ms
        return self._post(payload)

    def get_funding_history(self, coin: str, start_time_ms: int, end_time_ms: int | None = None) -> _t.Any:
        """Retrieve historical funding rates for a coin."""
        payload: dict[str, _t.Any] = {"type": "fundingHistory", "coin": coin, "startTime": start_time_ms}
        if end_time_ms is not None:
            payload["endTime"] = end_time_ms
        return self._post(payload)

    def get_predicted_fundings(self) -> _t.Any:
        """Retrieve predicted funding rates for different venues."""
        return self._post({"type": "predictedFundings"})

    def get_perps_at_open_interest_cap(self) -> _t.Any:
        """Query perps at open interest caps."""
        return self._post({"type": "perpsAtOpenInterestCap"})

    def get_perp_deploy_auction_status(self) -> _t.Any:
        """Retrieve information about the Perp Deploy Auction."""
        return self._post({"type": "perpDeployAuctionStatus"})

    def get_active_asset_data(self, user: str, coin: str) -> _t.Any:
        """Retrieve user's active asset data for a coin."""
        return self._post({"type": "activeAssetData", "user": user, "coin": coin})


