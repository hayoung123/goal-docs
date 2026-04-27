"""종목 점수 → 테마 점수 집계.

종목 점수:
  momentum     = clip(change_pct / momentum_norm, neg, pos)
  vol_intensity= clip(log10(max(value,1) / value_p50), 0, vol_intensity_clip)
                 # 시장 중간 거래대금 대비 상대 강도 (당일 시장 활성도 자동 보정)
  vol_kicker   = sign(change_pct) * vol_intensity
                 # 거래량은 등락률 방향을 증폭: 상승 + 거래량 폭발 = 강세, 하락 + 거래량 폭발 = 약세 가속
  liquidity    = 1 if value >= min_trade_value else 0
  stock_score  = (momentum_w * momentum + vol_w * vol_kicker) * liquidity

테마 점수:
  w_i        = mcap_i^p / Σ mcap_j^p
  weighted   = Σ w_i * stock_score_i
  breadth    = (상승 종목 수) / (테마 내 종목 수)
  n_factor   = min(log10(n+1)/log10(n_sat+1), 1.0)
  theme_score = (ws_w * weighted + br_w * breadth + n_w * n_factor) * 100
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ThemeScore:
    theme: str
    score: float
    weighted: float
    breadth: float
    n_factor: float
    n_stocks: int
    n_up: int
    representatives: list[dict]


def _stock_scores(
    ohlcv: pd.DataFrame, cfg: dict, min_value_override: float | None = None
) -> pd.DataFrame:
    s = cfg["scoring"]["stock"]
    min_value = float(min_value_override if min_value_override is not None else s["min_trade_value"])

    df = ohlcv.copy()
    for c in ["change_pct", "volume", "value", "mcap"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    momentum = (df["change_pct"] / float(s["momentum_norm"])).clip(
        lower=float(s["momentum_clip_neg"]), upper=float(s["momentum_clip_pos"])
    )

    # 거래대금 중간값 (전 종목 기준, 0 제외)
    nz = df.loc[df["value"] > 0, "value"]
    value_p50 = float(nz.median()) if len(nz) > 0 else 1.0
    vol_intensity_clip = float(s.get("vol_intensity_clip", 3.0))
    log_ratio = np.log10(np.maximum(df["value"].values, 1.0) / max(value_p50, 1.0))
    vol_intensity = np.clip(log_ratio, 0.0, vol_intensity_clip)
    vol_kicker = np.sign(df["change_pct"].values) * vol_intensity

    liquidity = (df["value"] >= min_value).astype(float)

    df["momentum"] = momentum
    df["vol_intensity"] = vol_intensity
    df["vol_kicker"] = vol_kicker
    df["liquidity"] = liquidity
    df["stock_score"] = (
        float(s["momentum_weight"]) * momentum
        + float(s["vol_intensity_weight"]) * vol_kicker
    ) * liquidity
    df.attrs["value_p50"] = value_p50
    return df


def score(
    ohlcv: pd.DataFrame,
    mapping: pd.DataFrame,
    cfg: dict,
    min_value_override: float | None = None,
    min_mcap: float | None = None,
) -> tuple[list[ThemeScore], pd.DataFrame]:
    stocks = _stock_scores(ohlcv, cfg, min_value_override)

    if min_mcap is not None:
        stocks = stocks[stocks["mcap"] >= float(min_mcap)]

    joined = mapping.merge(stocks, on="ticker", how="inner")

    t = cfg["scoring"]["theme"]
    p = float(t["mcap_weight_power"])
    ws_w = float(t["weighted_score_weight"])
    br_w = float(t["breadth_weight"])
    n_w = float(t["n_factor_weight"])
    n_sat = int(t["n_factor_saturate_at"])
    min_n = int(t["min_stocks_per_theme"])

    out: list[ThemeScore] = []
    for theme, g in joined.groupby("theme"):
        n = len(g)
        if n < min_n:
            continue
        mcap_pow = np.power(np.maximum(g["mcap"].values, 0.0), p)
        denom = mcap_pow.sum()
        w = (mcap_pow / denom) if denom > 0 else np.full(n, 1.0 / n)
        weighted = float((w * g["stock_score"].values).sum())
        n_up = int((g["change_pct"] > 0).sum())
        breadth = n_up / n
        n_factor = min(np.log10(n + 1) / np.log10(n_sat + 1), 1.0)

        score_val = (ws_w * weighted + br_w * breadth + n_w * n_factor) * 100.0

        rep_cols = [
            "ticker",
            "name",
            "market",
            "prev_close",
            "close",
            "change_abs",
            "change_pct",
            "volume",
            "value",
            "mcap",
            "momentum",
            "vol_intensity",
            "stock_score",
        ]
        rep_cols = [c for c in rep_cols if c in g.columns]
        reps = (
            g.sort_values("stock_score", ascending=False)[rep_cols].to_dict(orient="records")
        )
        out.append(
            ThemeScore(
                theme=str(theme),
                score=score_val,
                weighted=weighted,
                breadth=breadth,
                n_factor=float(n_factor),
                n_stocks=n,
                n_up=n_up,
                representatives=reps,
            )
        )

    out.sort(key=lambda x: x.score, reverse=True)
    return out, stocks


if __name__ == "__main__":
    print("scorer module — invoke via main_analyzer.py")
