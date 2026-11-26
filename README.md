# claude_trade — 미국 시가총액 Top 100 대시보드

세 페이지로 된 정적 웹 대시보드입니다.

1. **Top 100 주가 차트**: 시가총액 상위 100개 종목의 최근 2년 일별 수정 종가. 종목은 최대 8개까지 수익률(%)로 비교할 수 있습니다.
2. **Top 10 변동률**: 1일, 1주, 1개월, 3개월, 6개월, YTD, 1년, 2년 수익률을 막대 차트, 히트맵 표, 종목별 미니 차트로 보여줍니다.
3. **1위 고점 모니터링**: 시가총액 1위 기업의 사상 최고가 대비 하락률, 경보 단계(주의/경고/위험), 주요 하락 구간 표.

## 구조

| 경로 | 역할 |
|---|---|
| `scripts/fetch_data.py` | 후보 종목을 실시간 시가총액으로 정렬해 상위 100개를 고르고, 2년 일봉과 1위 기업의 전체 이력을 받아 `data/data.json`에 저장 |
| `scripts/build_site.py` | `web/index.html`에 데이터를 넣어 단일 파일 `site/index.html` 생성 |
| `.github/workflows/update-data.yml` | 매일 오전 6시 5분(KST)에 데이터를 갱신해 커밋하고, 기본 브랜치에서는 GitHub Pages로 배포 |

## 로컬 실행

```bash
pip install yfinance pandas
python scripts/fetch_data.py
python scripts/build_site.py
open site/index.html
```

## GitHub Pages

저장소 **Settings → Pages → Source: GitHub Actions**를 선택하세요. 그다음 기본 브랜치에서 워크플로가 실행되면 배포됩니다.
