"""테마 점수 → JSON + Markdown 리포트."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from tabulate import tabulate

try:
    from .paths import OUTPUT_DIR, load_config
    from .scorer import ThemeScore
except ImportError:  # pragma: no cover
    from paths import OUTPUT_DIR, load_config  # type: ignore
    from scorer import ThemeScore  # type: ignore

logger = logging.getLogger(__name__)


def _fmt_money(v: float) -> str:
    if v is None or v != v:  # NaN
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
    """예: 220,000→222,500 (+1.14%)"""
    if prev is None or prev != prev or curr is None or curr != curr:
        return "-"
    return f"{_fmt_price(prev)} → {_fmt_price(curr)} ({_fmt_pct(change_pct)})"


def generate(
    theme_scores: list[ThemeScore],
    resolved_date: str,
    mapping_meta: dict,
    top: int | None = None,
) -> tuple[Path, Path]:
    cfg = load_config()
    if top is None:
        top = int(cfg["report"]["default_top"])
    reps_cfg = cfg["report"]["representatives_per_theme"]
    reps_n: int | None = None if reps_cfg in (None, 0, "all") else int(reps_cfg)
    show_neg = bool(cfg["report"]["show_negative_themes"])

    # JSON
    json_path = OUTPUT_DIR / f"report_{resolved_date}.json"
    payload = {
        "date": resolved_date,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mapping": mapping_meta,
        "themes": [asdict(t) for t in theme_scores],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown
    md_path = OUTPUT_DIR / f"report_{resolved_date}.md"
    lines: list[str] = []
    lines.append(f"# 한국 시장 강한 테마 리포트 — {resolved_date}")
    lines.append("")
    lines.append(
        f"_매핑 소스: **{mapping_meta.get('source', '?')}** "
        f"(테마 {mapping_meta.get('n_themes', '?')}개) / 분석 테마 {len(theme_scores)}개_"
    )
    lines.append("")

    # 상위 테마 요약 표
    lines.append(f"## 상위 {top} 테마")
    lines.append("")
    summary_rows = []
    for i, t in enumerate(theme_scores[:top], 1):
        rep_names = ", ".join(r["name"] for r in t.representatives[:3])
        summary_rows.append(
            [
                i,
                t.theme,
                f"{t.score:.1f}",
                f"{t.breadth*100:.0f}%",
                f"{t.n_up}/{t.n_stocks}",
                rep_names,
            ]
        )
    lines.append(
        tabulate(
            summary_rows,
            headers=["#", "테마", "점수", "breadth", "상승/전체", "대표 종목"],
            tablefmt="github",
        )
    )
    lines.append("")

    # 테마별 상세
    lines.append("## 테마별 상세")
    lines.append("")
    for t in theme_scores[:top]:
        lines.append(f"### {t.theme}  ·  score {t.score:.1f}")
        lines.append(
            f"- weighted: {t.weighted:+.3f} / breadth: {t.breadth*100:.0f}% "
            f"({t.n_up}/{t.n_stocks}) / n_factor: {t.n_factor:.2f}"
        )
        lines.append("")
        reps_to_show = t.representatives if reps_n is None else t.representatives[:reps_n]
        rows = []
        for r in reps_to_show:
            rows.append(
                [
                    r["name"],
                    r["ticker"],
                    r["market"],
                    _fmt_price_change(r.get("prev_close"), r.get("close"), r["change_pct"]),
                    _fmt_money(r["value"]),
                    f"{r.get('vol_intensity', 0):.2f}",
                    _fmt_money(r["mcap"]),
                    f"{r['stock_score']:.2f}",
                ]
            )
        lines.append(
            tabulate(
                rows,
                headers=[
                    "종목",
                    "티커",
                    "시장",
                    "전일→종가 (등락률)",
                    "거래대금",
                    "vol×median(log)",
                    "시총",
                    "score",
                ],
                tablefmt="github",
            )
        )
        lines.append("")

    # 약세 테마
    if show_neg:
        weak = [t for t in theme_scores if t.score < 0][-5:]
        if weak:
            lines.append("## 약세 쏠림 테마 (참고)")
            lines.append("")
            weak_rows = [
                [t.theme, f"{t.score:.1f}", f"{t.breadth*100:.0f}%", f"{t.n_up}/{t.n_stocks}"]
                for t in weak
            ]
            lines.append(
                tabulate(weak_rows, headers=["테마", "점수", "breadth", "상승/전체"], tablefmt="github")
            )
            lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("[report] %s, %s", json_path.name, md_path.name)
    return json_path, md_path
