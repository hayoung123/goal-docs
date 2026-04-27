"""FinanceDataReader 기반 코스피+코스닥 일별 시세 스냅샷 수집 + 캐시.

출력 컬럼:
  ticker, name, market, close, change_pct, volume, value, mcap

주의:
  fdr.StockListing('KRX') 는 "현재" 스냅샷이라 장중에는 미체결가가 포함될 수 있음.
  운영상 장 마감 후(KST 16시 이후) 호출 권장.
  과거 특정 날짜 데이터는 fdr.DataReader 로 종목별 호출이 필요해 비싸므로,
  본 스킬은 "오늘"(또는 가장 최근 마감일) 분석에 집중.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    from .paths import CACHE_DIR
except ImportError:  # pragma: no cover
    from paths import CACHE_DIR  # type: ignore

logger = logging.getLogger(__name__)

KOREAN_MARKETS = {"KOSPI", "KOSDAQ"}


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.rename(
        columns={
            "Code": "ticker",
            "Name": "name",
            "Market": "market",
            "Close": "close",
            "ChagesRatio": "change_pct",
            "Changes": "change_abs",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Volume": "volume",
            "Amount": "value",
            "Marcap": "mcap",
        }
    )
    out = out[out["market"].isin(KOREAN_MARKETS)].copy()
    cols = [
        "ticker", "name", "market",
        "open", "high", "low", "close",
        "change_abs", "change_pct",
        "volume", "value", "mcap",
    ]
    out = out[cols]
    out["ticker"] = out["ticker"].astype(str).str.zfill(6)
    for c in ["open", "high", "low", "close", "change_abs", "change_pct", "volume", "value", "mcap"]:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)
    # 전일 종가 = 오늘 종가 - 일중 변동
    out["prev_close"] = (out["close"] - out["change_abs"]).clip(lower=0)
    return out.reset_index(drop=True)


def collect(date: str = "today", force: bool = False) -> tuple[pd.DataFrame, str]:
    """date='today' or 'YYYYMMDD'. 'today' 외의 값은 캐시 키로만 사용 (FDR 호출은 항상 현재 스냅샷).

    Returns (df, resolved_date).
    """
    import FinanceDataReader as fdr  # noqa: N813

    if date.lower() == "today":
        resolved = datetime.now().strftime("%Y%m%d")
    else:
        # 사용자가 특정 날짜를 지정해도 FDR Snapshot은 현재만 제공함을 경고
        resolved = date
        logger.warning(
            "[data_collector] FDR StockListing은 과거 날짜를 직접 제공하지 않음. "
            "캐시된 %s 데이터가 있으면 사용, 없으면 현재 스냅샷을 %s 로 저장.",
            resolved,
            resolved,
        )

    cache_path: Path = CACHE_DIR / f"ohlcv_{resolved}.parquet"
    if cache_path.exists() and not force:
        logger.info("[data_collector] cache hit: %s", cache_path.name)
        return pd.read_parquet(cache_path), resolved

    logger.info("[data_collector] FDR StockListing 호출")
    raw = fdr.StockListing("KRX")
    df = _normalize(raw)

    if df.empty:
        raise RuntimeError("FDR StockListing 결과가 비어있습니다.")

    df.to_parquet(cache_path, index=False)
    logger.info("[data_collector] cached %d rows -> %s", len(df), cache_path.name)
    return df, resolved


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--date", default="today")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    df, resolved = collect(args.date, force=args.force)
    print(f"[ok] {resolved}: {len(df)} 종목")
    print(df.head(8))
    print()
    print("change_pct describe:")
    print(df["change_pct"].describe())
