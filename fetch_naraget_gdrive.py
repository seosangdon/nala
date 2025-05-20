import requests
import json
from pymongo import MongoClient
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote_plus

# MongoDB 연결 설정
client = MongoClient('mongodb://192.168.56.108:27017/')
db = client['local']

# 두 개의 컬렉션 설정
collection_bids = db['ai_coding_bids']  # 공고 관련 컬렉션
collection_bids_status = db['ai_coding_bids_status']  # 낙찰 관련 컬렉션

# 유니크 인덱스 생성 (한 번만 실행)
collection_bids.create_index("bidNtceNo", unique=True)
collection_bids_status.create_index("bidNtceNo", unique=True)

# 마지막 수집 시점 로드 함수
def load_last_collected_time(file_name, default_value):
    try:
        with open(file_name, 'r') as f:
            return json.load(f)['last_collected_time']
    except (FileNotFoundError, KeyError):
        return default_value

# ① 입찰 공고 데이터 상태 추적
last_collected_file_bids = 'last_collected_time_bids.json'
last_collected_time_bids = load_last_collected_time(last_collected_file_bids, (datetime.now() - timedelta(minutes=5)).strftime('%Y%m%d%H%M'))# 처음 시작 시 5분 전


# 입찰 공고 API 호출
API_KEY = "DcZ5b7lx/oHvPlE7aW4wTlrptzalhS9RwW5qUWfFc1MgsRjOO3pKHLspaIbRaImLNj1B7KoOYRV1tgH0zQbYCQ=="
BASE_URL = "http://apis.data.go.kr/1230000/ao/PubDataOpnStdService/getDataSetOpnStdBidPblancInfo"

num = 1
info = []

while True:

    # last_collected_time_bids가 None일 경우 기본값 설정
    if last_collected_time_bids is None:
        last_collected_time_bids = (datetime.now() - timedelta(minutes=5)).strftime('%Y%m%d%H%M')  # 5분 전

    params = {
        'serviceKey': API_KEY,
        'pageNo': num,
        'numOfRows': 100,
        'inqryDiv': 1,
        'type': 'json',
        'bidNtceBgnDt': int(last_collected_time_bids),  # 마지막 수집 시점 이후 데이터만 요청
        'bidNtceEndDt': int(f"{datetime.now().strftime('%Y%m%d%H%M')}"),
    }

    query_string = urlencode(params, quote_via=quote_plus)
    URL = f"{BASE_URL}?{query_string}"

    try:
        response = requests.get(URL).json()
        items = response['response']['body']['items']
    except requests.exceptions.RequestException as e:
        print(f"API 호출 오류: {e}")
        break
    except KeyError:
        print("응답 형식 오류: 'items' 키가 없음")
        break

    if not items:
        break
    else:
        info.extend(items)
        num += 1

    # 마지막 수집 시점 갱신 (입찰 공고)
    last_collected_time_bids = items[-1].get('bidNtceBgnDt', None)  # 마지막 공고의 bidNtceBgnDt 기준
    if last_collected_time_bids:
        with open(last_collected_file_bids, 'w') as f:
            json.dump({"last_collected_time": last_collected_time_bids}, f)


# 공고 데이터 리스트
from pymongo import UpdateOne
operations = []
for item in info:
    bid_no = item.get("bidNtceNo")
    if bid_no:
        operations.append(
            
            UpdateOne(
                {"bidNtceNo": bid_no},
                {"$set": item},
                upsert=True
            )
        )

# bulk_write 수행
if operations:
    try:
        result = collection_bids.bulk_write(operations)
        print(f"업데이트: {result.modified_count}, 삽입: {result.upserted_count}")
    except Exception as e:
        print(f"bulk_write 중 오류 발생: {e}")
else:
    print("처리할 항목이 없습니다.")

# ② 낙찰 정보 데이터 상태 추적
last_collected_file_status = 'last_collected_time_status.json'

# 마지막 수집 시점 로드 (낙찰 정보)
try:
    with open(last_collected_file_status, 'r') as f:
        last_collected_time_status = json.load(f)['last_collected_time']
except FileNotFoundError:
    last_collected_time_status = (datetime.now() - timedelta(minutes=5)).strftime('%Y%m%d%H%M')  # 낙찰 정보의 기본 시작 시점

# ② 낙찰 정보 API 호출
service_key = "6FAWdycqkHj1fAb/TpeNQLlEzjIB+7eozDneMjTwZPUWDmva0FamSPT1uGtzrxVKuub/vADLVft2bCZ+hkL5YA=="
url =  f"http://apis.data.go.kr/1230000/as/ScsbidInfoService/getScsbidListSttusThng"

params = {
    'serviceKey': service_key,
    'numOfRows': '10',
    'pageNo': '1',
    'inqryDiv': '1',        # 1: 오늘, 2: 기간 조회
    'inqryBgnDt': int(last_collected_time_bids),  # 조회 시작일
    'inqryEndDt': int(f"{datetime.now().strftime('%Y%m%d%H%M')}"),  # 조회 종료일
    'type': 'json',         # 응답 형식 (json or xml)
}

response = requests.get(url, params=params)
data = response.json()

# 낙찰 데이터 처리 및 MongoDB에 저장
for item in data['response']['body']['items']:
    bid_no = item.get("bidNtceNo")
    try:
        collection_bids_status.update_one(
            {"bidNtceNo": bid_no},
            {"$set": item},
            upsert=True
        )
    except Exception as e:
        print(f"낙찰 데이터 업데이트 중 오류 발생: {e}")

# 마지막 수집 시점 갱신 (낙찰 정보)
last_collected_time_status = data['response']['body']['items'][-1].get('bidNtceNo', None)  # 마지막 낙찰 공고의 bidNtceNo 기준
if last_collected_time_status:
    with open(last_collected_file_status, 'w') as f:
        json.dump({"last_collected_time": last_collected_time_status}, f)

print("✅ 낙찰 정보 저장 완료")
