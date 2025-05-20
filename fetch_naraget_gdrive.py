from urllib.parse import urlencode, quote_plus
from datetime import datetime, timedelta
import requests
import json
import os
import logging
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('naraget_api')

# API 설정
API_KEY = os.environ.get("API_KEY", "")  # 환경 변수에서 가져오기
BASE_URL = "http://apis.data.go.kr/1230000/ao/PubDataOpnStdService/getDataSetOpnStdBidPblancInfo"

# 구글 드라이브 폴더 ID (데이터를 저장할 폴더)
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")

def authenticate_google_drive():
    """Google Drive API 인증"""
    try:
        # 서비스 계정 인증 설정
        gauth = GoogleAuth()
        
        # 서비스 계정 사용 (키 파일은 환경에 따라 경로 조정 필요)
        # 환경 변수에서 내용을 가져오거나 파일에서 읽을 수 있음
        service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "service_account.json")
        
        # 서비스 계정 JSON이 환경 변수에 내용으로 제공된 경우
        if service_account_json.startswith('{'):
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                temp_file.write(service_account_json)
                temp_file_path = temp_file.name
            scope = ['https://www.googleapis.com/auth/drive']
            credentials = ServiceAccountCredentials.from_json_keyfile_name(temp_file_path, scope)
            os.unlink(temp_file_path)  # 임시 파일 삭제
        else:
            # 서비스 계정 JSON이 파일로 제공된 경우
            scope = ['https://www.googleapis.com/auth/drive']
            credentials = ServiceAccountCredentials.from_json_keyfile_name(service_account_json, scope)
        
        gauth.credentials = credentials
        drive = GoogleDrive(gauth)
        logger.info("구글 드라이브 인증 성공")
        return drive
    except Exception as e:
        logger.error(f"구글 드라이브 인증 오류: {e}")
        raise

def fetch_naraget_data():
    """나라장터 API에서 입찰공고 데이터를 가져옵니다."""
    num = 1
    info = []

    while True:
        # API 요청 파라미터 설정
        params = {
            'serviceKey': API_KEY,
            'pageNo': num,
            'numOfRows': 100,
            'inqryDiv': 1,  # 조회구분
            'type': 'json',  # 응답 형식 지정 (xml 또는 json)
            'bidNtceBgnDt': (datetime.now() - timedelta(minutes=5)).strftime('%Y%m%d%H%M'),  # 조회시작일시(5분 전)
            'bidNtceEndDt': datetime.now().strftime('%Y%m%d%H%M')  # 조회종료일시(현재 시각 기준)
        }

        # API 호출 URL 생성
        query_string = urlencode(params, quote_via=quote_plus)
        URL = f"{BASE_URL}?{query_string}"

        # API 호출하기
        try:
            logger.info(f"API 요청 시도: 페이지 {num}")
            response = requests.get(URL).json()
            items = response['response']['body']['items']
        except requests.exceptions.RequestException as e:
            logger.error(f"API 호출 오류: {e}")
            break
        except KeyError as e:
            logger.error(f"응답 형식 오류: {e}, 전체 응답:{response}")
            break

        if not items:
            logger.info("더 이상 데이터가 없습니다.")
            break
        else:
            logger.info(f"페이지 {num}에서 {len(items)}개 항목 수신")
            info.extend(items)  # 데이터 추가
            num += 1

    return info

def save_to_google_drive(data, drive):
    """데이터를 구글 드라이브에 저장합니다."""
    try:
        # 현재 시간으로 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"naraget_data_{timestamp}.json"
        
        # 임시 파일 생성
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "count": len(data),
                "items": data
            }, f, ensure_ascii=False, indent=2)
        
        # 구글 드라이브에 파일 업로드
        gfile = drive.CreateFile({
            'title': filename,
            'parents': [{'id': GOOGLE_DRIVE_FOLDER_ID}]
        })
        gfile.SetContentFile(filename)
        gfile.Upload()
        
        # 임시 파일 삭제
        os.remove(filename)
        
        logger.info(f"구글 드라이브에 파일 업로드 성공: {filename}")
        return True
    except Exception as e:
        logger.error(f"구글 드라이브 파일 업로드 오류: {e}")
        return False

def main():
    """메인 실행 함수"""
    if not API_KEY:
        logger.error("API_KEY 환경 변수가 설정되지 않았습니다.")
        return
    
    if not GOOGLE_DRIVE_FOLDER_ID:
        logger.error("GOOGLE_DRIVE_FOLDER_ID 환경 변수가 설정되지 않았습니다.")
        return
    
    try:
        # 구글 드라이브 인증
        drive = authenticate_google_drive()
        
        # 데이터 가져오기
        logger.info("나라장터 API 데이터 수집 시작")
        data = fetch_naraget_data()
        
        if data:
            logger.info(f"총 {len(data)}개 입찰공고 데이터를 수집했습니다.")
            # 구글 드라이브에 저장
            save_to_google_drive(data, drive)
        else:
            logger.info("수집된 데이터가 없습니다.")
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {e}")

if __name__ == "__main__":
    main()
