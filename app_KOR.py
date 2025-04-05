import streamlit as st
import asyncio
import nest_asyncio
import anyio
import os

# components 폴더에서 필요한 모듈 임포트
from components.interests_tab import interests_tab
from components.secretary_tab import secretary_tab

# # nest_asyncio 적용: 이미 실행 중인 이벤트 루프 내에서 중첩 호출 허용 -> 주석 처리
# nest_asyncio.apply()

# 전역 이벤트 루프 생성 및 재사용
if "event_loop" not in st.session_state:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    st.session_state.event_loop = loop

# # anyio 백엔드 설정 -> 주석 처리
# os.environ["ANYIO_BACKEND"] = "asyncio"



# 페이지 설정: 제목, 아이콘, 레이아웃 구성
# 브라우저 탭에 표시될 제목과 아이콘이다.
st.set_page_config(page_title="나만의 비서 나비", page_icon="🦋", layout="wide")

# --- 탭 생성 --- START
tab1, tab2 = st.tabs(["🦋 나비 비서", "🔍 관심분야 보고서"])
# --- 탭 생성 --- END

# ==========================
#        탭 1: 나비 비서
# ==========================
with tab1:
    secretary_tab()

# ==========================
#        탭 2: 관심분야 보고서
# ==========================
with tab2:
    interests_tab()