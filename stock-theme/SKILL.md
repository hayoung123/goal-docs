---
name: stock-theme
description: >-
  한국 주식(코스피+코스닥) 전종목에서 그날의 강한 테마를 자동 탐지하는 스킬.
  거래량 폭발도, 등락률, breadth, 시총 가중을 종합해 시장이 어디로 쏠렸는지
  리포트한다. "오늘 강한 테마", "한국 시장 테마 분석", "코스피 코스닥 주도 테마",
  "장 마감 후 시장 분위기", "오늘 한국 시장에서 뭐가 강했어" 같은 요청에 사용.
  무료 데이터(FinanceDataReader + 네이버 증권)만 사용.
---

# stock-theme

한국 주식 시장에서 그날그날 **강한 테마**를 자동으로 찾아주는 스킬.

## 트리거 조건

다음과 같은 사용자 요청에 트리거:

- "오늘 강한 테마 찾아줘"
- "한국 시장 테마 분석"
- "코스피/코스닥 주도 테마"
- "장 마감 후 시장 분위기"
- "오늘 한국 시장에서 뭐가 강했어"
- "어제 한국 주식 강세 섹터"

## 사전 준비 (최초 1회)

스킬 디렉토리에서 venv + 의존성 설치 (Python 3.10+ 필요):

```bash
cd ~/.claude/skills/stock-theme
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install finance-datareader pandas pyarrow numpy requests beautifulsoup4 lxml pyyaml tabulate
```

`uv`가 있으면 `uv sync` 한 줄로 대체.

## 실행 방법

스킬 디렉토리에서:

```bash
.venv/bin/python scripts/main_analyzer.py --date today --top 10
```

### 인자

- `--date`: `today`(기본값) / `YYYYMMDD` (오늘 외에는 캐시 키로만 사용. FDR StockListing은 현재 스냅샷만 제공)
- `--top`: 상위 몇 개 테마를 보여줄지 (기본 10)
- `--min-value`: 종목 최소 거래대금(원). 노이즈 컷, 기본 1e9 (10억)
- `--min-mcap`: 종목 최소 시총(원). 기본 None
- `--dry-run`: 실제 데이터 수집 없이 캐시 점검만
- `--refresh-themes`: 테마 매핑 캐시 강제 갱신 (네이버 재스크래핑)
- `--force-data`: OHLCV 캐시 무시하고 재수집

## 동작 순서

1. `data_collector`: FinanceDataReader로 KOSPI+KOSDAQ 전종목 스냅샷 수집(약 5초). 캐시 hit 시 즉시 재사용.
2. `theme_mapper`: 네이버 증권 테마 페이지 스크래핑 → 실패/희소 시 `reference/theme_dict.yaml` 폴백. 일 1회 캐시.
3. `scorer`: 종목 점수(등락률 + 시장 중간 거래대금 대비 vol_intensity) → 테마 점수(시총가중+breadth+종목수 보정) 집계.
4. `report_generator`: `output/report_YYYYMMDD.{json,md}` 생성.
5. stdout에 MD 경로와 상위 테마 요약 출력.

## 결과 사용 가이드 (Claude에게)

`main_analyzer.py` 실행이 끝나면 stdout에 출력된 MD 파일 경로를 `Read`로 읽어 사용자에게 다음을 전달:

1. 상위 N개 테마 요약 표 (테마명 / 점수 / breadth / 대표 종목)
2. 한 줄 인사이트 — 예: "오늘은 AI반도체와 원전이 동반 강세, 2차전지는 거래량 폭발은 있지만 등락률이 음(-)이라 진정세"
3. 사용자가 추가로 보고 싶은 게 있으면 (특정 테마의 종목 리스트, 점수 가중치 변경 등) 옵션 제시

JSON 파일은 후속 분석/시각화용이므로 보통 안 읽어도 된다.

## 주의

- **장중에는 권장 X**. 거래소 마감 후 호출이 가장 정확. pykrx의 일별 데이터는 장중에는 미체결로 채워질 수 있음.
- **휴장일** 호출 시 가장 최근 거래일로 자동 폴백.
- **네이버 스크래핑 실패** 시 자동으로 `reference/theme_dict.yaml` 폴백 (큐레이션된 핵심 테마만 분석). 사용자에게 "폴백 모드" 명시.
- **점수 가중치**는 `config.yaml`에서 조정 가능 (모멘텀/거래량/breadth 비중).
- **테마 사전 보강**은 `reference/theme_dict.yaml`을 직접 편집.

## 트러블슈팅

- FDR `ConnectionError` → 일시 오류, 잠시 후 재시도. `--force-data`로 캐시 무시 가능.
- 네이버에서 테마 < 50개만 잡힘 → HTML 셀렉터 변동 가능성. 자동 폴백되며 리포트 헤더에 `source: static` 표기됨. `theme_mapper.py`의 `_parse_theme_list_page` 셀렉터 점검 후 PR.
- 결과 테마 score가 모두 0 → `--min-value` 너무 높을 수 있음, 낮춰서 재실행.
- 정적 사전(`reference/theme_dict.yaml`)의 종목 매핑이 부정확 → 한국 종목코드는 변경/합병 빈번. 종목명이 어색하면 yaml 직접 수정. 네이버 모드에서는 자동 정제됨.
