import streamlit as st
import pandas as pd
from pymongo import MongoClient
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# MongoDB 연결
def get_mongo_data():
    try:
        client = MongoClient('mongodb://192.168.56.108:27017/')
        db = client['local']  # 데이터베이스 이름

        # 두 개의 컬렉션 설정
        collection_bids = db['ai_coding_bids']  # 공고 관련 컬렉션
        collection_bids_status = db['ai_coding_bids_status']  # 낙찰 관련 컬렉션

        # 필요한 필드만 선택하여 최적화된 데이터 로딩
        projection_bids = {
            "bidNtceNo": 1,
            "bidNtceNm": 1,
            "ntceInsttNm": 1,
            "bsnsDivNm": 1,
            "asignBdgtAmt": 1,
            "bidNtceDate": 1,
            "bidClseDate": 1,
            "bidNtceUrl": 1,
            "bidNtceBgn": 1,
            "bidNtceSttusNm": 1,
            "dmndInsttNm": 1,
            "bidClseTm":1,
            "bidprcPsblIndstrytyNm":1
        }
        live_data = list(collection_bids.find({}, projection_bids))
        df_live = pd.DataFrame(live_data)

        # 낙찰 데이터 로딩 (모든 필드 가져오기)
        projection_bids_status = {}  # 빈 딕셔너리로 설정하여 모든 필드 선택
        completed_data = list(collection_bids_status.find({}, projection_bids_status))
        df_completed = pd.DataFrame(completed_data)

        return df_live, df_completed
    
    except Exception as e:
        st.error(f"MongoDB 연결 실패: {e}")
        return pd.DataFrame()

df_live, df_completed  = get_mongo_data()  # MongoDB 데이터 로딩

# 메인 페이지 금액 억단위
def convert_to_won_format(amount):
    try:
        if not amount or pd.isna(amount):
            return "공고 참조"
        
        amount = float(str(amount).replace(",", ""))

        if amount >= 10000000: # 1억 이상
            amount_in_100m = amount / 100000000
            return f"{amount_in_100m:.1f}억"
        elif amount >= 10000:# 100만원 미만
            amount_in_10k = amount / 10000
            return f"{round(amount_in_10k,1):.1f}만원"
        else: # 1만원 미만
            return f"{amount}원"
        
    except Exception as e:
          return f"오류 발생: {str(e)}"

# 상세페이지 금액을 원화로 포맷팅
def format_won(amount):
    try:
        # 쉼표를 포함한 문자열을 숫자로 변환 후, 다시 천 단위로 쉼표 추가
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
# 쿼리 파라미터로 현재 페이지 구분
page = st.session_state.get("page", "home")

st_autorefresh(interval=60*1000, key='refresh')
# ------------------------
# 📢 실시간 입찰 공고 탭
# ------------------------
if page == 'home':
    with tab1:
        st.subheader("📢 현재 진행 중인 입찰 목록")

        df_live = pd.DataFrame(live_bids)
        df_live = df_live[[
            "bidNtceNo", "bidNtceNm", "ntceInsttNm", 
            "bsnsDivNm","asignBdgtAmt", "bidNtceDate", "bidClseDate",
            "bidClseTm",'bidNtceUrl',"bidNtceBgn","bidNtceSttusNm",
            "dmndInsttNm", "bidprcPsblIndstrytyNm"]]
        df_live.columns = ["공고번호", "공고명", "공고기관", 
                           "분류","금액", "게시일", "마감일",
                           "마감시간",'url', "게시시간","입찰공고상태명",
                           "수요기관", "투찰가능업종명"]


    

        # 👉 날짜 형식 변환
        df_live["마감일"] = pd.to_datetime(df_live["마감일"])
        df_live["게시일"] = pd.to_datetime(df_live["게시일"])

        # 날짜순으로 정렬
        df_live = df_live.sort_values(by=['게시일','게시시간'], ascending=False)

        # 🔍 필터 UI
        search_keyword = st.text_input("🔎 공고명 또는 공고기관 검색")

        unique_categories = [ cat for cat in df_live["분류"].unique().tolist() if cat]

        selected_cls = st.multiselect("📁 분류 선택", 
                                    options= unique_categories, 
                                    default =unique_categories)

        col2, col3, col4 = st.columns(3)        
            
        with col2:
            start_date = st.date_input("📅 게시일 기준 시작일", value=df_live["게시일"].min().date())
        with col3:
            end_date = st.date_input("📅 게시일 기준 종료일", value=df_live["게시일"].max().date())
        with col4:
            sort_col = st.selectbox("정렬기준",options=["게시일","마감일","금액"])
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
        st.write("")  
        # 테이블 헤더
        header_cols = st.columns([2,2, 4, 3, 1, 1,1, 1, 1])
        headers = ['공고번호',"구분",'공고명','공고기관','분류','금액','게시일','마감일','상세정보']

        for col, head in zip(header_cols, headers):
            col.markdown(f"**{head}**")

        st.markdown("<hr style='margin-top: 5px; margin-bottom: 10px;'>", unsafe_allow_html=True) # 헤더 아래 구분선

        # 행 렌더링 + 버튼 (페이지네이션된 데이터 사용)
        for i, row in paginated_df.iterrows():
            cols = st.columns([2,2, 4, 3, 1, 1,1, 1, 1])
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

            # 각 행 아래에 구분선 추가
            st.markdown("<hr style='margin-top: 5px; margin-bottom: 10px;'>", unsafe_allow_html=True)


        # 6. "이전" 및 "다음" 버튼
        cols_pagination = st.columns([1, 3, 1])
        with cols_pagination[0]:
            if st.session_state["current_page"] > 0:
                if st.button("이전"):
                    st.session_state["current_page"] -= 1
                    st.rerun()

        with cols_pagination[2]:
            if st.session_state['current_page'] < total_pages -1:
                if st.button("다음"):
                    st.session_state["current_page"] += 1
                    st.rerun()

        # 7. 페이지 번호 표시    
        st.markdown(f"<div style='text-align: center;'> {st.session_state['current_page'] + 1}</div>", unsafe_allow_html=True)
        
