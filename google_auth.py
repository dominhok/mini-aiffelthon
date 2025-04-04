import os
import pickle
from pathlib import Path
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# 인증 관련 상수 정의
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events'
]
TOKEN_FILE = 'token.pickle'

def create_oauth_flow(redirect_uri):
    """OAuth 인증 흐름 생성"""
    client_config = {
        "web": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri]
        }
    }
    
    return Flow.from_client_config(
        client_config=client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )

def get_authorization_url(flow):
    """인증 URL 생성"""
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    return auth_url

def fetch_token(flow, code):
    """인증 코드로 토큰 가져오기"""
    flow.fetch_token(code=code)
    return flow.credentials

def save_credentials(credentials, user_id=None):
    """사용자 인증 정보 저장"""
    token_path = Path(TOKEN_FILE)
    if user_id:
        token_path = Path(f"token_{user_id}.pickle")
    
    with open(token_path, 'wb') as token:
        pickle.dump(credentials, token)
    
    return token_path

def load_credentials(user_id=None):
    """저장된 인증 정보 불러오기"""
    token_path = Path(TOKEN_FILE)
    if user_id:
        token_path = Path(f"token_{user_id}.pickle")
    
    credentials = None
    if token_path.exists():
        with open(token_path, 'rb') as token:
            credentials = pickle.load(token)
    
    # 토큰이 만료되었으면 갱신
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        save_credentials(credentials, user_id)
    
    return credentials

def build_gmail_service(credentials):
    """Gmail API 서비스 생성"""
    return build('gmail', 'v1', credentials=credentials)

def build_calendar_service(credentials):
    """Calendar API 서비스 생성"""
    return build('calendar', 'v3', credentials=credentials)

def is_authenticated(user_id=None):
    """사용자 인증 여부 확인"""
    credentials = load_credentials(user_id)
    return credentials is not None and not (credentials.expired and not credentials.refresh_token)
