"""네이버 금융 ETF API로부터 데이터를 수집하고 전처리하여 JSON 파일로 저장하는 데이터 파이프라인 모듈.

이 모듈은 네이버 금융 실시간 ETF API를 호출하여 데이터를 다운로드하고,
정해진 전처리 규칙(자산군 매핑, 수치 변환, NAV 괴리율 계산 등)을 거친 후,
정적 웹 대시보드가 로드할 수 있도록 JSON 파일로 내보냅니다.
"""

import datetime
import json
import os
import numpy as np
import pandas as pd
import requests


def fetch_etf_data() -> pd.DataFrame:
    """네이버 금융 실시간 API를 통해 ETF 원본 데이터를 수집합니다.

    이 함수는 HTTP GET 요청을 전송하여 네이버 ETF 목록 데이터를 획득하고,
    Pandas DataFrame 형식으로 변환하여 반환합니다.

    Returns:
        pd.DataFrame: 수집된 원본 ETF 데이터프레임.
            수집 중 오류가 발생하거나 실패하면 빈 데이터프레임을 반환합니다.

    Raises:
        requests.RequestException: 네트워크 통신 관련 에러가 발생할 때 유발될 수 있습니다.
    """
    url = "https://finance.naver.com/api/sise/etfItemList.nhn?etfType=0&targetColumn=market_sum&sortOrder=desc"
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("resultCode") == "success":
                item_list = data["result"]["etfItemList"]
                return pd.DataFrame(item_list)
            else:
                print(f"API 응답 실패 코드: {data.get('resultCode')}")
        else:
            print(f"HTTP 요청 실패 상태 코드: {response.status_code}")
    except Exception as e:
        print(f"데이터 수집 실패: {e}")
    return pd.DataFrame()


def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    """수집된 ETF 데이터의 전처리 및 파생 변수를 생성합니다.

    데이터 타입 정합성 확보(수치형 형변환), 자산분류 한글 매핑,
    등락 트렌드 매핑, NAV 괴리율 산출 등의 작업을 수행합니다.

    Args:
        df (pd.DataFrame): API로부터 가져온 가공되지 않은 원본 ETF 데이터프레임.

    Returns:
        pd.DataFrame: 타입 정합성이 보장되고 파생 변수 생성이 완료된 데이터프레임.
    """
    if df.empty:
        return df

    # 원본 훼손 방지를 위한 복사본 생성
    df = df.copy()

    # 탭 코드 한글 이름 매핑 (네이버 분류 기준)
    tab_mapping = {
        1: "국내 시장지수",
        2: "국내 업종/테마",
        3: "국내 파생(레버리지/인버스)",
        4: "해외 주식",
        5: "원자재/대체자산",
        6: "채권/금리",
    }
    df["assetClass"] = df["etfTabCode"].map(tab_mapping).fillna("기타/해외지수")

    # 각 변수별 적합한 데이터 타입(수치형)으로 명시적 변환
    df["nowVal"] = pd.to_numeric(df["nowVal"], errors="coerce")
    df["changeVal"] = pd.to_numeric(df["changeVal"], errors="coerce")
    df["changeRate"] = pd.to_numeric(df["changeRate"], errors="coerce")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df["threeMonthEarnRate"] = pd.to_numeric(df["threeMonthEarnRate"], errors="coerce")
    df["quant"] = pd.to_numeric(df["quant"], errors="coerce")
    df["amonut"] = pd.to_numeric(df["amonut"], errors="coerce")  # 거래대금 (백만 원 단위, API 스펙의 오타 반영)
    df["marketSum"] = pd.to_numeric(df["marketSum"], errors="coerce")  # 시가총액 (억 원 단위)

    # NAV 괴리율 계산: ((현재가 - NAV) / NAV) * 100
    # 분모(NAV)가 0인 경우에 대한 안정적 예외처리를 내부적으로 제공
    df["disparityRate"] = np.where(
        df["nav"] > 0,
        ((df["nowVal"] - df["nav"]) / df["nav"]) * 100,
        0.0
    )

    # risefall (등락구분) 한글화 및 기호 추가 (2: 상승, 5: 하락, 3: 보합)
    def map_risefall(row: pd.Series) -> str:
        """등락 유형(risefall)을 직관적인 한글 레이블로 매핑합니다.

        Args:
            row (pd.Series): 데이터프레임의 단일 행 시리즈.

        Returns:
            str: '상승', '하락', '보합' 중 하나.
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
    df["threeMonthEarnRate"] = df["threeMonthEarnRate"].fillna(0.0)
    df["disparityRate"] = df["disparityRate"].fillna(0.0)

    # JSON 호환되지 않는 값들(NaN 등)을 0이나 None으로 변환
    df = df.replace({np.nan: None})

    return df


def save_to_json(df: pd.DataFrame, output_path: str) -> None:
    """전처리된 ETF 데이터를 최종 JSON 파일로 저장합니다.

    저장 포맷은 생성 시각 정보가 포함된 구조화된 JSON 객체입니다.

    Args:
        df (pd.DataFrame): 전처리가 완료된 ETF 데이터프레임.
        output_path (str): 저장할 대상 JSON 파일의 경로.
    """
    # 디렉토리 자동 생성
    dir_name = os.path.dirname(output_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    # 현재 로컬 시간을 갱신 시간으로 지정
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # DataFrame을 Dictionary 리스트로 변환 (한글 보존을 위해 직접 처리)
    etf_list = df.to_dict(orient="records")

    payload = {
        "updated_at": current_time,
        "etf_items": etf_list
    }

    # 파일 쓰기
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"데이터 갱신 완료: {output_path} ({current_time})")


def main() -> None:
    """데이터 수집, 전처리 및 저장을 순차적으로 수행하는 진입점 함수."""
    print("실시간 ETF 데이터 수집을 시작합니다...")
    raw_df = fetch_etf_data()
    if raw_df.empty:
        print("데이터를 수집하지 못했습니다. 수집 파이프라인을 종료합니다.")
        return

    processed_df = preprocess_data(raw_df)
    
    # 상대경로 기준 데이터 파일 저장
    target_file = os.path.join("data", "etf_data.json")
    save_to_json(processed_df, target_file)


if __name__ == "__main__":
    main()
