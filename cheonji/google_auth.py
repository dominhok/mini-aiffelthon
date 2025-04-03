import os
import pickle
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 인증 관련 상수
CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'http://localhost:8501/')
SCOPES = os.getenv('SCOPES', 'https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/calendar.events').split(',')
TOKEN_PATH = 'token.pickle'

def create_client_config():
    """OAuth 클라이언트 설정 생성"""
    return {
        "web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uris": [REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }

def get_google_auth_url():
    """Google OAuth 인증 URL 생성"""
    flow = InstalledAppFlow.from_client_config(
        create_client_config(), 
        SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    return auth_url, flow

def handle_auth_callback(flow, code):
    """인증 콜백 처리 및 토큰 저장"""
    try:
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # 토큰 저장
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(credentials, token)
            
        return credentials
    except Exception as e:
        print(f"인증 처리 중 오류 발생: {e}")
        return None

def get_credentials():
    """저장된 인증 정보 가져오기 또는 새로 인증 필요 여부 확인"""
    credentials = None
    
    # 토큰 파일이 있으면 로드
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            credentials = pickle.load(token)
    
    # 유효한 인증 정보가 있는지 확인
    if credentials and credentials.valid:
        return credentials, False
    
    # 만료된 토큰이 있고 갱신 가능하면 갱신
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            with open(TOKEN_PATH, 'wb') as token:
                pickle.dump(credentials, token)
            return credentials, False
        except:
            # 갱신 실패 시 새로 인증 필요
            return None, True
    
    # 인증 정보가 없으면 새로 인증 필요
    return None, True

def build_calendar_service(credentials):
    """Google Calendar API 서비스 생성"""
    return build('calendar', 'v3', credentials=credentials)
