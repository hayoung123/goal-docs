# goal

한국 주식 시장 일일 리포트 자동 생성을 위한 Claude Code Skills 모음.
모두 무료 데이터(인증/API 키 불필요)만 사용한다.

---

## Skills

### `stock-screener` — 일일 종목 스크리너

매일 두 가지 조건으로 종목을 필터링하고 TradingView 차트 링크를 붙여 리포트.

| 조건 | 거래대금 | 등락률 | 의도 |
|---|---|---|---|
| **A · 대형주 강한 상승** | ≥ 1,000억 | ≥ +10% | 시장 주도주 (유동성+모멘텀) |
| **B · 급등주** | ≥ 10억 | ≥ +20% | 단기 폭발 종목 (저유동성 노이즈만 컷) |

임계값은 `stock-screener/config.yaml`에서 조정.

### `stock-theme` — 일일 강한 테마 탐지

코스피+코스닥 전종목에서 그날의 주도 테마를 정량화.
**거래량 폭발도 + 등락률 + breadth(테마 내 상승종목 비율) + 시총 가중**을
종합 점수화해 시장이 어디로 쏠렸는지 산출.

가중치는 `stock-theme/config.yaml`에서 조정.

---

## 데이터 소스 (어떤 API?)

| 소스 | 사용처 | 인증 | 비고 |
|---|---|---|---|
| **FinanceDataReader** (FDR) | 두 스킬 모두 — KOSPI/KOSDAQ 전종목 OHLCV 스냅샷 | 불필요 | 한국거래소 데이터를 KRX 마감 후 수집. `StockListing("KRX")`는 "현재" 스냅샷 |
| **네이버 증권 테마 페이지** | `stock-theme`만 — 종목↔테마 매핑 스크래핑 | 불필요 | 일 1회 캐시. 실패 시 정적 사전(`stock-theme/reference/theme_dict.yaml`) 자동 폴백 |
| **TradingView 차트 URL** | `stock-screener` — 리포트 내 차트 링크 | 불필요 | URL만 생성 (API 호출 없음). `https://www.tradingview.com/chart/?symbol=KRX:{ticker}` |

장 마감 후(KST 16:00 이후) 호출이 정확. 장중에는 미체결가일 수 있음.
NXT(Nextrade)는 KRX 공식 통계 미포함이라 다루지 않음.

---

## 사용 방법

### Claude Code에서

자연어 또는 슬래시 커맨드:

```
/stock-screener
/stock-theme
```

또는

```
오늘 거래대금 큰 상승주 보여줘
오늘 강한 테마 찾아줘
```

리포트는 `~/Desktop/goal/{skill}/screener_YYYYMMDD.{md,json}` (또는 `report_…`)로 저장.

### 셸에서 마지막 리포트 빠르게 보기

```bash
stock_screener   # glow로 오늘자 screener .md 렌더링
stock_theme      # glow로 오늘자 theme .md 렌더링
```

(별칭은 `~/.zshrc`에서 정의)

### 직접 실행 (Claude 없이)

```bash
cd ~/.claude/skills/stock-screener
.venv/bin/python scripts/main.py --date today

cd ~/.claude/skills/stock-theme
.venv/bin/python scripts/main_analyzer.py --date today --top 10
```

---

## 디렉토리 구조

```
~/Desktop/goal/
├── README.md                          # 이 파일
├── stock-screener/                    # 스킬 소스 + 일일 리포트
│   ├── SKILL.md
│   ├── config.yaml
│   ├── pyproject.toml
│   ├── scripts/
│   │   ├── main.py
│   │   ├── data_collector.py
│   │   ├── screener.py
│   │   ├── report_generator.py
│   │   └── paths.py
│   └── screener_YYYYMMDD.{md,json}    # 일자별 리포트 누적
└── stock-theme/
    ├── SKILL.md
    ├── config.yaml
    ├── pyproject.toml
    ├── scripts/
    │   ├── main_analyzer.py
    │   ├── data_collector.py
    │   ├── theme_mapper.py
    │   ├── scorer.py
    │   ├── report_generator.py
    │   └── paths.py
    ├── reference/
    │   └── theme_dict.yaml            # 네이버 폴백용 정적 테마 사전
    └── report_YYYYMMDD.{md,json}
```

> **운영 위치**: 실제 실행되는 스킬은 `~/.claude/skills/{stock-screener,stock-theme}/`에 있음.
> 본 디렉토리는 **소스 스냅샷 + 리포트 저장소**. 스킬 코드를 수정하면 양쪽을 동기화 필요.
> venv와 parquet 캐시는 운영 위치에만 존재 (재현 가능한 산출물이라 복사 제외).

---

## 사전 준비 (최초 1회)

각 스킬 운영 위치(`~/.claude/skills/{skill}/`)에서:

```bash
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e .
```

Python 3.11+ 필요.
