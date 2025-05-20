import streamlit as st
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# Google BigQuery 인증 설정
def get_bigquery_data():
    try:
        # Google Cloud 서비스 계정 키 파일 경로
        credentials = service_account.Credentials.from_service_account_file(
            'path_to_your_service_account_json.json'
        )

        client = bigquery.Client(credentials=credentials, project=credentials.project_id)

        # BigQuery 쿼리 예시: 입찰 공고 데이터
        query_bids = """
            SELECT
                bidNtceNo,
                bidNtceNm,
                ntceInsttNm,
                bsnsDivNm,
                asignBdgtAmt,
                bidNtceDate,
                bidClseDate,
                bidNtceUrl,
                bidNtceBgn,
                bidNtceSttusNm,
                dmndInsttNm,
                bidClseTm,
                bidprcPsblIndstrytyNm
            FROM `your_project_id.your_dataset_id.ai_coding_bids`
        """

        # BigQuery 쿼리 실행
        df_bids = client.query(query_bids).to_dataframe()

        # 낙찰 데이터 쿼리 예시
        query_bids_status = """
            SELECT
                bidNtceNo,
                bidNtceNm,
                dminsttNm,
                sucsfbidAmt,
                sucsfbidRate,
                fnlSucsfDate,
                bidwinnrNm
            FROM `your_project_id.your_dataset_id.ai_coding_bids_status`
        """

        # BigQuery 쿼리 실행
        df_bids_status = client.query(query_bids_status).to_dataframe()

        return df_bids, df_bids_status
    
    except Exception as e:
        st.error(f"BigQuery 연결 실패: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_live, df_completed = get_bigquery_data()  # BigQuery 데이터 로딩

# 금액 포맷팅 함수 등 기존 코드 유지
def convert_to_won_format(amount):
    try:
        if not amount or pd.isna(amount):
            return "공고 참조"
        
        amount = float(str(amount).replace(",", ""))
        if amount >= 10000000:  # 1억 이상
            amount_in_100m = amount / 100000000
            return f"{amount_in_100m:.1f}억"
        elif amount >= 10000:  # 100만원 미만
            amount_in_10k = amount / 10000
            return f"{round(amount_in_10k,1):.1f}만원"
        else:  # 1만원 미만
            return f"{amount}원"
        
    except Exception as e:
          return f"오류 발생: {str(e)}"

def format_won(amount):
    try:
        amount = int(amount.replace(",", ""))  # 쉼표 제거 후 숫자로 변환
        return f"{amount:,}원"  # 천 단위로 쉼표 추가 후 원화 표시
    except ValueError:
        return "공고 참조"

# ------------------------
# 예시 데이터 (공고 중)
# ------------------------
live_bids = df_live.to_dict(orient="records")

# ------------------------
# 예시 데이터 (입찰 완료)
# ------------------------
completed_bids = df_completed.to_dict(orient="records")

st.set_page_config(page_title="입찰 공고 서비스", layout="wide")
st.title("📝 실시간 입찰 공고 및 낙찰 결과")

tab1, tab2 = st.tabs(["📢 실시간 입찰 공고", "📑 입찰 결과"])
page = st.session_state.get("page", "home")

st_autorefresh(interval=60*1000, key='refresh')

# ------------------------
# 📢 실시간 입찰 공고 탭
# ------------------------
if page == 'home':
    with tab1:
        st.subheader("📢 현재 진행 중인 입찰 목록")

        df_live = pd.DataFrame(live_bids)
        df_live = df_live[[ "bidNtceNo", "bidNtceNm", "ntceInsttNm", "bsnsDivNm","asignBdgtAmt", "bidNtceDate", "bidClseDate",
                            "bidClseTm",'bidNtceUrl',"bidNtceBgn","bidNtceSttusNm","dmndInsttNm", "bidprcPsblIndstrytyNm"]]
        df_live.columns = ["공고번호", "공고명", "공고기관", "분류","금액", "게시일", "마감일","마감시간",'url', "게시시간","입찰공고상태명",
                           "수요기관", "투찰가능업종명"]

        # 👉 날짜 형식 변환
        df_live["마감일"] = pd.to_datetime(df_live["마감일"])
        df_live["게시일"] = pd.to_datetime(df_live["게시일"])

        # 날짜순으로 정렬
        df_live = df_live.sort_values(by=['게시일','게시시간'], ascending=False)

        # 🔍 필터 UI
        search_keyword = st.text_input("🔎 공고명 또는 공고기관 검색")

        unique_categories = [cat for cat in df_live["분류"].unique().tolist() if cat]
        selected_cls = st.multiselect("📁 분류 선택", options=unique_categories, default=unique_categories)

        col2, col3, col4 = st.columns(3)        
            
        with col2:
            start_date = st.date_input("📅 게시일 기준 시작일", value=df_live["게시일"].min().date())
        with col3:
            end_date = st.date_input("📅 게시일 기준 종료일", value=df_live["게시일"].max().date())
        with col4:
            sort_col = st.selectbox("정렬기준", options=["게시일","마감일","금액"])
            sort_order = st.radio("", options=["오름차순", "내림차순"], horizontal=True)
            
        # 🔎 필터링 적용
        filtered = df_live.copy()

        # 1. 분류 필터
        if selected_cls:
            filtered = df_live[df_live["분류"].isin(selected_cls)]
        else:
            filtered = df_live.copy()

        # 2. 검색어 필터
        if search_keyword:
            filtered = filtered[
                filtered["공고명"].str.contains(search_keyword, case=False, na=False, regex=False) |
                filtered["공고기관"].str.contains(search_keyword, case=False, na=False, regex=False)
            ]

        # 3. 게시일 범위 필터
        filtered = filtered[
            (filtered["게시일"].dt.date >= start_date) & 
            (filtered["게시일"].dt.date <= end_date)
        ]

        # 5. 정렬 순서 수정
        ascending = False if sort_order == "오름차순" else True

        # 6. 정렬 적용
        if sort_col == "게시일":
            filtered = filtered.sort_values(by=[sort_col, "게시시간"], ascending=ascending)
        else:
            filtered = filtered.sort_values(by=sort_col, ascending=ascending)

        # 결과 출력
        st.markdown(f"<div style='text-align: left; margin-bottom: 10px;'>검색 결과 {len(filtered)}건</div>", unsafe_allow_html=True)
      
        # 1. 페이지 크기 설정
        PAGE_SIZE = 10

        # 2. 데이터 분할 함수
        def paginate_dataframe(df, page_num, page_size):
            start_index = page_num * page_size
            end_index = (page_num + 1) * page_size
            return df.iloc[start_index:end_index]

        # 3. 현재 페이지 번호 초기화
        if "current_page" not in st.session_state:
            st.session_state["current_page"] = 0

        # 4. 데이터 필터링 및 페이지 분할
        total_pages = (len(filtered) + PAGE_SIZE - 1) // PAGE_SIZE
        paginated_df = paginate_dataframe(filtered, st.session_state["current_page"], PAGE_SIZE)
        st.write("")

        # 결과 렌더링
        header_cols = st.columns([2, 2, 4, 3, 1, 1, 1, 1, 1])
        headers = ['공고번호', "구분", '공고명', '공고기관', '분류', '금액', '게시일', '마감일', '상세정보']
        for col, head in zip(header_cols, headers):
            col.markdown(f"**{head}**")

        # 행 렌더링
        for i, row in paginated_df.iterrows():
            cols = st.columns([2, 2, 4, 3, 1, 1, 1, 1, 1])
            cols[0].write(row["공고번호"])
            cols[1].write(row["입찰공고상태명"])
            bid_title_link = f"[{row['공고명']}]({row['url']})"
            cols[2].markdown(bid_title_link)
            cols[3].write(row["공고기관"])
            cols[4].write(row["분류"])
            cols[5].write(convert_to_won_format(row["금액"]))
            cols[6].write(row["게시일"].strftime("%Y-%m-%d"))
            if pd.isna(row["마감일"]):
                cols[7].write("공고 참조")
            else:
                cols[7].write(row["마감일"].strftime("%Y-%m-%d"))
            if cols[8].button("보기", key=f"live_detail_{i}"):
                st.session_state["page"] = "detail"
                st.session_state["selected_live_bid"] = row.to_dict()
                st.rerun()
