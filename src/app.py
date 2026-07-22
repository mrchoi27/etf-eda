"""
네이버 금융 실시간 ETF API 데이터를 활용한 종합 EDA 대시보드 모듈.

이 모듈은 네이버 금융 실시간 API로부터 ETF 정보를 실시간으로 가져와서,
메모리 내에서 전처리를 수행하고 Streamlit 웹 애플리케이션을 통해
10가지 핵심 EDA 시각화 및 비즈니스 인사이트를 제공합니다.
"""

import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Streamlit 페이지 설정
st.set_page_config(
    page_title="네이버 금융 실시간 ETF 종합 EDA 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS로 디자인 고도화
st.markdown("""
<style>
    .reportview-container {
        background: #f8f9fa;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    h1 {
        font-family: 'Outfit', 'Inter', sans-serif;
        color: #1e293b;
        font-weight: 700;
    }
    h2, h3 {
        color: #334155;
    }
    .metric-card {
        background-color: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        border: 1px solid #e2e8f0;
    }
    .stAlert {
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f1f5f9;
        border-radius: 8px 8px 0px 0px;
        gap: 8px;
        padding-left: 16px;
        padding-right: 16px;
        font-weight: 600;
        color: #475569;
    }
    .stTabs [aria-selected="true"] {
        background-color: #3b82f6 !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# 1. API 데이터 수집 함수 (캐싱 적용, 새로고침 시 갱신 가능하도록)
@st.cache_data(ttl=60) # 1분 캐시
def fetch_etf_data() -> pd.DataFrame:
    """네이버 금융 실시간 API를 통해 ETF 리스트 데이터를 수집합니다.

    이 함수는 네이버 ETF 리스트 API에 요청을 보내 원본 데이터를 가져온 뒤
    pandas DataFrame 형태로 변환하여 반환합니다. 1분간의 캐싱이 적용됩니다.

    Returns:
        pd.DataFrame: 수집된 원본 ETF 데이터프레임.
            수집에 실패하거나 오류가 발생하면 빈 데이터프레임을 반환합니다.
    """
    # _callback 파라미터를 배제하여 순수 JSON을 획득
    url = "https://finance.naver.com/api/sise/etfItemList.nhn?etfType=0&targetColumn=market_sum&sortOrder=desc"
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get("resultCode") == "success":
                item_list = data["result"]["etfItemList"]
                df = pd.DataFrame(item_list)
                return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
    return pd.DataFrame()

# 2. 데이터 전처리 함수
def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    """수집된 ETF 데이터에 대한 전처리 및 유도변수 생성을 수행합니다.

    데이터 타입 변환, 자산분류 한글 맵핑, 등락 트렌드 매핑,
    그리고 순자산가치(NAV) 괴리율 필드 산출 작업을 진행합니다.

    Args:
        df (pd.DataFrame): API로부터 수집된 가공되지 않은 원본 ETF 데이터프레임.

    Returns:
        pd.DataFrame: 수치 형변환, 파생 변수 생성이 완료된 데이터프레임.
    """
    if df.empty:
        return df
    
    # 카피본 생성하여 원본 훼손 방지
    df = df.copy()
    
    # 탭 코드 한글 이름 매핑 (한국거래소 및 네이버 분류 참고)
    tab_mapping = {
        1: "국내 시장지수",
        2: "국내 업종/테마",
        3: "국내 파생(레버리지/인버스)",
        4: "해외 주식",
        5: "원자재/대체자산",
        6: "채권/금리"
    }
    df["assetClass"] = df["etfTabCode"].map(tab_mapping).fillna("기타/해외지수")
    
    # 각 변수별 적합한 데이터 타입(수치형)으로 명시적 변환
    df["nowVal"] = pd.to_numeric(df["nowVal"], errors="coerce")
    df["changeVal"] = pd.to_numeric(df["changeVal"], errors="coerce")
    df["changeRate"] = pd.to_numeric(df["changeRate"], errors="coerce")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df["threeMonthEarnRate"] = pd.to_numeric(df["threeMonthEarnRate"], errors="coerce")
    df["quant"] = pd.to_numeric(df["quant"], errors="coerce")
    df["amonut"] = pd.to_numeric(df["amonut"], errors="coerce") # 거래대금 (백만 원 단위)
    df["marketSum"] = pd.to_numeric(df["marketSum"], errors="coerce") # 시가총액 (억 원 단위)
    
    # NAV 괴리율 계산: ((현재가 - NAV) / NAV) * 100
    df["disparityRate"] = ((df["nowVal"] - df["nav"]) / df["nav"]) * 100
    
    # risefall (등락구분) 한글화 및 기호 추가
    # 2: 상승, 5: 하락, 3: 보합 (API 리턴값 관찰 결과 기준)
    def map_risefall(row: pd.Series) -> str:
        """등락 유형(risefall)을 한글 레이블로 매핑합니다.

        Args:
            row (pd.Series): 데이터프레임의 단일 행 시리즈.

        Returns:
            str: '상승', '하락', '보합' 중 하나를 반환합니다.
        """
        val = str(row["risefall"])
        if val == "2" or row["changeVal"] > 0:
            return "상승"
        elif val == "5" or row["changeVal"] < 0:
            return "하락"
        else:
            return "보합"
    
    df["trend"] = df.apply(map_risefall, axis=1)
    
    # 결측치 처리 (수익률 등 미제공 종목은 0 또는 안전 처리)
    df["threeMonthEarnRate"] = df["threeMonthEarnRate"].fillna(0)
    df["disparityRate"] = df["disparityRate"].fillna(0)
    
    return df

# 데이터 로드 및 전처리 실행
raw_df = fetch_etf_data()
df = preprocess_data(raw_df)

# 타이틀 및 개요
st.title("📊 네이버 금융 실시간 ETF 종합 EDA 대시보드")
st.markdown("네이버 금융 API로부터 실시간으로 ETF 정보를 수집하여 데이터 파일 저장 없이 즉시 가공 및 분석하는 종합 데이터 사이언스 대시보드입니다.")

if df.empty:
    st.warning("실시간 ETF 데이터를 가져올 수 없습니다. API 서버 상태를 확인해 주세요.")
else:
    # ------------------ 사이드바 필터 ------------------
    st.sidebar.header("🔍 대화형 필터 옵션")
    
    # 수동 새로고침
    if st.sidebar.button("🔄 실시간 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()
        
    # 검색어 필터
    search_query = st.sidebar.text_input("종목명 또는 코드 검색", "").strip()
    
    # 자산군(Tab) 필터
    all_classes = sorted(df["assetClass"].unique())
    selected_classes = st.sidebar.multiselect(
        "자산군 분류 필터", 
        options=all_classes, 
        default=all_classes
    )
    
    # 시가총액 범위 필터 (억 원 단위)
    min_market_sum = int(df["marketSum"].min())
    max_market_sum = int(df["marketSum"].max())
    selected_market_range = st.sidebar.slider(
        "시가총액 범위 (억 원)",
        min_value=min_market_sum,
        max_value=max_market_sum,
        value=(min_market_sum, max_market_sum)
    )
    
    # 거래대금 범위 필터 (백만 원 단위)
    min_amount = int(df["amonut"].min())
    max_amount = int(df["amonut"].max())
    selected_amount_range = st.sidebar.slider(
        "거래대금 범위 (백만 원)",
        min_value=min_amount,
        max_value=max_amount,
        value=(min_amount, max_amount)
    )
    
    # 데이터 필터링 적용
    filtered_df = df[
        df["assetClass"].isin(selected_classes) &
        (df["marketSum"] >= selected_market_range[0]) &
        (df["marketSum"] <= selected_market_range[1]) &
        (df["amonut"] >= selected_amount_range[0]) &
        (df["amonut"] <= selected_amount_range[1])
    ]
    
    if search_query:
        filtered_df = filtered_df[
            filtered_df["itemname"].str.contains(search_query, case=False) |
            filtered_df["itemcode"].str.contains(search_query)
        ]

    # ------------------ 상단 요약 KPI 영역 ------------------
    st.subheader("📈 실시간 ETF 시장 개요 (필터 적용 기준)")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("총 상장 종목 수", f"{len(filtered_df):,} 개", 
                  delta=f"전체 대비 {len(filtered_df)/len(df)*100:.1f}%")
    with col2:
        total_market_sum_trillion = filtered_df["marketSum"].sum() * 100000000 / 1000000000000 # 조원 단위 변환
        st.metric("총 시가총액", f"{total_market_sum_trillion:.2f} 조원",
                  delta=f"평균 {filtered_df['marketSum'].mean():.1f} 억원")
    with col3:
        total_amount_billion = filtered_df["amonut"].sum() / 1000 # 십억원 단위 변환
        st.metric("당일 총 거래대금", f"{total_amount_billion:.2f} 십억원",
                  delta=f"평균 {filtered_df['amonut'].mean():.1f} 백만원")
    with col4:
        trend_counts = filtered_df["trend"].value_counts()
        up_cnt = trend_counts.get("상승", 0)
        down_cnt = trend_counts.get("하락", 0)
        flat_cnt = trend_counts.get("보합", 0)
        st.metric("상승 / 하락 / 보합", f"🔺{up_cnt} | 🔻{down_cnt}", f"보합 {flat_cnt} 개")

    # ------------------ 메인 탭 레이아웃 (EDA 10종 구성) ------------------
    tab_overview, tab_scale, tab_volatility, tab_momentum, tab_structure = st.tabs([
        "🏠 시장 요약 & 데이터 미리보기 (KPI)",
        "💎 ETF 규모 및 거래 유동성 (시가총액/거래대금)",
        "⚡ 변동성 및 수익률 특성 (등락률/3개월/단가)",
        "🔥 모멘텀 & 테마 로테이션 (상하위 순위)",
        "🧩 자산군 구조 및 시장 효율성 (상관관계/괴리율)"
    ])

    # --- 탭 1: 시장 요약 & 데이터 미리보기 ---
    with tab_overview:
        st.subheader("📋 실시간 데이터 미리보기 (상/하위 5개 종목)")
        
        # 1단계: 데이터 탐색적 미리보기 (Head & Tail)
        col_head, col_tail = st.columns(2)
        with col_head:
            st.markdown("**[Head] 시가총액 상위 5개 종목**")
            st.dataframe(filtered_df.head(5)[["itemcode", "itemname", "assetClass", "nowVal", "marketSum", "changeRate"]])
        with col_tail:
            st.markdown("**[Tail] 시가총액 하위 5개 종목**")
            st.dataframe(filtered_df.tail(5)[["itemcode", "itemname", "assetClass", "nowVal", "marketSum", "changeRate"]])
            
        st.markdown("---")
        st.subheader("🔍 전체 필터링 데이터 테이블")
        st.dataframe(filtered_df[[
            "itemcode", "itemname", "assetClass", "nowVal", "changeVal", 
            "changeRate", "nav", "disparityRate", "threeMonthEarnRate", 
            "quant", "amonut", "marketSum", "trend"
        ]].rename(columns={
            "itemcode": "종목코드", "itemname": "종목명", "assetClass": "자산분류",
            "nowVal": "현재가(원)", "changeVal": "대비(원)", "changeRate": "등락률(%)",
            "nav": "NAV(원)", "disparityRate": "괴리율(%)", "threeMonthEarnRate": "3개월수익률(%)",
            "quant": "거래량", "amonut": "거래대금(백만)", "marketSum": "시가총액(억)",
            "trend": "등락구분"
        }))

    # --- 탭 2: ETF 규모 및 거래 유동성 ---
    with tab_scale:
        col_c1, col_c2 = st.columns(2)
        
        with col_c1:
            st.subheader("1. 시가총액 TOP 20 종목 분석")
            top20_market = filtered_df.nlargest(20, "marketSum")
            fig1 = px.bar(
                top20_market,
                x="marketSum",
                y="itemname",
                orientation='h',
                color="marketSum",
                color_continuous_scale="Blues",
                labels={"marketSum": "시가총액 (억 원)", "itemname": "종목명"},
                title="시가총액 상위 20개 ETF"
            )
            fig1.update_layout(yaxis={'categoryorder':'total ascending'}, height=500)
            st.plotly_chart(fig1, use_container_width=True)
            
            # 병행 데이터 표
            st.markdown("**[표 1] 시가총액 상위 20개 종목 주요 지표**")
            st.dataframe(top20_market[["itemname", "marketSum", "nowVal", "threeMonthEarnRate"]].rename(
                columns={"itemname":"종목명", "marketSum":"시가총액(억)", "nowVal":"현재가", "threeMonthEarnRate":"3개월수익률(%)"}
            ))
            
            # 300자 이상 심층 인사이트
            st.info("""
            **💡 분석 및 비즈니스 인사이트 (20년차 분석가 제언)**  
            한국 ETF 시장의 시가총액 집중도는 매우 높은 편이며, 주로 코스피 200이나 미국 S&P500, 나스닥100 등 대표 지수를 추종하는 패시브 상품들이 상위권을 독점하고 있습니다. 이는 개인 투자자들의 장기 연금 계좌를 통한 적립식 투자와 기관 투자자들의 자산 배분 전략이 이들 핵심 지수에 집중되고 있음을 반영합니다. 이러한 대형 지수 중심의 성장은 시장의 전반적인 유동성을 보강하지만, 한편으로는 특정 초대형 종목들의 주가 등락이 지수 전체와 ETF 시장 판세를 과도하게 좌우하는 왜곡 현상을 낳을 수도 있습니다. 투자자 입장에서는 대형 패시브 자금의 유입에 따른 대형주 프리미엄 현상을 인지하고, 지수 내 비중 변화에 따른 리밸런싱 수요를 파악하여 투자 기회로 활용할 필요가 있습니다.
            """)
            
        with col_c2:
            st.subheader("2. 거래대금 TOP 20 종목 분석")
            top20_amount = filtered_df.nlargest(20, "amonut")
            fig2 = px.bar(
                top20_amount,
                x="amonut",
                y="itemname",
                orientation='h',
                color="amonut",
                color_continuous_scale="Reds",
                labels={"amonut": "거래대금 (백만 원)", "itemname": "종목명"},
                title="거래대금 상위 20개 ETF"
            )
            fig2.update_layout(yaxis={'categoryorder':'total ascending'}, height=500)
            st.plotly_chart(fig2, use_container_width=True)
            
            # 병행 데이터 표
            st.markdown("**[표 2] 거래대금 상위 20개 종목 주요 지표**")
            st.dataframe(top20_amount[["itemname", "amonut", "changeRate", "quant"]].rename(
                columns={"itemname":"종목명", "amonut":"거래대금(백만)", "changeRate":"등락률(%)", "quant":"거래량"}
            ))
            
            # 300자 이상 심층 인사이트
            st.info("""
            **💡 분석 및 비즈니스 인사이트 (20년차 분석가 제언)**  
            거래대금 상위 종목은 당일 시장에서 가장 유동성이 풍부하며 투자자들의 관심이 극도로 쏠려 있는 섹터가 무엇인지를 실시간으로 보여줍니다. 보통 레버리지 및 인버스 파생 상품이나 시장의 가장 뜨거운 단기 테마형 ETF(예: AI 반도체, 바이오, 2차전지 등)가 높은 순위를 차지합니다. 거래대금의 급증은 시장의 단기 투기적 자금 흐름과 강한 모멘텀을 시사하며, 개인 투자자들의 적극적인 참여와 기관 및 외국인의 단기 포트폴리오 헤징 활동이 결합된 결과입니다. 하지만 이러한 유동성 쏠림은 테마의 과열을 경고하는 신호일 수도 있으므로, 거래대금이 이례적으로 폭발한 이후 거래량이 급감하며 발생하는 가격 조정 리스크에 항상 유의해야 합니다.
            """)

    # --- 탭 3: 변동성 및 수익률 특성 ---
    with tab_volatility:
        col_v1, col_v2 = st.columns(2)
        
        with col_v1:
            st.subheader("3. 당일 등락률 분포 분석")
            fig3 = px.histogram(
                filtered_df,
                x="changeRate",
                marginal="box",
                nbins=30,
                color_discrete_sequence=["#3b82f6"],
                labels={"changeRate": "등락률 (%)"},
                title="전체 ETF 등락률 분포 및 이상치 현황"
            )
            st.plotly_chart(fig3, use_container_width=True)
            
            # 병행 데이터 표
            st.markdown("**[표 3] 당일 등락률 요약 통계**")
            st.dataframe(filtered_df["changeRate"].describe().to_frame().T)
            
            # 300자 이상 심층 인사이트
            st.info("""
            **💡 분석 및 비즈니스 인사이트 (20년차 분석가 제언)**  
            오늘 하루 동안 거래된 전체 ETF의 등락률 분포는 현재 시장의 전반적인 센티먼트와 온도를 즉각적으로 진단하는 지표입니다. 분포의 대칭성(왜도)을 분석하여 상승 종목이 지배적인 불장(Bull market)인지, 혹은 하락 종목이 우세한 약세장(Bear market)인지를 시각적으로 파악할 수 있습니다. 박스플롯 상에서 발견되는 이상치(Outlier)들은 시장 평균 수준을 벗어나 오늘 하루 극단적인 급등이나 급락을 기록한 특정 테마 ETF들을 나타내며, 이는 개별 업종의 강한 호재나 악재를 매크로 흐름과 독립적으로 보여줍니다. 투자자는 전체 분포의 중앙값 대비 이상치들의 거리를 관찰하여 현재 시장의 변동성이 특정 섹터에 국한된 것인지, 아니면 시장 전체의 체계적 리스크로 확산되는 중인지 평가할 수 있습니다.
            """)
            
            st.markdown("---")
            st.subheader("5. 거래량(Quant) 대비 거래대금(Amount) 분석")
            fig5 = px.scatter(
                filtered_df,
                x="quant",
                y="amonut",
                color="assetClass",
                hover_data=["itemname", "nowVal"],
                labels={"quant": "거래량 (주)", "amonut": "거래대금 (백만 원)"},
                title="거래량 vs 거래대금 산점도"
            )
            st.plotly_chart(fig5, use_container_width=True)
            
            # 병행 데이터 표
            st.markdown("**[표 5] 자산군별 평균 거래량 및 거래대금**")
            st.dataframe(filtered_df.groupby("assetClass")[["quant", "amonut"]].mean().reset_index())
            
            # 300자 이상 심층 인사이트
            st.info("""
            **💡 분석 및 비즈니스 인사이트 (20년차 분석가 제언)**  
            거래량과 거래대금의 비율을 나타내는 이 분석은 개별 ETF의 1주당 평균 단가(Unit Price) 구조가 시장의 거래 활성도에 미치는 영향을 파악하는 데 유용합니다. 주당 가격이 높은 고단가 ETF(예: 10만 원 이상)는 거래량 자체는 적어 보일지라도 실제 유입된 자금 규모(거래대금)는 매우 클 수 있으며, 이는 호가 스프레드가 촘촘하게 관리되어 거래 비용 측면에서 매우 유리함을 시사합니다. 반면, 주당 가격이 매우 낮은 동전주 형태의 ETF는 거래량은 엄청나지만 실질 거래대금은 미미하여 호가 왜곡이 발생하기 쉽고 투기적 거래에 노출될 위험이 있습니다. 따라서 분석가는 겉보기 거래량에 현혹되지 않고 실질 거래대금과 단가 구조를 연계하여 종합적인 유동성을 평가해야 합니다.
            """)
            
        with col_v2:
            st.subheader("4. 3개월 수익률 분포 분석")
            fig4 = px.histogram(
                filtered_df,
                x="threeMonthEarnRate",
                marginal="box",
                nbins=30,
                color_discrete_sequence=["#10b981"],
                labels={"threeMonthEarnRate": "3개월 수익률 (%)"},
                title="전체 ETF 3개월 수익률 분포"
            )
            st.plotly_chart(fig4, use_container_width=True)
            
            # 병행 데이터 표
            st.markdown("**[표 4] 3개월 수익률 요약 통계**")
            st.dataframe(filtered_df["threeMonthEarnRate"].describe().to_frame().T)
            
            # 300자 이상 심층 인사이트
            st.info("""
            **💡 분석 및 비즈니스 인사이트 (20년차 분석가 제언)**  
            3개월 누적 수익률 분포는 단기 소음(Noise)을 걷어내고 중기적인 시장의 추세와 건강 상태를 평가하는 데 매우 유용한 지표입니다. 3개월 분포가 양의 방향으로 길게 꼬리를 늘어뜨리고 있다면 최근 분기 동안 전반적인 상승 랠리가 지속되며 강한 추종 자금이 시장을 이끌었음을 의미하며, 반대로 음의 영역에 쏠려 있다면 전반적인 시장 조정 혹은 하락 압력이 누적되었음을 시사합니다. 중기 자산 배분 관점에서 이 분포의 중앙값과 사분위수 범위를 모니터링하면 현재 시장이 과매수 영역에 도달했는지 혹은 낙폭 과대로 인한 저가 매수 진입 시점인지를 가늠할 수 있어, 포트폴리오의 주식 비중을 조절하는 전략적 의사결정에 기여할 수 있습니다.
            """)

    # --- 탭 4: 모멘텀 & 테마 로테이션 ---
    with tab_momentum:
        col_m1, col_m2 = st.columns(2)
        
        with col_m1:
            st.subheader("6. 당일 등락률 TOP 10 (상승 vs 하락)")
            top10_up = filtered_df.nlargest(10, "changeRate")
            top10_down = filtered_df.nsmallest(10, "changeRate")
            combined_momentum = pd.concat([top10_up, top10_down])
            
            fig6 = px.bar(
                combined_momentum,
                x="changeRate",
                y="itemname",
                orientation='h',
                color="changeRate",
                color_continuous_scale="RdBu_r",
                labels={"changeRate": "등락률 (%)", "itemname": "종목명"},
                title="상위 10개(상승) vs 하위 10개(하락) ETF"
            )
            fig6.update_layout(yaxis={'categoryorder':'total ascending'}, height=500)
            st.plotly_chart(fig6, use_container_width=True)
            
            # 병행 데이터 표
            st.markdown("**[표 6] 극단 모멘텀 종목 지표**")
            st.dataframe(combined_momentum[["itemname", "changeRate", "nowVal", "amonut"]].rename(
                columns={"itemname":"종목명", "changeRate":"등락률(%)", "nowVal":"현재가", "amonut":"거래대금(백만)"}
            ))
            
            # 300자 이상 심층 인사이트
            st.info("""
            **💡 분석 및 비즈니스 인사이트 (20년차 분석가 제언)**  
            오늘 하루 동안 가장 극단적인 모멘텀을 보인 상하위 10개 종목의 대비는 시장의 주도 테마와 소외 테마 간의 자금 이동과 순환매 패턴을 극명하게 보여줍니다. 급등 1위 그룹의 주도 섹터(예: 특정 반도체나 원자재)와 급락 1위 그룹의 섹터 간 상반된 움직임은 매크로 환경(금리 변동, 환율 변동, 지정학적 리스크 등)이 개별 산업에 어떻게 차별적으로 작용하고 있는지 분석하는 단초가 됩니다. 특히 등락률 상위권에 레버리지/인버스 파생 ETF가 대거 포진해 있다면 방향성 베팅이 심화된 변동성 국면임을 뜻하며, 특정 테마의 독주는 시장 자금의 쏠림이 임계점에 도달해 단기 기술적 반등이나 차익 실현 매물이 출현할 타이밍임을 암시할 수 있습니다.
            """)
            
        with col_m2:
            st.subheader("7. 3개월 수익률 TOP 10 종목")
            top10_earn = filtered_df.nlargest(10, "threeMonthEarnRate")
            fig7 = px.bar(
                top10_earn,
                x="threeMonthEarnRate",
                y="itemname",
                orientation='h',
                color="threeMonthEarnRate",
                color_continuous_scale="Viridis",
                labels={"threeMonthEarnRate": "3개월 수익률 (%)", "itemname": "종목명"},
                title="3개월 중기 수익률 상위 10개 ETF"
            )
            fig7.update_layout(yaxis={'categoryorder':'total ascending'}, height=500)
            st.plotly_chart(fig7, use_container_width=True)
            
            # 병행 데이터 표
            st.markdown("**[표 7] 중기 수익률 우수 종목 지표**")
            st.dataframe(top10_earn[["itemname", "threeMonthEarnRate", "marketSum", "nowVal"]].rename(
                columns={"itemname":"종목명", "threeMonthEarnRate":"3개월수익률(%)", "marketSum":"시가총액(억)", "nowVal":"현재가"}
            ))
            
            # 300자 이상 심층 인사이트
            st.info("""
            **💡 분석 및 비즈니스 인사이트 (20년차 분석가 제언)**  
            최근 3개월 누적 수익률 상위 10개 종목은 단순한 당일 변동성을 넘어 중기적으로 시장을 지배하고 있는 진정한 '메가 트렌드'를 식별하는 지표입니다. 이 영역에 지속적으로 이름을 올리는 ETF들은 기초자산의 펀더멘털 개선이나 구조적인 산업 성장세가 뒷받침되고 있는 경우가 많습니다. 모멘텀 투자 관점에서는 이들 주도주에 올라타는 전략이 유효할 수 있으나, 단기 과열로 인해 기초자산 대비 괴리율이나 밸류에이션 부담이 과도하지 않은지 반드시 체크해야 합니다. 20년차 분석가 관점에서는 이 상위 목록의 업종 구성 변화(예: 기술주에서 가치주로의 전환 등)를 관찰함으로써 시장의 거시적 로테이션 신호를 선제적으로 포착할 수 있습니다.
            """)

    # --- 탭 5: 구조 및 효율성 ---
    with tab_structure:
        col_s1, col_s2 = st.columns(2)
        
        with col_s1:
            st.subheader("8. 시가총액 vs 거래대금 상관성 분석")
            fig8 = px.scatter(
                filtered_df,
                x="marketSum",
                y="amonut",
                color="changeRate",
                color_continuous_scale="RdBu_r",
                size=np.abs(filtered_df["changeRate"]) + 1,
                hover_data=["itemname"],
                labels={"marketSum": "시가총액 (억 원)", "amonut": "거래대금 (백만 원)"},
                title="시가총액 vs 거래대금 (버블 크기: 당일 등락률 크기)"
            )
            st.plotly_chart(fig8, use_container_width=True)
            
            # 병행 데이터 표
            corr_val = filtered_df["marketSum"].corr(filtered_df["amonut"])
            st.markdown(f"**[표 8] 상관관계 분석 지표 (피어슨 상관계수: {corr_val:.4f})**")
            st.dataframe(filtered_df[["marketSum", "amonut"]].corr())
            
            # 300자 이상 심층 인사이트
            st.info("""
            **💡 분석 및 비즈니스 인사이트 (20년차 분석가 제언)**  
            시가총액(펀드 규모)과 거래대금(실제 거래 활성도) 간의 상관관계를 보여주는 이 산점도는 두 지표 사이의 불일치(Mismatch) 현상을 파악하여 유동성 위험을 감지하는 데 필수적입니다. 시가총액은 매우 크지만 당일 거래대금이 극히 저조한 종목들은 주로 연금용 장기 채권형이나 자산 배분형 ETF로, 유동성 공급자(LP)의 매수/매도 호가가 촘촘하지 않을 경우 거래 비용이 높아질 수 있습니다. 반대로 시가총액은 작으나 거래대금이 폭발하는 종목은 단기 테마에 편승한 투기성 자금이 일시에 유입된 것으로, 모멘텀 소멸 시 급격한 가격 변동과 호가 공백이 발생할 우려가 큽니다. 투자자는 이 산점도를 통해 자신이 거래하려는 종목의 규모 대비 유동성 수준이 적절한지 검증해야 합니다.
            """)
            
            st.markdown("---")
            st.subheader("10. NAV 괴리율 분포 및 이상치 검출")
            fig10 = px.scatter(
                filtered_df,
                x="marketSum",
                y="disparityRate",
                color="assetClass",
                hover_data=["itemname"],
                labels={"marketSum": "시가총액 (억 원)", "disparityRate": "괴리율 (%)"},
                title="시가총액 규모별 NAV 괴리율 추이"
            )
            fig10.add_hline(y=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig10, use_container_width=True)
            
            # 병행 데이터 표
            st.markdown("**[표 10] 자산군별 평균 및 절대 괴리율 최댓값**")
            disparity_summary = filtered_df.groupby("assetClass")["disparityRate"].agg(["mean", "min", "max"]).reset_index()
            st.dataframe(disparity_summary.rename(columns={"mean":"평균 괴리율(%)", "min":"최소 괴리율(%)", "max":"최대 괴리율(%)"}))
            
            # 300자 이상 심층 인사이트
            st.info("""
            **💡 분석 및 비즈니스 인사이트 (20년차 분석가 제언)**  
            ETF의 현재 시장 가격과 순자산가치(NAV) 간의 차이를 나타내는 괴리율 분포는 해당 ETF의 유동성 공급자(LP)가 적절한 호가를 제공하여 시장의 효율성을 유지하고 있는지 평가하는 척도입니다. 괴리율이 플러스를 기록하면 고평가, 마이너스면 저평가 상태를 의미하며, 특히 해외 자산이나 원자재를 추종하는 ETF의 경우 시차나 기초자산 거래 정지 등으로 인해 괴리율이 빈번히 벌어집니다. 괴리율이 비정상적으로 큰 상태에서 거래하면 투자자는 즉각적인 손실(비싸게 사고 싸게 파는 비용)을 입게 되므로 주의해야 합니다. 이 지표를 주기적으로 모니터링하여 괴리율이 안정적으로 0% 부근에 수렴하는 운용 능력이 우수한 ETF를 선별하는 혜안이 필요합니다.
            """)

        with col_s2:
            st.subheader("9. 자산군별 종목 점유율 및 규모 비중")
            asset_summary = filtered_df.groupby("assetClass").agg(
                count=("itemcode", "count"),
                total_market_sum=("marketSum", "sum")
            ).reset_index()
            
            fig9 = px.pie(
                asset_summary,
                values="total_market_sum",
                names="assetClass",
                hole=0.4,
                title="자산군별 시가총액 점유율 (도넛 차트)"
            )
            st.plotly_chart(fig9, use_container_width=True)
            
            # 병행 데이터 표
            st.markdown("**[표 9] 자산군별 종목 수 및 총 시가총액**")
            st.dataframe(asset_summary.rename(columns={"assetClass":"자산군", "count":"종목수", "total_market_sum":"총시가총액(억)"}))
            
            # 300자 이상 심층 인사이트
            st.info("""
            **💡 분석 및 비즈니스 인사이트 (20년차 분석가 제언)**  
            자산군별 종목 수와 시가총액 비중을 보여주는 이 도넛 차트는 한국 ETF 시장의 구조적 성숙도와 다각화 수준을 진단하는 데 중요합니다. 주식 지수 추종 상품이 압도적인 비중을 차지하는지, 혹은 금리형 및 채권형 ETF의 비중이 늘어나고 있는지를 통해 시장 참가자들의 전반적인 위험 선호도를 읽을 수 있습니다. 최근 고금리 장기화 기조 속에서 채권 및 금리 추종 상품의 시가총액 점유율이 높아진 것은 안정적인 이자 수익(Carry)을 노리는 대기성 자금이 ETF 시장으로 대거 유입되었음을 방증합니다. 자산배분 투자를 지향하는 개인 투자자들은 다양한 자산군별 규모를 확인하여 자산별 유동성이 확보된 대표 상품을 선택하는 기준으로 삼아야 합니다.
            """)
