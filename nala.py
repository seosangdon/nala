import streamlit as st  # streamlit 모듈 임포트 추가
import pandas as pd
from pymongo import MongoClient
from streamlit_autorefresh import st_autorefresh


__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

# 실시간 입찰 공고 탭
st.set_page_config(page_title="입찰 공고 서비스", layout="wide")


@st.cache_resource(show_spinner=False)
def get_mongo_data():
    try:
        # ① secrets.toml에서 불러오기
        uri     = st.secrets["mongodb"]["uri"]
        db_name = st.secrets["mongodb"]["database"]

        # ② Atlas에 TLS 인증서 검증 포함하여 연결
        client = MongoClient(
            uri,
            tls=True,
            tlsCAFile=certifi.where()
        )
        db = client[db_name]

        coll_bids      = db["ai_coding_bids"]
        coll_bids_stat = db["ai_coding_bids_status"]

        # 필요한 필드만 projection
        proj_live = {
            "bidNtceNo": 1, "bidNtceNm": 1, "ntceInsttNm": 1,
            "bsnsDivNm": 1, "asignBdgtAmt": 1, "bidNtceDate": 1,
            "bidClseDate": 1, "bidClseTm": 1, "bidNtceUrl": 1,
            "bidNtceBgn": 1, "bidNtceSttusNm": 1,
            "dmndInsttNm": 1, "bidprcPsblIndstrytyNm": 1
        }

        live_data      = list(coll_bids.find({}, proj_live))
        completed_data = list(coll_bids_stat.find({}))

        return pd.DataFrame(live_data), pd.DataFrame(completed_data)

    except Exception as e:
        st.error(f"MongoDB Atlas 연결 실패: {e}")
        return pd.DataFrame(), pd.DataFrame()

        # 낙찰 데이터 로딩 (모든 필드 가져오기)
        projection_bids_status = {}  # 빈 딕셔너리로 설정하여 모든 필드 선택
        completed_data = list(collection_bids_status.find({}, projection_bids_status))
        df_completed = pd.DataFrame(completed_data)

        return df_live, df_completed
    
    except Exception as e:
        st.error(f"MongoDB Atlas 연결 실패: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_live, df_completed = get_mongo_data()  # MongoDB 데이터 로딩

# 금액 억단위로 포맷팅 함수
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
            return f"{round(amount_in_10k, 1):.1f}만원"
        else:  # 1만원 미만
            return f"{amount}원"
        
    except Exception as e:
        return f"오류 발생: {str(e)}"

# 상세 페이지 금액을 원화로 포맷팅
def format_won(amount):
    try:
        # 쉼표를 포함한 문자열을 숫자로 변환 후, 다시 천 단위로 쉼표 추가
        amount = int(amount.replace(",", ""))  # 쉼표 제거 후 숫자로 변환
        return f"{amount:,}원"  # 천 단위로 쉼표 추가 후 원화 표시
    except (ValueError, AttributeError):
        return "공고 참조"


st.title("📝 실시간 입찰 공고 및 낙찰 결과")

tab1, tab2 = st.tabs(["📢 실시간 입찰 공고", "📑 입찰 결과"])

# 60초마다 자동 새로 고침
st_autorefresh(interval=60 * 1000, key="refresh")

# ------------------------
# 📢 실시간 입찰 공고 탭
# ------------------------
with tab1:
    st.subheader("📢 현재 진행 중인 입찰 목록")

    if df_live.empty:
        st.warning("데이터를 불러올 수 없습니다.")
    else:
        df_live = df_live[[
            "bidNtceNo", "bidNtceNm", "ntceInsttNm", 
            "bsnsDivNm", "asignBdgtAmt", "bidNtceDate", 
            "bidClseDate", "bidClseTm", "bidNtceUrl", 
            "bidNtceBgn", "bidNtceSttusNm", "dmndInsttNm", 
            "bidprcPsblIndstrytyNm"
        ]]
        df_live.columns = ["공고번호", "공고명", "공고기관", 
                           "분류", "금액", "게시일", "마감일", 
                           "마감시간", 'url', "게시시간", "입찰공고상태명", 
                           "수요기관", "투찰가능업종명"]

        # 날짜 형식 변환
        df_live["마감일"] = pd.to_datetime(df_live["마감일"])
        df_live["게시일"] = pd.to_datetime(df_live["게시일"])

        # 날짜순으로 정렬
        df_live = df_live.sort_values(by=["게시일", "게시시간"], ascending=False)

        # 필터 UI
        search_keyword = st.text_input("🔎 공고명 또는 공고기관 검색")

        unique_categories = [cat for cat in df_live["분류"].unique().tolist() if cat]

        selected_cls = st.multiselect("📁 분류 선택", 
                                      options=unique_categories, 
                                      default=unique_categories)

        col2, col3, col4 = st.columns(3)        
        with col2:
            start_date = st.date_input("📅 게시일 기준 시작일", value=df_live["게시일"].min().date())
        with col3:
            end_date = st.date_input("📅 게시일 기준 종료일", value=df_live["게시일"].max().date())
        with col4:
            sort_col = st.selectbox("정렬기준", options=["게시일", "마감일", "금액"])
            sort_order = st.radio("", options=["오름차순", "내림차순"], horizontal=True)

        # 필터링 적용
        filtered = df_live.copy()

        # 분류 필터
        if selected_cls:
            filtered = filtered[filtered["분류"].isin(selected_cls)]

        # 검색어 필터
        if search_keyword:
            filtered = filtered[filtered["공고명"].str.contains(search_keyword, case=False, na=False) | 
                                filtered["공고기관"].str.contains(search_keyword, case=False, na=False)]

        # 게시일 범위 필터
        filtered = filtered[
            (filtered["게시일"].dt.date >= start_date) & 
            (filtered["게시일"].dt.date <= end_date)
        ]

        # 정렬 적용
        ascending = False if sort_order == "오름차순" else True
        filtered = filtered.sort_values(by=sort_col, ascending=ascending)

        # 결과 출력
        st.markdown(f"<div style='text-align: left; margin-bottom: 10px;'>검색 결과 {len(filtered)}건</div>", unsafe_allow_html=True)

        # 페이지 크기 설정
        PAGE_SIZE = 10

        # 데이터 분할 함수
        def paginate_dataframe(df, page_num, page_size):
            start_index = page_num * page_size
            end_index = (page_num + 1) * page_size
            return df.iloc[start_index:end_index]

        # 현재 페이지 번호 초기화
        if "current_page" not in st.session_state:
            st.session_state["current_page"] = 0

        # 데이터 필터링 및 페이지 분할
        total_pages = (len(filtered) + PAGE_SIZE - 1) // PAGE_SIZE
        paginated_df = paginate_dataframe(filtered, st.session_state["current_page"], PAGE_SIZE)
        st.write("")

        # 테이블 헤더
        header_cols = st.columns([2, 2, 4, 3, 1, 1, 1, 1, 1])
        headers = ['공고번호', "구분", '공고명', '공고기관', '분류', '금액', '게시일', '마감일', '상세정보']

        for col, head in zip(header_cols, headers):
            col.markdown(f"**{head}**")

        st.markdown("<hr style='margin-top: 5px; margin-bottom: 10px;'>", unsafe_allow_html=True)

        # 행 렌더링 + 버튼
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

            st.markdown("<hr style='margin-top: 5px; margin-bottom: 10px;'>", unsafe_allow_html=True)

        # "이전" 및 "다음" 버튼
        cols_pagination = st.columns([1, 3, 1])
        with cols_pagination[0]:
            if st.session_state["current_page"] > 0:
                if st.button("이전"):
                    st.session_state["current_page"] -= 1
                    st.rerun()

        with cols_pagination[2]:
            if st.session_state['current_page'] < total_pages - 1:
                if st.button("다음"):
                    st.session_state["current_page"] += 1
                    st.rerun()

        # 페이지 번호 표시    
        st.markdown(f"<div style='text-align: center;'> {st.session_state['current_page'] + 1}</div>", unsafe_allow_html=True)
