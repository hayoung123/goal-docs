---
layout: default
title: goal-docs
---

# 📈 한국 시장 데일리 리포트

매일 마감 후(KST 16:00 이후) 자동 생성되는 스크리너 + 테마 분석.

## 🔍 종목 스크리너 (일일)

거래대금 1,000억+ & +10%+ (대형주 강한 상승), +20%+ (급등주) 두 조건.

{% assign screener_md = site.pages | where_exp: "p", "p.path contains 'stock-screener/screener_'" | sort: 'path' | reverse %}
<ul>
{% for p in screener_md %}
  <li><a href="{{ p.url | relative_url }}">{{ p.path | split: '/' | last | replace: '.md','' }}</a></li>
{% endfor %}
</ul>

## 🪙 코인 스크리너 (일일)

업비트 KRW 마켓. 지속 강세(현재 +10%+) / 장중 펌핑(고점 +20%+) 두 조건.

{% assign crypto_md = site.pages | where_exp: "p", "p.path contains 'crypto-screener/screener_'" | sort: 'path' | reverse %}
<ul>
{% for p in crypto_md %}
  <li><a href="{{ p.url | relative_url }}">{{ p.path | split: '/' | last | replace: '.md','' }}</a></li>
{% endfor %}
</ul>

## 🔥 테마 분석 (일일)

거래량 폭발도 + 등락률 + breadth + 시총 가중 종합 테마 탐지.

{% assign theme_md = site.pages | where_exp: "p", "p.path contains 'stock-theme/report_'" | sort: 'path' | reverse %}
<ul>
{% for p in theme_md %}
  <li><a href="{{ p.url | relative_url }}">{{ p.path | split: '/' | last | replace: '.md','' }}</a></li>
{% endfor %}
</ul>

---

[GitHub repo](https://github.com/hayoung123/goal-docs) · [README](./README.html)
