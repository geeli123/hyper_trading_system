from perps_api import PerpsAPI


def list_dex_names(api: PerpsAPI) -> list[str]:
    result = api.get_perp_dexs()
    names: list[str] = []
    if isinstance(result, list):
        for entry in result:
            if isinstance(entry, list) and len(entry) == 2 and isinstance(entry[1], dict):
                name = entry[1].get("name")
                if isinstance(name, str):
                    names.append(name)
    return names


def fetch_universe_and_ctxs(api: PerpsAPI) -> tuple[list[dict], list[dict]]:
    result = api.get_meta_and_asset_ctxs()
    if not (isinstance(result, list) and len(result) == 2):
        return [], []
    meta_obj, ctxs = result
    universe = meta_obj.get("universe", []) if isinstance(meta_obj, dict) else []
    ctxs_list = ctxs if isinstance(ctxs, list) else []
    return universe, ctxs_list


def coin_to_ctx(api: PerpsAPI) -> dict[str, dict]:
    universe, ctxs = fetch_universe_and_ctxs(api)
    mapping: dict[str, dict] = {}
    for asset, ctx in zip(universe, ctxs):
        coin = asset.get("name") if isinstance(asset, dict) else None
        if isinstance(coin, str) and isinstance(ctx, dict):
            mapping[coin] = ctx
    return mapping


def coin_mark_prices(api: PerpsAPI) -> dict[str, float]:
    mapping = coin_to_ctx(api)
    result: dict[str, float] = {}
    for coin, ctx in mapping.items():
        mark_px_raw = ctx.get("markPx")
        try:
            if isinstance(mark_px_raw, str):
                result[coin] = float(mark_px_raw)
        except (TypeError, ValueError):
            continue
    return result


