import sqlite3
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request

DB_FILE = "auth.db"

# 데이터베이스 초기화
def init_db():
    """SQLite 데이터베이스 초기화"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS google_auth (
            user_id TEXT PRIMARY KEY,
            credentials TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


# 인증 정보 저장
def save_credentials(credentials, user_id="default_user"):
    """사용자 인증 정보를 SQLite에 저장"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    serialized_credentials = json.dumps({
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    })
    cursor.execute('REPLACE INTO google_auth (user_id, credentials) VALUES (?, ?)', (user_id, serialized_credentials))
    conn.commit()
    conn.close()

# 인증 정보 불러오기
def load_credentials(user_id="default_user"):
    """SQLite에서 사용자 인증 정보를 불러오기"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT credentials FROM google_auth WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        credentials_info = json.loads(row[0])
        credentials = Credentials.from_authorized_user_info(credentials_info)
        # 만료된 토큰 갱신
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            save_credentials(credentials, user_id)
        return credentials
    return None

# 인증 정보 존재 여부 확인
def is_authenticated(user_id="default_user"):
    """사용자 인증 여부 확인"""
    credentials = load_credentials(user_id)
    return credentials is not None and not (credentials.expired and not credentials.refresh_token)
