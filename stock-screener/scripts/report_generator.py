"""스크리닝 결과 → JSON + Markdown 리포트."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from tabulate import tabulate

try:
    from .paths import OUTPUT_DIR, load_config
except ImportError:  # pragma: no cover
    from paths import OUTPUT_DIR, load_config  # type: ignore

logger = logging.getLogger(__name__)


def _fmt_money(v: float) -> str:
    if v is None or v != v:
        return "-"
    if v >= 1e12:
        return f"{v/1e12:.2f}조"
    if v >= 1e8:
        return f"{v/1e8:.0f}억"
    if v >= 1e4:
        return f"{v/1e4:.0f}만"
    return f"{v:.0f}"


def _fmt_pct(v: float) -> str:
    if v is None or v != v:
        return "-"
    return f"{v:+.2f}%"


def _fmt_price(v: float) -> str:
    if v is None or v != v:
        return "-"
    return f"{int(round(v)):,}"


def _fmt_price_change(prev: float, curr: float, change_pct: float) -> str:
    if prev is None or prev != prev or curr is None or curr != curr:
        return "-"
    return f"{_fmt_price(prev)} → {_fmt_price(curr)} ({_fmt_pct(change_pct)})"


def _row(rec: dict) -> list:
    return [
        rec["name"],
        rec["ticker"],
        rec["market"],
        _fmt_price_change(rec.get("prev_close"), rec.get("close"), rec.get("change_pct")),
        _fmt_money(rec.get("value")),
        _fmt_money(rec.get("mcap")),
        f"[TradingView]({rec.get('tradingview_url', '')})",
    ]


HEADERS = ["종목", "티커", "시장", "전일→종가 (등락률)", "거래대금", "시총", "차트"]


def generate(
    results: dict[str, pd.DataFrame],
    resolved_date: str,
) -> tuple[Path, Path]:
    cfg = load_config()
    screens_cfg = cfg["screens"]

    json_path = OUTPUT_DIR / f"screener_{resolved_date}.json"
    md_path = OUTPUT_DIR / f"screener_{resolved_date}.md"

    payload = {
        "date": resolved_date,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "screens": {},
    }
    for name, df in results.items():
        payload["screens"][name] = {
            "label": screens_cfg[name]["label"],
            "params": {
                "min_value": float(screens_cfg[name]["min_value"]),
                "min_change_pct": float(screens_cfg[name]["min_change_pct"]),
            },
            "n": len(df),
            "rows": df.to_dict(orient="records"),
        }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    lines: list[str] = []
    lines.append(f"# 한국 시장 일일 스크리닝 — {resolved_date}")
    lines.append("")
    total = sum(len(df) for df in results.values())
    lines.append(f"_총 매칭: {total}건 · 생성 {datetime.now().strftime('%Y-%m-%d %H:%M')} KST_")
    lines.append("")

    for i, (name, df) in enumerate(results.items(), 1):
        label = screens_cfg[name]["label"]
        lines.append(f"## 조건 {chr(64+i)} · {label}")
        lines.append(f"> 매칭 종목: **{len(df)}개**")
        lines.append("")
        if df.empty:
            lines.append("_해당 종목 없음_")
            lines.append("")
            continue
        rows = [_row(r) for r in df.to_dict(orient="records")]
        lines.append(tabulate(rows, headers=HEADERS, tablefmt="github"))
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("[report] %s, %s", json_path.name, md_path.name)
    return json_path, md_path