elif page == "detail":
    # ⬅️ 뒤로가기 버튼 추가
    if st.button("⬅️ 뒤로가기"):
        st.session_state["page"] = "home"
        st.rerun()
        
    if "selected_live_bid" in st.session_state:
        row = st.session_state["selected_live_bid"]
        
        st.subheader(f"{row['공고명']}")
        
        st.markdown(f"- **구분:** {row['입찰공고상태명']}")
        st.markdown(f"- **수요기관:** {row['수요기관']}")
        st.markdown(f"- **금액:** {format_won(row['금액'])}")
        st.markdown(f"- **게시일:** {row['게시일'].strftime("%Y-%m-%d")}")        
        # 마감일이 None 또는 NaN인 경우 처리
        if pd.isna(row['마감일']):
            end_date = "공고 참조"
        else:
            end_date = row['마감일'].strftime("%Y-%m-%d")
        # 마감시간이 None 또는 NaN인 경우 처리
        if pd.isna(row['마감시간']):
            end_time = "공고 참조"
        else:
            end_time = row['마감시간']
        st.markdown(f"- **공고마감일:** {end_date} {end_time}")
          # 업종제한 카드 형태 표시
        st.markdown(
            f"""
            <div style="
                background-color: #f9f9f9; 
                border: 1px solid #e5e5e5;
                border-radius: 15px;
                padding: 15px;
                margin-top: 15px;
                margin-bottom: 15px;
                width: 20%;
            ">
                <h4 style="font-size: 20px; font-weight: bold;">🚫업종 제한</h4>
                <hr style="border: 1px solid #e5e5e5; margin-top: 10px; margin-bottom: 10px;">
                <p style="font-size: 18px; font-weight: bold;">
                    {"<br>".join([f"{i+1}. {item.strip()}" for i,
                                  item in enumerate(str(row['투찰가능업종명']).split(','))]) 
                                  if row['투찰가능업종명'] and str(row['투찰가능업종명']).strip() != "" else '공문서참조'}
                </p>
            </div>
            """, unsafe_allow_html=True
        )
    # 📌 GPT 요약 영역 (공고)
    st.markdown("### 🤖 GPT 요약")
    st.info("💡 이 입찰 공고에 대한 GPT 요약이 여기에 표시됩니다. (예: 공사의 목적, 예상 참여사 등)")

        
    
