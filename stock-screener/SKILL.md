---
name: stock-screener
description: >-
  한국 주식(코스피+코스닥) 일일 스크리닝 스킬. 두 가지 조건으로 종목을 추출하고
  각 종목 옆에 TradingView 차트 링크를 붙여 리포트한다.
  - 조건 A: 거래대금 1000억+ & 등락률 +10%+ (대형주 강한 상승)
  - 조건 B: 등락률 +20%+ (급등주, 거래대금 10억 컷)
  "오늘 거래대금 큰 상승주", "급등주 스크리닝", "20% 이상 오른 종목",
  "오늘 차트 봐야할 종목", "한국장 강한 종목 찾아줘" 같은 요청에 사용.
  무료 데이터(FinanceDataReader)만 사용.
---

# stock-screener

한국 주식 시장에서 매일 두 가지 스크리닝 조건에 부합하는 종목을 추출하고 TradingView 차트 링크를 붙여주는 스킬.

## 트리거 조건

다음과 같은 사용자 요청에 트리거:

- "오늘 거래대금 큰 상승주 보여줘"
- "급등주 스크리닝"
- "오늘 20% 이상 오른 종목"
- "오늘 차트 봐야할 종목"
- "한국장 강한 종목 찾아줘"
- "오늘 스크리너 돌려줘"

## 스크리닝 조건

| 조건 | 거래대금 | 등락률 | 의도 |
|---|---|---|---|
| **A · 대형주 강한 상승** | ≥ 1,000억 | ≥ +10% | 시장 주도주 (유동성+모멘텀) |
| **B · 급등주** | ≥ 10억 | ≥ +20% | 단기 폭발 종목 (저유동성 노이즈만 컷) |

값은 `config.yaml`에서 조정 가능.

## 사전 준비 (최초 1회)

스킬 디렉토리에서 venv + 의존성 설치 (Python 3.11+ 필요):

```bash
cd ~/.claude/skills/stock-screener
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install finance-datareader pandas pyarrow pyyaml tabulate
```

## 실행 방법

스킬 디렉토리에서:

```bash
.venv/bin/python scripts/main.py --date today
```

### 인자

- `--date`: `today`(기본) / `YYYYMMDD` (캐시 키로만 사용. FDR StockListing은 현재 스냅샷만 제공)
- `--force-data`: OHLCV 캐시 무시하고 재수집

## 동작 순서

1. `data_collector`: FinanceDataReader로 KOSPI+KOSDAQ 전종목 스냅샷 수집(약 5초). 캐시 hit 시 재사용.
2. `screener`: 두 조건으로 필터링, 각 종목에 TradingView URL 부착 (KOSPI→`KRX-`, KOSDAQ→`KOSDAQ-`).
3. `report_generator`: `output/screener_YYYYMMDD.{json,md}` 생성.
4. stdout에 MD 경로와 매칭 카운트, 상위 5개 미리보기 출력.

## 결과 사용 가이드 (Claude에게)

`main.py` 실행이 끝나면 stdout에 출력된 MD 파일 경로를 `Read`로 읽어 사용자에게 다음을 전달:

1. 두 조건별 매칭 종목 표 (종목/티커/시장/전일→종가/거래대금/시총/TradingView 링크)
2. 한 줄 인사이트 — 예: "조건 A 2건 모두 반도체. 조건 B는 로보틱스 1건"
3. 매칭 0건이면 "오늘은 해당 조건 종목 없음" 명시

JSON 파일은 후속 분석/시각화용.

## TradingView 링크 형식

- 모든 KRX 종목: `https://www.tradingview.com/chart/?symbol=KRX%3A{ticker}`
- KOSPI/KOSDAQ 구분 없이 `KRX:` prefix로 통일 (TradingView chart URL이 자동 해석)

마크다운 링크로 출력되므로 Claude Code/IDE에서 바로 클릭 가능.

## 주의

- **장중에는 권장 X**. 거래소 마감 후(KST 16:00 이후) 호출이 가장 정확. FDR 스냅샷은 장중엔 미체결가일 수 있음.
- **휴장일** 호출 시 가장 최근 거래일 데이터가 들어옴 (리포트 헤더의 날짜로 확인).
- **NXT(Nextrade)** 거래는 KRX 공식 통계 미포함이라 본 스킬도 다루지 않음.
- **임계값 조정**은 `config.yaml`에서 (`screens.big_movers.min_value` 등).

## 트러블슈팅

- FDR `ConnectionError` → 일시 오류, `--force-data`로 재시도.
- 매칭 0건 → 임계값이 너무 빡빡할 수 있음. config에서 `min_change_pct` 또는 `min_value` 완화.
- TradingView 링크가 빈 페이지 → 종목코드는 맞지만 TradingView가 인덱싱 안한 종목(상장 직후 등). 차트는 네이버/한투에서 조회.
