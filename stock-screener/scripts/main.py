"""stock-screener — 오케스트레이터.

실행:
  .venv/bin/python scripts/main.py --date today
  .venv/bin/python scripts/main.py --date today --force-data

출력:
  output/screener_YYYYMMDD.{md,json}
"""
from __future__ import annotations

import argparse
import logging

try:
    from . import data_collector, report_generator, screener
    from .paths import load_config
except ImportError:  # pragma: no cover
    import data_collector  # type: ignore
    import report_generator  # type: ignore
    import screener  # type: ignore
    from paths import load_config  # type: ignore


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="stock-screener")
    p.add_argument("--date", default="today", help="YYYYMMDD 또는 'today' (기본)")
    p.add_argument("--force-data", action="store_true", help="OHLCV 캐시 무시하고 재수집")
    return p.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s",
                        datefmt="%H:%M:%S")
    log = logging.getLogger("main")
    args = parse_args()
    cfg = load_config()

    log.info("step 1/3: OHLCV 수집")
    ohlcv, resolved = data_collector.collect(args.date, force=args.force_data)
    log.info("  -> %s, %d 종목", resolved, len(ohlcv))

    log.info("step 2/3: 스크리닝")
    results = screener.run(ohlcv, cfg)
    for name, df in results.items():
        log.info("  -> %s: %d", name, len(df))

    log.info("step 3/3: 리포트 생성")
    json_path, md_path = report_generator.generate(results, resolved)

    print()
    print(f"date: {resolved}")
    for name, df in results.items():
        label = cfg["screens"][name]["label"]
        print(f"  {name}: {len(df)}건 ({label})")
        for r in df.head(5).to_dict(orient="records"):
            print(f"    - {r['name']} ({r['ticker']}) {r['change_pct']:+.2f}% · {r['tradingview_url']}")
    print()
    print(f"[report] {md_path}")
    print(f"[json]   {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
