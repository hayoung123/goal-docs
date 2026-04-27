"""테마-종목 매핑 빌더.

전략:
  1) 네이버 증권 테마 페이지(/sise/theme.naver) 스크래핑 (페이지네이션 → 각 테마 상세)
  2) 결과 테마 수가 임계값 미만이면 reference/theme_dict.yaml 폴백
  3) 일 1회 캐시 (cache/theme_map_YYYYMMDD.json)

출력 DataFrame: ticker, theme, source, weight
  - source: "naver" or "static"
  - weight: 1.0 (현재는 동일 가중. 추후 confidence 가중 가능)
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
import yaml
from bs4 import BeautifulSoup

try:
    from .paths import CACHE_DIR, REFERENCE_DIR, load_config
except ImportError:  # pragma: no cover
    from paths import CACHE_DIR, REFERENCE_DIR, load_config  # type: ignore

logger = logging.getLogger(__name__)

NAVER_THEME_LIST = "https://finance.naver.com/sise/theme.naver"
NAVER_BASE = "https://finance.naver.com"


def _http_get(url: str, ua: str, timeout: int = 10) -> str:
    headers = {"User-Agent": ua, "Accept-Language": "ko,en;q=0.9"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "euc-kr"
    return r.text


def _parse_theme_list_page(html: str) -> list[tuple[str, str]]:
    """테마 목록 페이지에서 (theme_name, detail_url) 추출."""
    soup = BeautifulSoup(html, "lxml")
    out: list[tuple[str, str]] = []
    for a in soup.select('a[href*="sise_group_detail.naver?type=theme"]'):
        name = a.get_text(strip=True)
        href = a.get("href", "")
        if not name or not href:
            continue
        out.append((name, urljoin(NAVER_BASE, href)))
    # dedup
    seen: dict[str, str] = {}
    for n, u in out:
        seen.setdefault(n, u)
    return list(seen.items())


def _parse_theme_detail(html: str) -> list[str]:
    """테마 상세 페이지에서 종목 코드 list 추출 (6자리 ticker)."""
    soup = BeautifulSoup(html, "lxml")
    tickers: list[str] = []
    for a in soup.select('a[href*="/item/main.naver?code="]'):
        href = a.get("href", "")
        m = re.search(r"code=(\d{6})", href)
        if m:
            tickers.append(m.group(1))
    return list(dict.fromkeys(tickers))  # preserve order, dedup


def _scrape_naver(cfg: dict) -> pd.DataFrame:
    ua = cfg["theme_mapping"]["naver_user_agent"]
    throttle = float(cfg["theme_mapping"]["naver_throttle_sec"])

    themes: dict[str, str] = {}
    for page in range(1, 8):  # 보통 6~7페이지에서 끝
        url = f"{NAVER_THEME_LIST}?&page={page}"
        try:
            html = _http_get(url, ua)
        except Exception as e:
            logger.warning("[theme_mapper] list page %d 실패: %s", page, e)
            continue
        page_themes = _parse_theme_list_page(html)
        if not page_themes:
            break
        themes.update(page_themes)
        time.sleep(throttle)

    logger.info("[theme_mapper] naver: %d 테마 수집됨", len(themes))

    rows: list[dict] = []
    for i, (name, detail_url) in enumerate(themes.items(), 1):
        try:
            html = _http_get(detail_url, ua)
            tickers = _parse_theme_detail(html)
        except Exception as e:
            logger.debug("[theme_mapper] detail '%s' 실패: %s", name, e)
            continue
        for t in tickers:
            rows.append({"ticker": t, "theme": name, "source": "naver", "weight": 1.0})
        if i % 30 == 0:
            logger.info("[theme_mapper] %d/%d 테마 처리", i, len(themes))
        time.sleep(throttle)

    return pd.DataFrame(rows, columns=["ticker", "theme", "source", "weight"])


def _load_static(cfg: dict) -> pd.DataFrame:
    path = REFERENCE_DIR / Path(cfg["theme_mapping"]["static_dict_path"]).name
    if not path.exists():
        return pd.DataFrame(columns=["ticker", "theme", "source", "weight"])
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    rows: list[dict] = []
    for theme, items in (data.get("themes") or {}).items():
        for t in items or []:
            tk = str(t).zfill(6)
            rows.append({"ticker": tk, "theme": theme, "source": "static", "weight": 1.0})
    return pd.DataFrame(rows, columns=["ticker", "theme", "source", "weight"])


def build(refresh: bool = False) -> tuple[pd.DataFrame, dict]:
    """테마-종목 매핑 빌드.

    Returns (df, meta) — meta: {"source": "naver"|"static"|"hybrid", "n_themes": int, "stale": bool}
    """
    cfg = load_config()
    today = datetime.now().strftime("%Y%m%d")
    cache_path: Path = CACHE_DIR / f"theme_map_{today}.json"

    if cache_path.exists() and not refresh:
        logger.info("[theme_mapper] cache hit: %s", cache_path.name)
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        df = pd.DataFrame(payload["rows"])
        return df, payload["meta"]

    min_themes = cfg["theme_mapping"]["naver_min_themes"]
    df_naver = _scrape_naver(cfg)
    n_themes_naver = df_naver["theme"].nunique() if not df_naver.empty else 0

    if n_themes_naver >= min_themes:
        df_static = _load_static(cfg)
        df = pd.concat([df_naver, df_static], ignore_index=True).drop_duplicates(
            subset=["ticker", "theme"], keep="first"
        )
        meta = {"source": "hybrid" if not df_static.empty else "naver", "n_themes": int(df["theme"].nunique())}
    else:
        logger.warning(
            "[theme_mapper] naver 부족(%d < %d), 정적 사전 폴백", n_themes_naver, min_themes
        )
        df = _load_static(cfg)
        meta = {"source": "static", "n_themes": int(df["theme"].nunique()) if not df.empty else 0}

    if df.empty:
        raise RuntimeError("테마 매핑이 비어있습니다. 네트워크 또는 정적 사전을 확인하세요.")

    cache_path.write_text(
        json.dumps({"rows": df.to_dict(orient="records"), "meta": meta}, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(
        "[theme_mapper] %d rows / %d themes (source=%s) cached", len(df), meta["n_themes"], meta["source"]
    )
    return df, meta


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--refresh", action="store_true")
    args = p.parse_args()

    df, meta = build(refresh=args.refresh)
    print(meta)
    print(df.head())
    print("themes:", df["theme"].nunique(), "rows:", len(df))
