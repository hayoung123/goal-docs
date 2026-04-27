"""두 가지 조건으로 종목 필터 + TradingView URL 부여.

조건:
  big_movers: value >= min_value AND change_pct >= min_change_pct  (기본 1000억 & +10%)
  surge:     value >= min_value AND change_pct >= min_change_pct  (기본 10억   & +20%)
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def _filter(df: pd.DataFrame, min_value: float, min_change_pct: float) -> pd.DataFrame:
    out = df[(df["value"] >= float(min_value)) & (df["change_pct"] >= float(min_change_pct))]
    return out.sort_values("change_pct", ascending=False).reset_index(drop=True)


def add_tradingview_url(df: pd.DataFrame, templates: dict[str, str]) -> pd.DataFrame:
    if df.empty:
        df = df.copy()
        df["tradingview_url"] = pd.Series(dtype="object")
        return df
    df = df.copy()
    df["tradingview_url"] = df.apply(
        lambda r: templates.get(r["market"], "").format(ticker=r["ticker"]),
        axis=1,
    )
    return df


def run(ohlcv: pd.DataFrame, cfg: dict) -> dict[str, pd.DataFrame]:
    screens = cfg["screens"]
    templates = cfg["tradingview"]["url_template"]

    results: dict[str, pd.DataFrame] = {}
    for name, params in screens.items():
        filtered = _filter(
            ohlcv,
            min_value=float(params["min_value"]),
            min_change_pct=float(params["min_change_pct"]),
        )
        with_url = add_tradingview_url(filtered, templates)
        results[name] = with_url
        logger.info("[screener] %s: %d 종목", name, len(with_url))
    return results


if __name__ == "__main__":
    print("screener module — invoke via main.py")
