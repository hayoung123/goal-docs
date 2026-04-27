"""오케스트레이터: 데이터 수집 → 매핑 → 점수화 → 리포트.

사용:
  uv run python scripts/main_analyzer.py --date today --top 10
  uv run python scripts/main_analyzer.py --date 20260424 --top 15 --min-value 2e9
"""
from __future__ import annotations

import argparse
import logging
import sys

try:
    from . import data_collector, report_generator, scorer, theme_mapper
    from .paths import load_config
except ImportError:  # pragma: no cover
    import data_collector  # type: ignore
    import report_generator  # type: ignore
    import scorer  # type: ignore
    import theme_mapper  # type: ignore
    from paths import load_config  # type: ignore


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="한국 주식 강한 테마 자동 탐지")
    p.add_argument("--date", default="today", help="YYYYMMDD or 'today' (기본 today)")
    p.add_argument("--top", type=int, default=None, help="상위 몇 테마 (기본 config.report.default_top)")
    p.add_argument("--min-value", type=float, default=None, help="종목 최소 거래대금(원). config 오버라이드")
    p.add_argument("--min-mcap", type=float, default=None, help="종목 최소 시총(원)")
    p.add_argument("--dry-run", action="store_true", help="캐시 점검만 (실제 수집/스코어링 X)")
    p.add_argument("--refresh-themes", action="store_true", help="테마 매핑 캐시 강제 갱신")
    p.add_argument("--force-data", action="store_true", help="OHLCV 캐시 무시하고 재수집")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("main_analyzer")
    cfg = load_config()

    if args.dry_run:
        try:
            from .paths import CACHE_DIR, OUTPUT_DIR
        except ImportError:
            from paths import CACHE_DIR, OUTPUT_DIR  # type: ignore
        log.info("[dry-run] cache files: %s", sorted(p.name for p in CACHE_DIR.glob("*")))
        log.info("[dry-run] output files: %s", sorted(p.name for p in OUTPUT_DIR.glob("*")))
        return 0

    # 1. OHLCV
    log.info("step 1/4: OHLCV 수집")
    ohlcv, resolved = data_collector.collect(args.date, force=args.force_data)
    log.info("  -> %s, %d 종목", resolved, len(ohlcv))

    # 2. 테마 매핑
    log.info("step 2/4: 테마 매핑")
    mapping, mapping_meta = theme_mapper.build(refresh=args.refresh_themes)
    log.info("  -> source=%s, %d 테마, %d rows", mapping_meta["source"], mapping_meta["n_themes"], len(mapping))

    # 3. 점수화
    log.info("step 3/4: 점수화")
    theme_scores, _ = scorer.score(
        ohlcv, mapping, cfg, min_value_override=args.min_value, min_mcap=args.min_mcap
    )
    log.info("  -> %d 테마 점수 산출", len(theme_scores))

    # 4. 리포트
    log.info("step 4/4: 리포트 생성")
    json_path, md_path = report_generator.generate(
        theme_scores, resolved_date=resolved, mapping_meta=mapping_meta, top=args.top
    )

    top_n = args.top if args.top is not None else int(cfg["report"]["default_top"])
    print()
    print(f"date: {resolved}")
    print(f"mapping: {mapping_meta}")
    print(f"top {min(top_n, len(theme_scores))} 테마:")
    for i, t in enumerate(theme_scores[:top_n], 1):
        reps = ", ".join(r["name"] for r in t.representatives[:3])
        print(
            f"  {i:2d}. {t.theme:20s}  score={t.score:6.1f}  "
            f"breadth={t.breadth*100:3.0f}%  n={t.n_stocks:3d}  | {reps}"
        )
    print()
    print(f"[report] {md_path}")
    print(f"[json]   {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
