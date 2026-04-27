# Scoring Methodology

## 종목 점수 (stock_score)

```
momentum      = clip(change_pct / momentum_norm, neg, pos)
vol_intensity = clip(log10(max(value, 1) / value_p50), 0, vol_intensity_clip)
vol_kicker    = sign(change_pct) * vol_intensity
liquidity     = 1 if value >= min_trade_value else 0
stock_score   = (momentum_w * momentum + vol_intensity_w * vol_kicker) * liquidity
```

`vol_kicker`는 거래량을 등락률 부호 방향으로 적용해, **상승 + 거래량 폭발은 강세 가속, 하락 + 거래량 폭발은 약세 가속**으로 해석한다 (뉴스 호재로 거래량과 함께 오르는 패턴 vs 악재로 거래량과 함께 빠지는 패턴 구분).

- `momentum`: 등락률을 5%로 정규화하고 [-2, +3] 클립. 상한선이 비대칭(+3)인 이유는 한국 시장의 **상한가 30%** 가능성을 반영. 단일 종목 슈퍼스파이크가 테마 점수를 과도하게 끌어올리지 않도록 클리핑.
- `vol_intensity`: **시장 중간 거래대금 대비 상대 강도**(log10). 그날의 KRX 전종목 거래대금 중간값(value_p50)을 분모로 잡아, 시장 활성도가 자동으로 보정됨. log10 = 0 이면 평범, 1이면 10배, 2이면 100배. 음수(중간값 이하)는 0으로 클립해 약세 종목에 추가 페널티 없음.
- 왜 20일 평균 거래량이 아닌가: FinanceDataReader 무료 API는 일자별 스냅샷만 빠르게 제공하고, 종목별 20일 히스토리는 종목 단위 호출이라 2,800종목 전수에 비효율. 시장 중간값 대비는 계산 비용 0이면서 시장 전체 활성도를 자동 보정해 trade-off가 좋음.
- `liquidity`: 거래대금 < 10억(기본) 종목은 노이즈 컷. 작전성 급등주가 테마 점수를 흔드는 것 방지.
- 가중치: 모멘텀 0.45 / vol_intensity 0.45 (등가중). 한국 시장은 거래량 동반 여부가 테마 강도의 핵심 시그널이라 등가중을 디폴트로 둠.

## 테마 점수 (theme_score)

```
w_i        = mcap_i^p / Σ mcap_j^p           (p = mcap_weight_power, 기본 0.5)
weighted   = Σ w_i * stock_score_i
breadth    = (테마 내 상승 종목 수) / (테마 내 종목 수)
n_factor   = min(log10(n+1)/log10(n_sat+1), 1.0)
theme_score = (ws_w * weighted + br_w * breadth + n_w * n_factor) * 100
```

- `mcap_weight_power=0.5` (제곱근 가중): 시총 비례(p=1.0)는 대형주에 의해 테마 점수가 결정되어 "테마"의 의미가 흐려짐. 균등(p=0.0)은 잡주에 휩쓸림. 제곱근 가중이 둘 사이의 절충.
- `breadth`: 테마 내 상승 비율. 한 종목만 폭등하고 나머지가 빠지는 경우(가짜 테마) 페널티.
- `n_factor`: 종목 수 보정. 종목 < 3 컷 + log 포화로 "10종목짜리 테마"와 "100종목짜리 테마"가 비슷하게 평가되도록 함.
- 가중치: weighted 0.50 / breadth 0.30 / n_factor 0.20. 본질은 weighted score, breadth와 n_factor는 보정.
- 마지막 `* 100`은 가독성 정규화. 일반적인 일자에서 상위 테마는 30~80 정도 점수.

## 해석 가이드

- **80 이상**: 매우 강한 테마. 다수 종목이 거래량 동반 +5% 이상, breadth > 70%.
- **40~80**: 의미 있는 테마 강세. 모멘텀이나 거래량 한쪽이 두드러짐.
- **0~40**: 약한 신호. 일부 종목만 움직임.
- **음수**: 테마 전반 약세 쏠림. 약세 테마 섹션에서 별도 표기.

## 한계

- 네이버 테마 매핑은 종목 중복이 많음 (한 종목이 5~10개 테마에 속함). 테마 점수 간 상관이 높을 수 있어, 상위 N개를 그대로 베팅 후보로 보지 말고 **클러스터/서사 단위로 재해석** 필요.
- 정적 사전 폴백은 ~15개 핵심 테마만 커버. 최신 테마(예: 갑자기 뜬 신규 테마) 누락 가능. 폴백 모드일 땐 리포트 헤더에 명시.
- vol_intensity는 **그날 시장 중간 거래대금**과의 상대값이라 절대 거래량 변동을 직접 보진 않음. 종목 자체의 평소 거래량 대비 폭발은 측정 못함. 추후 정확도가 필요하면 종목별 5/20일 평균 거래대금 캐시를 추가해 vol_burst 항목으로 보강할 수 있음.
- FDR StockListing은 "현재 스냅샷"이라 장중 호출 시 미체결가 포함. 장 마감(KST 16시) 이후 사용 권장.
