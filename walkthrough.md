# ETF EDA 정적 대시보드 구축 및 배포 자동화 완료 보고서

네이버 금융 실시간 ETF API 데이터를 활용한 10대 핵심 EDA 분석 정적 대시보드와 GitHub Actions를 활용한 스케줄링 업데이트 파이프라인의 구축을 완료하였습니다.

---

## 1. 아키텍처 개요

대시보드의 데이터 흐름 및 배포 흐름은 다음과 같습니다.

```mermaid
graph TD
    subgraph GitHub_Actions_Runner [GitHub Actions Runner (평일 09~16시 매시 정각)]
        A[collect_data.py 실행] -->|API 호출| B(네이버 금융 ETF API)
        B -->|JSON 응답 수집| A
        A -->|데이터 전처리 및 변환| C[data/etf_data.json 생성/갱신]
        C -->|Git Commit & Push| D((GitHub Repository Main Branch))
    end

    subgraph GitHub_Pages_Hosting [GitHub Pages Web Hosting]
        D -->|자동 빌드 및 배포 트리거| E[GitHub Pages CDN]
        F[index.html] -->|웹 호스팅| E
        C -->|웹 호스팅| E
    end

    subgraph User_Browser [사용자 브라우저]
        G[사용자 접속] -->|index.html 로드| E
        G -->|data/etf_data.json 비동기 fetch| E
        G -->|Plotly.js & Tailwind 렌더링| H[대화형 10대 차트 EDA 대시보드 시각화]
    end
```

---

## 2. 주요 구현 내역

### 📂 주요 신규 생성 파일
* 🐍 [collect_data.py](file:///c:/Users/student/Documents/etf-eda/src/collect_data.py): 데이터 수집 및 전처리 파이프라인 (파이썬)
* 🌐 [index.html](file:///c:/Users/student/Documents/etf-eda/index.html): 실시간 필터 및 10대 차트 EDA 대시보드 (HTML/JS)
* ⚙️ [data_update.yml](file:///c:/Users/student/Documents/etf-eda/.github/workflows/data_update.yml): GitHub Actions 자동화 워크플로우 (YAML)

---

## 3. 구현 세부 설명

### 1) 데이터 수집 및 가공 ([collect_data.py](file:///c:/Users/student/Documents/etf-eda/src/collect_data.py))
- 기존 `app.py`에 적용되어 있던 데이터 정제 로직을 온전히 보존하였습니다.
- **자산군 분류 매핑**: `etfTabCode` 값을 한글 카테고리로 변환합니다.
- **NAV 괴리율 계산**: `((현재가 - NAV) / NAV) * 100` 수식을 적용하고, 분모가 0인 종목에 대한 예외 처리를 반영하였습니다.
- **등락 트렌드 매핑**: 당일 시세 변동 상태를 '상승', '하락', '보합' 한글 태그로 매핑합니다.
- **JSON 포맷 구조화**: 정적 페이지에서 시각 정보를 즉시 노출할 수 있도록 갱신 시각(`updated_at`)과 원본 배열(`etf_items`)을 객체 구조로 묶어 저장합니다.

### 2) 대화형 웹 대시보드 ([index.html](file:///c:/Users/student/Documents/etf-eda/index.html))
- **Tailwind CSS 디자인**: 둥근 카드 모서리, 미려한 그림자 효과, 글래스모피즘 탭 효과를 가미하여 프리미엄 대시보드 레이아웃을 구현했습니다.
- **동적 필터링**: 검색어 입력, 자산군 다중 선택, 시가총액/거래대금 더블 슬라이더를 연동하여 값이 바뀔 때마다 차트와 표가 실시간으로 재랜더링됩니다.
- **Plotly.js 기반 10대 분석 차트**:
  1. **시가총액 TOP 20** 수평 막대 차트 (Blue 계열)
  2. **거래대금 TOP 20** 수평 막대 차트 (Red 계열)
  3. **당일 등락률 분포** 히스토그램 (이상치 감지 박스 연계 대응)
  4. **3개월 수익률 분포** 히스토그램 (중기 추세 모니터링)
  5. **거래량 vs 거래대금** 산점도 (단가 구조 시각화)
  6. **당일 등락률 극단값** (상승 10종 vs 하락 10종) 수평 막대 차트
  7. **3개월 수익률 TOP 10** 수평 막대 차트
  8. **시가총액 vs 거래대금 상관성** 버블 산점도 (등락률 크기 반영)
  9. **자산군별 시가총액 점유율** 도넛 차트
  10. **시가총액 규모별 NAV 괴리율** 분포 산점도
- **통계 연산**: JavaScript로 구현된 기술통계량 산출 로직을 통해 평균, 표준편차, 사분위수(25%, 50%, 75%), 피어슨 상관계수 등을 테이블에 실시간으로 출력합니다.
- **전체 테이블 정렬**: 각 테이블 헤더 클릭 시 오름차순/내림차순 정렬 기능을 바닐라 JavaScript로 가볍게 구현했습니다.

### 3) GitHub Actions 자동화 ([data_update.yml](file:///c:/Users/student/Documents/etf-eda/.github/workflows/data_update.yml))
- 한국 시간(KST) 기준 **평일 오전 9시부터 오후 4시까지 매시 정각**에 크론식(`0 0-7 * * 1-5`)을 통해 동작합니다.
- 변경된 사항이 존재할 때만 자동 커밋 및 푸시하여 GitHub Actions 리소스를 절약하고 불필요한 Git 히스토리를 방지합니다.

---

## 4. 검증 결과 및 확인 방법

### 1) 로컬 실행 및 수동 테스트
* 현재 로컬 웹 서버가 포트 `8000`에서 백그라운드로 실행 중입니다.
* 브라우저를 열고 다음 URL에 접속하여 직접 필터 조작 및 10가지 차트 전환을 확인하실 수 있습니다:
  👉 **[http://localhost:8000/index.html](http://localhost:8000/index.html)**

> [!NOTE]
> 자동화 브라우저 검사 도구(Playwright 패키지 매니저)의 외부 CDN 다운로드 이슈(404 Not Found)로 인해 서브에이전트를 통한 브라우저 자동 테스트는 스킵되었습니다. 실제 페이지 작동 상태는 위의 로컬 서버 주소로 접속하시어 직관적으로 확인하실 수 있습니다.

---

## 5. GitHub Pages 배포 설정 안내

프로젝트를 리포지토리에 푸시한 후, 아래 설정을 적용하시면 정적 페이지 호스팅이 활성화됩니다.

1. GitHub Repository의 **Settings** 탭으로 이동합니다.
2. 좌측 메뉴에서 **Pages**를 클릭합니다.
3. **Build and deployment** 섹션의 Source 설정을 `Deploy from a branch`로 선택합니다.
4. Branch 설정을 `main` 브랜치, 폴더 설정을 `/ (root)`로 지정한 뒤 **Save**를 누릅니다.
5. 약 1~2분 뒤 상단에 제공되는 GitHub Pages URL(예: `https://<username>.github.io/<repo-name>/`)로 접속하면 실시간 ETF EDA 대시보드가 정상적으로 구동됩니다.