# ------------------------
# 📑 입찰 결과 탭
# ------------------------
with tab2:
    st.subheader("📑 낙찰 완료된 입찰 목록")

    # 1) DataFrame 생성 & 컬럼 정리
    df_result = pd.DataFrame(completed_bids)
    df_result = df_result[[
        "bidNtceNo", "bidNtceNm", "dminsttNm",
        "sucsfbidAmt", "sucsfbidRate", "fnlSucsfDate", "bidwinnrNm"
    ]]
    df_result.columns = [
        "공고번호", "공고명", "발주기관",
        "낙찰금액", "낙찰률", "낙찰일자", "낙찰업체"
    ]

    # 2) 날짜형 변환
    df_result["낙찰일자"] = pd.to_datetime(df_result["낙찰일자"], errors="coerce")

    # 3) 검색어 & 날짜 필터 UI
    search_kw = st.text_input("🔎 공고명 또는 발주기관 검색", key="res_search")
    col1, col2, col3 = st.columns(3)
    with col1:
        res_start = st.date_input("📅 낙찰 시작일", value=df_result["낙찰일자"].min().date(), key="res_sd")
    with col2:
        res_end = st.date_input("📅 낙찰 종료일", value=df_result["낙찰일자"].max().date(), key="res_ed")
    with col3:
        sort_col_r = st.selectbox("정렬기준", options=["낙찰일자", "낙찰금액", "낙찰률"], key="res_sortcol")
        sort_ord_r = st.radio("", options=["오름차순", "내림차순"], horizontal=True, key="res_sortord")
        asc_r = True if sort_ord_r == "오름차순" else False
    # 4) 필터링 적용
    filtered_res = df_result.copy()
    if search_kw:
        filtered_res = filtered_res[
            filtered_res["공고명"].str.contains(search_kw, case=False, na=False, regex=False) |
            filtered_res["발주기관"].str.contains(search_kw, case=False, na=False, regex=False)
        ]
    filtered_res = filtered_res[
        (filtered_res["낙찰일자"].dt.date >= res_start) &
        (filtered_res["낙찰일자"].dt.date <= res_end)
    ]

    

    if sort_col_r == "낙찰금액":
        # 금액에서 쉼표 제거 후 숫자 정렬
        filtered_res["금액_숫자"] = filtered_res["낙찰금액"].str.replace(",", "").astype(float)
        filtered_res = filtered_res.sort_values(by="금액_숫자", ascending=asc_r)
    elif sort_col_r == "낙찰률":
        filtered_res["률_숫자"] = filtered_res["낙찰률"].str.replace("%", "").astype(float)
        filtered_res = filtered_res.sort_values(by="률_숫자", ascending=asc_r)
    else:
        filtered_res = filtered_res.sort_values(by=sort_col_r, ascending=asc_r)

    # 6) 결과 개수 표시
    st.markdown(f"<div style='text-align: left;'>검색 결과 {len(filtered_res)}건</div>", unsafe_allow_html=True)
    st.markdown("---")

    # 7) 페이지네이션
    PAGE_SIZE_R = 10
    def paginate(df, page, size): return df.iloc[page*size:(page+1)*size]

    if "res_page" not in st.session_state:
        st.session_state["res_page"] = 0
    total_pages_r = (len(filtered_res) - 1)//PAGE_SIZE_R + 1
    page_df = paginate(filtered_res, st.session_state["res_page"], PAGE_SIZE_R)

    # 테이블 헤더
    hdr_cols = st.columns([2, 4, 3, 2, 2, 2, 2])
    hdrs = ["공고번호","공고명","발주기관","금액","낙찰률","낙찰일자","상세보기"]
    for c, h in zip(hdr_cols, hdrs):
        c.markdown(f"**{h}**")

    # 행 렌더링 + 상세보기 버튼
    for idx, r in page_df.iterrows():
        row_cols = st.columns([2,4,3,2,2,2,2])
        row_cols[0].write(r["공고번호"])
        row_cols[1].write(r["공고명"])
        row_cols[2].write(r["발주기관"])
        row_cols[3].write(r["낙찰금액"])
        row_cols[4].write(r["낙찰률"])
        row_cols[5].write(r["낙찰일자"].strftime("%Y-%m-%d"))
        if row_cols[6].button("보기", key=f"res_detail_{idx}"):
            st.session_state["selected_result"] = r.to_dict()

    # 페이지 이동 버튼
    coln = st.columns([1,3,1])
    with coln[0]:
        if st.session_state["res_page"] > 0 and st.button("이전", key="res_prev"):
            st.session_state["res_page"] -= 1
            st.rerun()
    with coln[2]:
        if st.session_state["res_page"] < total_pages_r-1 and st.button("다음", key="res_next"):
            st.session_state["res_page"] += 1
            st.rerun()
    st.markdown(f"<div style='text-align:center'>{st.session_state['res_page']+1} / {total_pages_r}</div>", unsafe_allow_html=True)

    # 8) 상세 정보 표시
    if "selected_result" in st.session_state:
        it = st.session_state["selected_result"]
        st.markdown("---")
        st.subheader(f"📌 낙찰 상세: {it['공고명']}")
        st.markdown(f"- **공고번호:** {it['공고번호']}")
        st.markdown(f"- **발주기관:** {it['발주기관']}")
        st.markdown(f"- **낙찰금액:** {it['낙찰금액']} 원")
        st.markdown(f"- **낙찰률:** {it['낙찰률']}")
        st.markdown(f"- **낙찰일자:** {it['낙찰일자']}")
        st.markdown(f"- **낙찰업체:** {it['낙찰업체']}")


    # 📌 GPT 요약 영역 (낙찰 결과)
    st.markdown("### 🤖 GPT 요약")
    st.info("💡 이 입찰 결과에 대한 GPT 요약이 여기에 표시됩니다. (예: 경쟁률, 낙찰업체 특징 등)")

    
