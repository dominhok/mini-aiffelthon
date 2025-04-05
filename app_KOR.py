import streamlit as st
import asyncio
import nest_asyncio
import json
import anyio
import os
from pathlib import Path
import pickle

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

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_teddynote.messages import astream_graph, random_uuid
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.messages.tool import ToolMessage
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from langchain_upstage import ChatUpstage

# Google 인증 관련 모듈 임포트
from google_auth import (
    create_oauth_flow, get_authorization_url, fetch_token, 
    save_credentials, load_credentials, is_authenticated,
    build_gmail_service, build_calendar_service
)
from calendar_utils import create_calendar_event
from gmail_utils import send_email
from datetime import datetime

# 환경 변수 로드 (.env 파일에서 API 키 등의 설정을 가져옴)
load_dotenv(override=True)

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
    # --- 사이드바 상단 서비스 소개 --- START
    with st.sidebar.container(border=True):
        st.markdown("### 🦋 나만의 비서: 나비")
        st.caption("**나비**는 당신의 일상을 더 스마트하게 관리하도록 돕는 AI 비서입니다.") # caption으로 변경
 
        st.markdown("📧 **Gmail 및 캘린더 연동**")
        st.caption("메일 확인/작성 및 캘린더 일정 관리") # 각 항목 설명은 caption 사용
        
        st.markdown("📰 **관심 분야 조사**")
        st.caption("최신 정보 보고서 받기")
        
        st.markdown("💬 **일상 대화**")
        st.caption("날씨 질문, 간단한 대화 등")
        
    # --- 사이드바 상단 서비스 소개 --- END

    # 기존 페이지 타이틀 및 설명
    # 웹 페이지의 타이틀과 설명이다.
    st.title("🦋 나만의 비서: 나비")
    st.markdown("✨ **나비, 당신의 하루를 더 가볍게 만들어줄 스마트 비서!** ✨")

    # --- 화면 하단 고정 입력창 CSS --- START
    st.markdown("""
    <style>
        /* 메인 콘텐츠 영역에 하단 여백 추가 (입력창에 가려지지 않도록) */
        /* 선택자는 Streamlit 구조에 따라 달라질 수 있습니다. */
        .main .block-container {
            padding-bottom: 8rem; /* 입력창 높이에 맞춰 조정 (기존 5rem -> 8rem으로 증가) */
        }

        /* st.chat_input 위젯 자체를 타겟팅하여 고정 */
        div[data-testid="stChatInput"] {
            position: fixed;
            bottom: 0;
            /* width: calc(100% - 1rem); */ /* 너비 자동 조정으로 변경 */
            background-color: #9CA3AF; /* 배경색 흰색으로 변경 */
            padding: 1rem 1rem 1rem 1rem; /* 위, 오른쪽, 아래, 왼쪽 여백 */
            border-top: 1px solid #e0e0e0; /* 구분선 */
            z-index: 999;
            left: 0; /* 왼쪽 정렬 */
            right: 0; /* 오른쪽 정렬 추가하여 전체 너비 차지 */
            /* margin-left: 0.5rem; */ /* 마진 제거 */
            /* margin-right: 0.5rem; */ /* 마진 제거 */
            box-sizing: border-box; /* 패딩과 테두리를 너비에 포함 */
            transition: left 0.3s ease; /* left 속성 변경 시 0.3초 동안 부드럽게 전환 */
        }

        /* Streamlit 1.33 이상에서 사이드바 너비를 고려한 chat_input 위치 조정 */
        @media (min-width: 576px) { /* 모바일 뷰 이상에서 적용 */
            div[data-testid="stChatInput"] {
                left: 324px; /* 사이드바 너비만큼 왼쪽 오프셋 (기본값 기준, 테마/설정에 따라 조정 필요) */
            }
        }

        /* 사이드바 토글 버튼 숨기기 */
        button[data-testid="stSidebarNavToggle"] {
            display: none;
        }

        /* 사이드바 리사이즈 커서 제거 */
        section[data-testid="stSidebar"] {
            cursor: default !important;
        }
    </style>
    """, unsafe_allow_html=True)
    # --- 화면 하단 고정 입력창 CSS --- END

    # 세션 상태 초기화
    if "session_initialized" not in st.session_state:
        st.session_state.session_initialized = False  # 세션 초기화 상태 플래그
        st.session_state.agent = None  # ReAct 에이전트 객체 저장 공간
        st.session_state.history = []  # 대화 기록 저장 리스트
        st.session_state.mcp_client = None  # MCP 클라이언트 객체 저장 공간

        ### 구글 인증 관련
        st.session_state.google_authenticated = False  # Google 인증 상태
        st.session_state.gmail_service = None  # Gmail 서비스 객체
        st.session_state.calendar_service = None  # 캘린더 서비스 객체

        # 폼 표시 상태 변수 초기화
        st.session_state.show_email_form_area = False
        st.session_state.show_calendar_form_area = False
        st.session_state.just_submitted_form = False # 폼 제출 직후 상태 플래그
        st.session_state.initial_greeting = None # 초기 환영 메시지 저장
        st.session_state.needs_greeting_regeneration = False # 인증 후 인사말 재생성 필요 플래그
        # st.session_state.user_interests = "" # <<< 이 라인 삭제

        # 정보 검색 탭 관련 초기화 추가
        st.session_state.briefing_result = None # 관심 분야 브리핑 결과
        st.session_state.last_briefed_interests = None # 마지막 브리핑된 관심 분야

    # --- 관심 분야 저장/로드 함수 --- START
    INTERESTS_FILE = "interests.pickle"

    def save_interests(interests):
        """사용자 관심 분야를 pickle 파일에 저장합니다."""
        try:
            with open(INTERESTS_FILE, "wb") as f:
                pickle.dump(interests, f)
            print(f"DEBUG: Interests saved to {INTERESTS_FILE}")
            return True
        except Exception as e:
            st.error(f"관심 분야 저장 중 오류 발생: {e}")
            print(f"ERROR saving interests: {e}")
            return False

    def load_interests():
        """pickle 파일에서 사용자 관심 분야를 로드합니다."""
        if Path(INTERESTS_FILE).exists():
            try:
                with open(INTERESTS_FILE, "rb") as f:
                    interests = pickle.load(f)
                    print(f"DEBUG: Interests loaded from {INTERESTS_FILE}")
                    return interests
            except Exception as e:
                st.error(f"관심 분야 로드 중 오류 발생: {e}")
                print(f"ERROR loading interests: {e}")
                # 파일이 손상되었을 수 있으므로 삭제 고려
                # try:
                #     Path(INTERESTS_FILE).unlink()
                #     st.warning(f"{INTERESTS_FILE} 파일이 손상되어 삭제되었습니다.")
                # except Exception as del_e:
                #     print(f"ERROR deleting corrupted interests file: {del_e}")
        return "" # 파일 없거나 오류 시 빈 문자열 반환
    # --- 관심 분야 저장/로드 함수 --- END

    # --- 앱 시작 시 관심 분야 로드 --- START
    if 'user_interests' not in st.session_state:
        st.session_state.user_interests = load_interests()
    # --- 앱 시작 시 관심 분야 로드 --- END

    # --- 백그라운드 브리핑 생성 함수 --- START
    async def generate_briefing_background():
        """백그라운드에서 관심 분야 브리핑을 생성하고 세션 상태에 저장합니다."""
        interests = st.session_state.get("user_interests", "")
        if not interests:
            print("DEBUG (Background Briefing): No interests set, skipping briefing generation.")
            return

        print(f"DEBUG (Background Briefing): Starting briefing generation for: {interests}")
        # 세션 초기화 완료 및 클라이언트 존재 확인
        if not st.session_state.get("session_initialized") or not st.session_state.get("mcp_client"):
            print("ERROR (Background Briefing): Session or MCP client not ready.")
            # 결과 비우기 (이전 결과가 남아있을 수 있으므로)
            st.session_state.briefing_result = "시스템 준비 중 오류로 브리핑을 생성할 수 없습니다."
            return

        try:
            client = st.session_state.mcp_client
            tools = client.get_tools()
            search_tool = next((t for t in tools if t.name in ['pplx_search', 'perplexity_search']), None)

            if not search_tool:
                print("ERROR (Background Briefing): Perplexity search tool not found.")
                st.session_state.briefing_result = "검색 도구를 찾을 수 없어 브리핑 생성에 실패했습니다."
                return

            search_prompt = f"Summarize the latest developments and key information about: {interests}. Provide a concise overview suitable for a briefing."
            result = await search_tool.ainvoke({"query": search_prompt})
            st.session_state.briefing_result = result
            print(f"DEBUG (Background Briefing): Briefing generation complete for: {interests}")

        except Exception as e:
            print(f"ERROR (Background Briefing): Failed to generate briefing for {interests}: {e}")
            st.session_state.briefing_result = f"오류로 인해 브리핑 생성에 실패했습니다: {e}"
    # --- 백그라운드 브리핑 생성 함수 --- END

    def initialize_google_services():
        """
        Google 서비스(Gmail, 캘린더)를 초기화합니다.
        """
        if is_authenticated():
            credentials = load_credentials()
            st.session_state.gmail_service = build_gmail_service(credentials)
            st.session_state.calendar_service = build_calendar_service(credentials)
            st.session_state.google_authenticated = True
            return True
        return False

    # --- Google 서비스 사전 초기화 (토큰 파일 존재 시) --- START
    if not st.session_state.google_authenticated and is_authenticated():
        print("DEBUG: Token file found, attempting pre-initialization of Google services.")
        initialize_google_services()
        if st.session_state.google_authenticated:
             print("DEBUG: Google services pre-initialized successfully.")
        else:
             print("DEBUG: Google services pre-initialization failed (likely token issue).")
    # --- Google 서비스 사전 초기화 (토큰 파일 존재 시) --- END

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = random_uuid()

    ### Google 인증 관련 상수
    REDIRECT_URI = "http://localhost:8501/callback"

    # --- 사용자 정의 예외 --- START
    class StopStreamAndRerun(Exception):
        """콜백에서 스트림 중단 및 rerun 필요 신호를 보내기 위한 예외"""
        pass
    # --- 사용자 정의 예외 --- END

    async def run_initial_tools_and_summarize():
        """
        앱 시작 시 필요한 도구를 호출하고 결과를 구조화하여 요약하고,
        사용 가능한 기능을 안내하는 환영 메시지를 생성합니다.
        Google 인증 상태에 따라 분기하여 처리합니다.
        """
        initial_greeting = "안녕하세요! 당신만의 비서 나비입니다. 무엇을 도와드릴까요? 🦋" # 기본 인사말
        weather_result = "날씨 정보를 가져오는 데 실패했어요."
        # calendar_result와 email_result는 인증 상태 분기 내에서 초기화

        with st.spinner("🦋 비서 '나비'가 오늘의 정보를 준비하고 있어요..."):
            try:
                # LLM 모델 준비 확인 (공통)
                llm = None
                if hasattr(st.session_state, 'llm_model') and st.session_state.llm_model is not None:
                    llm = st.session_state.llm_model
                else:
                    print("DEBUG: LLM model not found in session state for greeting generation.")
                    # LLM 없으면 기본 인사말 바로 반환 (기능 안내 포함)
                    return """안녕하세요! 비서 나비입니다 🦋
정보 요약 기능을 사용하려면 LLM 설정이 필요해요.

**제가 도와드릴 수 있는 일:**
* 날씨 질문, 간단한 대화
* (Google 계정 연동 시) 이메일 및 캘린더 관련 기능

무엇을 도와드릴까요?"""

                # MCP 클라이언트 및 기본 도구 준비 확인 (공통)
                if not st.session_state.mcp_client:
                    print("DEBUG: MCP Client not ready for initial summary.")
                    # MCP 클라이언트 없으면 기본 인사말 반환
                    return """안녕하세요! 비서 나비입니다 🦋
도구 서버에 연결할 수 없어 정보 조회가 불가능해요.

**제가 도와드릴 수 있는 일:**
* 간단한 대화

무엇을 도와드릴까요?"""
                
                client = st.session_state.mcp_client
                tools = client.get_tools()
                weather_tool = next((t for t in tools if t.name == 'get_weather'), None)

                # --- Google 인증 상태에 따른 분기 --- START
                if st.session_state.google_authenticated:
                    # --- 인증된 사용자 로직 --- START
                    calendar_result = "가장 가까운 일정을 가져오는 데 실패했어요."
                    email_result = "중요한 이메일을 확인하는 데 실패했어요."
                    list_events_tool = next((t for t in tools if t.name == 'list_events_tool'), None)
                    list_emails_tool = next((t for t in tools if t.name == 'list_emails_tool'), None)

                    # 1. 날씨 정보 (인증 사용자)
                    if weather_tool:
                        try:
                            result = await weather_tool.ainvoke({})
                            weather_result = str(result)
                        except Exception as e: print(f"ERROR invoking get_weather (auth): {e}")
                    else: weather_result = "날씨 도구를 찾을 수 없어요."

                    # 2. 가장 가까운 일정 (인증 사용자)
                    if list_events_tool:
                        try:
                            result = await list_events_tool.ainvoke({"max_results": 1})
                            calendar_result = str(result)
                            if not calendar_result or "다가오는 일정이 없습니다" in calendar_result or "일정을 찾을 수 없습니다" in calendar_result:
                                calendar_result = "가장 가까운 예정된 일정이 없어요. 여유로운 하루를 보내세요!"
                            elif "Google 계정 인증이 필요합니다" in calendar_result: calendar_result = "Google 계정 연동 오류."
                        except Exception as e:
                            print(f"ERROR invoking list_events_tool (auth): {e}")
                            calendar_result = "일정 확인 중 오류 발생."
                    else: calendar_result = "캘린더 도구를 찾을 수 없어요."

                    # 3. 최근 10개 이메일 (인증 사용자, LLM 요약용)
                    if list_emails_tool:
                        try:
                            result = await list_emails_tool.ainvoke({"max_results": 10})
                            email_result = str(result)
                            if not email_result or "메일을 찾을 수 없습니다" in email_result: email_result = "최근 도착 메일 없음."
                        except Exception as e:
                            print(f"ERROR invoking list_emails_tool (auth): {e}")
                            email_result = "이메일 확인 중 오류 발생."
                    else: email_result = "이메일 도구를 찾을 수 없어요."

                    # 4. LLM 프롬프트 (인증 사용자)
                    prompt = f"""당신은 사용자 비서 '나비'입니다. 다음 정보를 바탕으로 사용자에게 **정중하면서도 친근하고 도움이 되는 어조**로, 구조화된 환영 인사를 **'~습니다' 체**로 생성해주세요. **과도한 격식 표현(~님, 친애하는 등)이나 너무 가벼운 말투(반말, 속어)는 피해주세요.**

**환영 인사 구조:**
1. **정중하고 친근한** 인사말 (예: "안녕하세요! 당신의 스마트 비서, 나비입니다. 🦋" 또는 "오늘 하루, 나비와 함께 가볍게 시작해 보세요! 🦋")
2. **오늘의 정보 요약** 섹션 (날씨, 가장 가까운 일정, 중요 이메일 요약 - 각 항목은 주어진 정보를 바탕으로 **정중하고 친근하게** 생성)
3. **제가 도와드릴 수 있는 일** 섹션 (아래 목록 전체 안내, **명확하고 친절하게**)
    * 이메일: 새 메일 확인, 특정 메일 검색, 이메일 작성 및 보내기
    * 캘린더: 일정 확인, 새로운 일정 추가
    * 날씨: 현재 날씨 질문
    * 기타: 간단한 대화나 궁금한 점 질문하기
4. **도움을 제안하는** 마무리 인사 (예: "무엇을 도와드릴까요?" 또는 "어떤 작업을 시작할까요?")

**주어진 정보:**
[날씨] {weather_result}
[일정] {calendar_result}
[최근 이메일 목록] {email_result}

**정중하면서도 친근한 '~습니다' 체로 구조화된 환영 인사를 작성해주세요:**
"""
                    try:
                        print("DEBUG: Invoking LLM for authenticated user greeting...")
                        response = await llm.ainvoke(prompt)
                        initial_greeting = response.content
                        print(f"DEBUG: Generated authenticated greeting: {initial_greeting}")
                    except Exception as e:
                        print(f"ERROR generating authenticated greeting with LLM: {e}")
                        initial_greeting = f"""안녕하세요! 비서 나비입니다 🦋

**오늘의 정보 요약:**
* 날씨: {weather_result}
* 가까운 일정: {calendar_result}
* 이메일: {email_result} (요약 실패)

**제가 도와드릴 수 있는 일:**
* 이메일: 확인, 검색, 작성/전송
* 캘린더: 일정 확인, 새 일정 추가
* 날씨: 현재 날씨 질문
* 기타: 간단한 대화

무엇을 도와드릴까요?"""
                    # --- 인증된 사용자 로직 --- END
                
                else:
                    # --- 미인증 사용자 로직 --- START
                    # 1. 날씨 정보 (미인증 사용자)
                    if weather_tool:
                        try:
                            result = await weather_tool.ainvoke({})
                            weather_result = str(result)
                        except Exception as e: print(f"ERROR invoking get_weather (unauth): {e}")
                    else: weather_result = "날씨 도구를 찾을 수 없어요."
                    
                    # 2. LLM 프롬프트 (미인증 사용자)
                    prompt = f"""당신은 사용자 비서 '나비'입니다. 다음 정보를 바탕으로 사용자에게 **정중하면서도 친근하고 도움이 되는 어조**로, 구조화된 환영 인사를 **'~습니다' 체**로 생성해주세요. **과도한 격식 표현(~님, 친애하는 등)이나 너무 가벼운 말투(반말, 속어)는 피해주세요.**

**환영 인사 구조:**
1. **정중하고 친근한** 인사말 (예: "안녕하세요! 당신의 스마트 비서, 나비입니다. 🦋")
2. **오늘의 날씨 정보** 섹션 (주어진 날씨 정보 요약, **정중하고 친근하게**)
3. **Google 계정 연동 안내** 섹션 (연동 시 이메일/캘린더 기능 사용 가능함을 **명확하고 친절하게** 안내)
4. **현재 도와드릴 수 있는 일** 섹션 (아래 목록 안내, **명확하고 친절하게**)
    * 날씨: 현재 날씨 질문
    * 기타: 간단한 대화나 궁금한 점 질문하기
5. **도움을 제안하는** 마무리 인사 (예: "무엇을 도와드릴까요?")

**주어진 정보:**
[날씨] {weather_result}

**정중하면서도 친근한 '~습니다' 체로 구조화된 환영 인사를 작성해주세요:**
"""
                    try:
                        print("DEBUG: Invoking LLM for unauthenticated user greeting...")
                        response = await llm.ainvoke(prompt)
                        initial_greeting = response.content
                        print(f"DEBUG: Generated unauthenticated greeting: {initial_greeting}")
                    except Exception as e:
                        print(f"ERROR generating unauthenticated greeting with LLM: {e}")
                        initial_greeting = f"""안녕하세요! 비서 나비입니다 🦋

**오늘의 날씨:**
* {weather_result}

**Google 계정을 연동하시면** 이메일 확인 및 작성, 캘린더 일정 관리 기능도 사용할 수 있어요!

**현재 도와드릴 수 있는 일:**
* 날씨 질문
* 간단한 대화

무엇을 도와드릴까요?"""
                    # --- 미인증 사용자 로직 --- END
                # --- Google 인증 상태에 따른 분기 --- END

            except Exception as e:
                print(f"ERROR during initial tool run and summary: {e}")
                # 전체 프로세스 오류 시 기본 인사말 (공통)
                initial_greeting = """안녕하세요! 비서 나비입니다 🦋 정보를 준비하는 중 문제가 발생했어요.

**제가 도와드릴 수 있는 일:**
* 날씨 질문, 간단한 대화
* (Google 계정 연동 시) 이메일 및 캘린더 관련 기능

필요하신 도움이 있다면 말씀해주세요!"""

        return initial_greeting


    def print_message():
        """
        채팅 기록을 화면에 출력합니다.

        사용자와 어시스턴트의 메시지를 구분하여 화면에 표시하고,
        도구 호출 정보는 메시지 아래에 마크다운으로 표시합니다. (Expander 제거)
        """
        # 전체 메시지 기록을 순회하며 표시
        for message in st.session_state.history:
            if message["role"] == "user":
                st.chat_message("user").markdown(message["content"])
            elif message["role"] == "assistant":
                with st.chat_message("assistant"):
                    st.markdown(message["content"]) # 메시지 본문 표시
                    # 도구 결과가 저장되어 있으면 본문 아래에 마크다운으로 표시 (Expander 대신)
                    if "tool_output" in message and message["tool_output"]:
                        st.markdown("\n---\n**🔧 도구 실행 결과:**") # 구분선 및 제목 추가
                        st.markdown(message["tool_output"])
            # elif message["role"] == "assistant_tool": # 이 형식은 사용하지 않음
            #     ...


    def get_streaming_callback(text_placeholder):
        accumulated_text = []
        tool_results = []
        formatted_tool_results_for_history = [] # 히스토리 저장용은 유지

        def callback_func(message: dict):
            nonlocal accumulated_text, tool_results, formatted_tool_results_for_history
            message_content = message.get("content", None)

            if isinstance(message_content, AIMessageChunk):
                # 에이전트 텍스트 처리 (텍스트 누적 및 UI 업데이트)
                if hasattr(message_content, "content") and isinstance(message_content.content, str):
                     accumulated_text.append(message_content.content)
                     complete_response = "".join(accumulated_text)
                     text_placeholder.markdown(complete_response) # UI 업데이트 복구

                # 도구 호출 청크 처리 (폼 트리거 로직 유지)
                if hasattr(message_content, 'tool_call_chunks') and message_content.tool_call_chunks:
                    for chunk in message_content.tool_call_chunks:
                        tool_name = chunk.get('name')
                        tool_args_str = chunk.get('args', '')

                        # 빈 인수 감지 및 폼 트리거 로직 (이전과 동일)
                        if tool_name in ["send_email_tool", "create_event_tool"]:
                            is_empty_args = False
                            if not tool_args_str or tool_args_str == '{}': is_empty_args = True
                            else:
                                try:
                                    parsed_args = json.loads(tool_args_str)
                                    if isinstance(parsed_args, dict) and not parsed_args: is_empty_args = True
                                except json.JSONDecodeError: pass
                            if is_empty_args:
                                print(f"DEBUG (Callback): Detected empty args for {tool_name}. Checking context...")
                                
                                # --- 폼 제출 직후 상태 확인 로직 --- START
                                if st.session_state.get("just_submitted_form", False):
                                    print("DEBUG (Callback): 'just_submitted_form' flag is True. Ignoring empty tool call and resetting flag.")
                                    st.session_state.just_submitted_form = False # 플래그 리셋
                                    # 폼을 띄우지 않고 넘어감
                                else:
                                    # 폼 제출 직후가 아닐 경우, 폼 띄우기 로직 실행
                                    print(f"DEBUG (Callback): Triggering form for {tool_name} (not immediately after form submission).")
                                    if tool_name == "send_email_tool": st.session_state.show_email_form_area = True
                                    elif tool_name == "create_event_tool": st.session_state.show_calendar_form_area = True
                                    st.session_state.rerun_needed = True
                                    raise StopStreamAndRerun()
                                # --- 폼 제출 직후 상태 확인 로직 --- END
                                
                                # 사용자 의도 확인 로직 제거됨

            elif isinstance(message_content, ToolMessage):
                # ToolMessage 처리: 내부 저장 + history용 포맷만 수행
                tool_result_str = str(message_content.content)
                tool_name = message_content.name
                print(f"DEBUG (Callback): Received ToolMessage for {tool_name}. Storing and formatting for history.")

                # 결과 내부 저장
                try:
                    result_data = json.loads(tool_result_str)
                    tool_results.append(result_data)
                except json.JSONDecodeError:
                    tool_results.append(tool_result_str)

                # 결과 포맷팅 (history 저장용 - 기존과 동일)
                formatted_result = ""
                try: 
                    parsed_res = json.loads(tool_result_str)
                    formatted_result = f"```json\n{json.dumps(parsed_res, indent=2, ensure_ascii=False)}\n```"
                except json.JSONDecodeError: 
                    formatted_result = f"```text\n{tool_result_str}\n```"

                # 포맷된 결과를 history 저장용 리스트에 추가
                result_info = f"**결과 ({tool_name}):**\n{formatted_result}"
                formatted_tool_results_for_history.append(result_info)

            return None

        return callback_func, accumulated_text, tool_results, formatted_tool_results_for_history


    async def process_query(query, text_placeholder, timeout_seconds=300):
        """
        사용자 질문을 처리하고 응답을 생성합니다.
        # 폼 제출 후에는 요약된 시스템 메시지를 주입합니다. -> 제거
        """
        try:
            if st.session_state.agent:
                streaming_callback, accumulated_text_obj, final_tool_results, formatted_tool_results_for_history = (
                    get_streaming_callback(text_placeholder)
                )
                response = None 
                final_text = "" 
                
                # # 폼 제출 후 전달될 초기 메시지 구성 -> 제거
                # messages_to_send = [] 
                # if "pending_initial_messages" in st.session_state:
                #     pending_messages = st.session_state.pop("pending_initial_messages") 
                #     try:
                #         messages_to_send = [...]
                #         print(f"DEBUG: Injecting pending messages: ...")
                #     except Exception as msg_e:
                #         print(f"ERROR converting pending messages: {msg_e}")
                #         messages_to_send = []

                # 현재 사용자 쿼리만 HumanMessage로 구성
                messages_to_send = [HumanMessage(content=query)]
                print(f"DEBUG: Final messages being sent to agent: {[m.type for m in messages_to_send]}")

                try:
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                    async with anyio.create_task_group() as tg:
                        # --- 수정: StopStreamAndRerun 예외 처리 블록을 TaskGroup 내부로 이동 --- START
                        try:
                            response = await asyncio.wait_for(
                                astream_graph(
                                    st.session_state.agent,
                                    {"messages": messages_to_send}, # 현재 사용자 입력만 전달
                                    callback=streaming_callback,
                                    config=RunnableConfig(
                                        recursion_limit=200,
                                        thread_id=st.session_state.thread_id, # 새 thread_id 사용됨
                                        max_concurrency=1,
                                    ),
                                ),
                                timeout=timeout_seconds,
                            )
                            await asyncio.sleep(2) # UI 업데이트 후 약간의 지연 복구
                            final_text = "".join(accumulated_text_obj).strip()
                        except StopStreamAndRerun:
                            # 콜백에서 스트림 중단 요청 감지 (TaskGroup 내에서 처리)
                            print("DEBUG (process_query in TG): StopStreamAndRerun caught. Stream stopped early for rerun.")
                            final_text = "".join(accumulated_text_obj).strip()
                            response = {} # 빈 응답으로 설정
                        # --- 수정: StopStreamAndRerun 예외 처리 블록을 TaskGroup 내부로 이동 --- END

                except asyncio.TimeoutError:
                    error_msg = f"⏱️ 요청 시간이 {timeout_seconds}초를 초과했습니다."
                    return {"error": error_msg}, error_msg, [], []
                except Exception as e:
                    # StopStreamAndRerun 외의 다른 예외
                    error_msg = f"처리 중 오류 발생: {str(e)}"
                    return {"error": error_msg}, error_msg, [], []

                print(f"DEBUG: Final agent text output (before history append): '{final_text}'")

                return response, final_text, final_tool_results, formatted_tool_results_for_history
            else:
                return (
                    {"error": "🚫 에이전트가 초기화되지 않았습니다."},
                    "🚫 에이전트가 초기화되지 않았습니다.",
                    [],
                    []
                )
        except Exception as e:
            import traceback
            error_msg = f"❌ 쿼리 처리 중 오류 발생: {str(e)}\n{traceback.format_exc()}"
            return {"error": error_msg}, error_msg, [], []


    async def initialize_session(mcp_config=None):
        """
        MCP 세션과 에이전트를 초기화합니다.

        매개변수:
            mcp_config: MCP 도구 설정 정보(JSON). None인 경우 기본 설정 사용

        반환값:
            bool: 초기화 성공 여부
        """
        try:
            with st.spinner("🔄 MCP 서버에 연결 중..."):
                if mcp_config is None:
                    # 기본 설정 사용
                    mcp_config = {
                        "weather": {
                            "command": "python",
                            "args": ["./mcp_server_local.py"],
                            "transport": "stdio",
                        },
                        "gsuite": {
                            "command": "python",
                            "args": ["./gsuite_mcp_server.py"],
                            "transport": "stdio",
                        },
                        # pplx_search 서버 추가
                        "pplx_search": {
                            "command": "python",
                            "args": ["./pplx_search_mcp_server.py"],
                            "transport": "stdio",
                        },
                    }
                client = MultiServerMCPClient(mcp_config)
                await client.__aenter__()
                tools = client.get_tools()
                st.session_state.tool_count = len(tools)
                st.session_state.mcp_client = client

                model = ChatUpstage(
                    model="solar-pro",
                    temperature=0.0,
                    max_tokens=20000
                )
                # --- 추가: LLM 모델 인스턴스를 세션 상태에 저장 ---
                st.session_state.llm_model = model
                # --- 추가 끝 ---
                
                agent = create_react_agent(
                    model,
                    tools,
                    checkpointer=MemorySaver(),
                    prompt="""You are an intelligent and helpful assistant using tools. Respond in Korean.

                    **Available Tools:** You have tools for:
                    *   Weather: `get_weather`
                    *   Gmail: `list_emails_tool`, `search_emails_tool`, `send_email_tool`, `modify_email_tool`
                    *   Google Calendar: `list_events_tool`, `create_event_tool`
                    *   Web Search: `perplexity_search`

                    **VERY IMPORTANT RULES (Tool Usage):**
                    1. You MUST **ONLY** use the tools listed in 'Available Tools'.
                    2. **NEVER** attempt to use tools that are not listed.
                    3. **Web Search (`perplexity_search`) Usage - STRICT RULE:**
                        *   You **MUST NOT** use the `perplexity_search` tool unless the user's message contains **explicit search keywords** like "검색해줘", "찾아줘", "알아봐줘", "search for", "find information about", etc.
                        *   For **ANY** other type of query, including definitions (like "잘했어가 뭐야?"), explanations, general conversation, or questions answerable from common knowledge, you **MUST respond directly without using any tools**, especially `perplexity_search`.
                        *   Prioritize direct, tool-less responses **unless** an explicit search command is given.
                    4. If the user's request is unrelated to the available tools (following the strict search rule above) or can be answered without tools, respond directly.

                    **CRITICAL RULE for Specific Phrases (Form Trigger):**
                    - If the user's message is EXACTLY "일정 추가" or "일정 추가해" or "add event", the correct first step is to use the `create_event_tool` with empty arguments `{}`. **Do not ask for details first.**
                    - If the user's message is EXACTLY "메일 보내줘" or "이메일 작성" or "send email", the correct first step is to use the `send_email_tool` with empty arguments `{}`. **Do not ask for details first.**
                    - The system will handle prompting for details via a form after these specific calls.

                    **Other Requests:**
                    For any other request (following the specific rules above), identify the correct tool from 'Available Tools' or answer directly if appropriate. Use the provided details if available when calling tools.

                    **Handling Tool Results (ToolMessage):**
                    - Incorporate tool results into your final response clearly and helpfully.
                    """,
                )
                st.session_state.agent = agent
                st.session_state.session_initialized = True
                return True
        except Exception as e:
            st.error(f"❌ 초기화 중 오류 발생: {str(e)}")
            import traceback

            st.error(traceback.format_exc())
            return False




    # --- Google 인증 UI ---
    with st.sidebar.expander("Google 계정 연동", expanded=True):
        if not st.session_state.google_authenticated:
            st.write("Google 계정을 연동하여 Gmail과 캘린더를 사용할 수 있습니다.")
            
            # 1. 세션 상태에 flow 초기화
            if 'flow' not in st.session_state:
                st.session_state.flow = create_oauth_flow(REDIRECT_URI)
            
            # 2. URL에서 인증 코드 확인
            query_params = st.query_params
            if 'code' in query_params:
                try:
                    # 3. flow 객체가 없는 경우 재생성
                    if 'flow' not in st.session_state:
                        st.session_state.flow = create_oauth_flow(REDIRECT_URI)
                    
                    # 4. 토큰 가져오기
                    auth_code = query_params['code']
                    credentials = fetch_token(st.session_state.flow, auth_code)
                    save_credentials(credentials)
                    
                    if initialize_google_services():
                        st.session_state.google_authenticated = True
                        st.query_params.clear()  # URL 파라미터 초기화
                        # --- 수정: 직접 호출 대신 플래그 설정 ---
                        st.session_state.needs_greeting_regeneration = True # 인사말 재생성 필요 플래그 설정
                        # 이전에 추가했던 try-except 블록 제거
                        # --- 수정 끝 ---
                        st.rerun()
                except Exception as e:
                    st.error(f"인증 오류: {str(e)}")
            else: # 인증 코드가 없을 때 버튼 표시
                # 5. 인증 버튼 (st.link_button 사용)
                try:
                    auth_url = get_authorization_url(st.session_state.flow)
                    st.link_button(
                        "Google 계정 연동하기", 
                        auth_url, 
                        type="primary", 
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"인증 URL 생성 중 오류 발생: {str(e)}")
        else:
            st.success("✅ Google 계정이 연동되었습니다.")
            if st.button("연동 해제", use_container_width=True):
                token_path = Path("token.pickle")
                if token_path.exists():
                    token_path.unlink()
                st.session_state.google_authenticated = False
                st.session_state.gmail_service = None
                st.session_state.calendar_service = None
                # 연동 해제 시에는 재생성 플래그 설정 불필요
                st.rerun()

    # --- 관심 분야 입력 UI (수정) --- START
    with st.sidebar.expander("관심 분야 설정", expanded=True):
        # 세션 상태에서 현재 관심 분야 가져오기
        current_interests = st.session_state.get("user_interests", "")

        if not current_interests:
            # 저장된 관심 분야가 없을 경우: 입력 필드 표시
            st.write("관심 분야를 입력해주세요 (쉼표로 구분).")
            interests_input = st.text_input(
                "관심 분야",
                value="", # 초기값은 빈 문자열
                key="interests_input_new", # 키 변경 (상태 전환 시 위젯 재생성 유도)
                label_visibility="collapsed"
            )
            if st.button("관심 분야 저장", key="save_interests_button", use_container_width=True):
                if interests_input:
                    if save_interests(interests_input):
                        st.session_state.user_interests = interests_input # 세션 상태 업데이트 먼저
                        st.success("저장완료! 이제 '관심분야 보고서' 탭에서 최신 정보를 확인할 수 있습니다.")
                        # --- 보고서 즉시 생성 로직 추가 --- START
                        st.session_state.briefing_result = None # 이전 결과 초기화
                        st.session_state.last_briefed_interests = None # 마지막 브리핑 관심사 초기화

                        if st.session_state.session_initialized and st.session_state.mcp_client:
                            search_tool = None
                            try:
                                client = st.session_state.mcp_client
                                tools = client.get_tools()
                                search_tool = next((t for t in tools if t.name in ['pplx_search', 'perplexity_search']), None)
                            except Exception as e:
                                st.error(f"보고서 생성을 위한 검색 도구 확인 중 오류: {e}", icon="⚠️")

                            if search_tool:
                                with st.spinner(f"'{interests_input}' 관련 최신 보고서 생성 중..."): # 스피너 추가
                                    try:
                                        loop = st.session_state.event_loop
                                        search_prompt = f"Summarize the latest developments and key information about: {interests_input}. Provide a concise overview suitable for a briefing."
                                        print(f"DEBUG (Interest Save): Triggering briefing search for: {interests_input}")
                                        result = loop.run_until_complete(search_tool.ainvoke({"query": search_prompt}))
                                        st.session_state.briefing_result = result # 결과 저장
                                        st.session_state.last_briefed_interests = interests_input # 마지막 브리핑 관심사 업데이트
                                        print(f"DEBUG (Interest Save): Briefing search complete for: {interests_input}")
                                    except Exception as e:
                                        st.error(f"관심 분야 보고서 생성 중 오류 발생: {e}", icon="🚨")
                                        st.session_state.briefing_result = f"오류로 인해 보고서 생성에 실패했습니다: {e}"
                            else:
                                st.warning("Perplexity 검색 도구를 찾을 수 없어 보고서를 생성할 수 없습니다.", icon="🤔")
                        else:
                            st.warning("시스템 준비 중이거나 MCP 클라이언트 연결 실패로 보고서를 생성할 수 없습니다.", icon="⏳")
                        # --- 보고서 즉시 생성 로직 추가 --- END
                        st.rerun() # UI 업데이트 및 스피너/메시지 표시 위해 rerun
                    else:
                        # 저장 실패 시 에러 메시지는 save_interests 함수에서 처리
                        pass
                else:
                    st.warning("관심 분야를 입력해주세요.")
        else:
            # 저장된 관심 분야가 있을 경우: 텍스트 및 삭제 버튼 표시
            st.markdown(f"**저장된 관심 분야:**")
            st.write(current_interests)
            if st.button("관심 분야 삭제", key="delete_interests_button", use_container_width=True):
                # 세션 상태 초기화
                st.session_state.user_interests = ""
                # 파일 삭제 시도
                try:
                    if Path(INTERESTS_FILE).exists():
                        Path(INTERESTS_FILE).unlink()
                        st.info("관심 분야가 삭제되었습니다.")
                        # 브리핑 상태 초기화 (삭제 시에도)
                        st.session_state.briefing_result = None
                        st.session_state.last_briefed_interests = None
                    else:
                        st.info("저장된 관심 분야 파일이 이미 없습니다.")
                except Exception as e:
                    st.error(f"관심 분야 파일 삭제 중 오류 발생: {e}")
                    print(f"ERROR deleting interests file: {e}")
                st.rerun() # UI 즉시 업데이트
    # --- 관심 분야 입력 UI (수정) --- END

    # --- 폼 렌더링 함수 정의 ---
    def render_email_form():
        with st.form(key='email_form_area', clear_on_submit=True):
            st.subheader("✉️ 이메일 보내기")
            to = st.text_input("받는 사람", placeholder="example@gmail.com (쉼표로 구분하여 여러 명 지정 가능)")
            subject = st.text_input("제목")
            body = st.text_area("내용", height=150)
            cc = st.text_input("참조 (CC)", placeholder="선택사항")
            bcc = st.text_input("숨은 참조 (BCC)", placeholder="선택사항")
            html_format = st.checkbox("HTML 형식")

            submitted = st.form_submit_button("전송", use_container_width=True)
            if submitted:
                if not to or not subject or not body:
                    st.error("받는 사람, 제목, 내용은 필수 입력 항목입니다.")
                else:
                    with st.spinner("이메일 전송 중..."):
                        try:
                            # from gmail_utils import send_email # 상단에서 이미 import 함
                            to_list = [email.strip() for email in to.split(',') if email.strip()]
                            cc_list = [email.strip() for email in cc.split(',') if email.strip()] if cc else None
                            bcc_list = [email.strip() for email in bcc.split(',') if email.strip()] if bcc else None

                            sent_message = send_email(
                                st.session_state.gmail_service,
                                to_list,
                                subject,
                                body,
                                cc=cc_list,
                                bcc=bcc_list,
                                html=html_format
                            )

                            if sent_message:
                                success_msg = f"이메일이 성공적으로 전송되었습니다. (ID: {sent_message['id']})"
                                st.success(success_msg)

                                # 2. 새 thread_id 생성 (유지)
                                st.session_state.thread_id = random_uuid()
                                print(f"DEBUG: Email form submitted. New thread_id: {st.session_state.thread_id}. Context reset.")

                                # 3. 사용자 표시용 히스토리 업데이트 (유지)
                                st.session_state.history.append({"role": "assistant", "content": f"✅ {success_msg} 다른 도움이 필요하시면 말씀해주세요."})
                                
                                # 4. 폼 숨기기 및 새로고침 (유지)
                                st.session_state.show_email_form_area = False
                                st.rerun()
                            else:
                                error_msg = "이메일 전송에 실패했습니다."
                                st.error(error_msg)
                                # 오류 메시지를 히스토리에 추가
                                st.session_state.history.append({"role": "assistant", "content": f"❌ {error_msg}"})
                        except Exception as e:
                            error_msg = f"이메일 전송 중 오류 발생: {str(e)}"
                            st.error(error_msg)
                            # 오류 메시지를 히스토리에 추가
                            st.session_state.history.append({"role": "assistant", "content": f"❌ {error_msg}"})

    def render_calendar_form():
        with st.form(key='calendar_form_area', clear_on_submit=True):
            st.subheader("📝 일정 추가하기")
            summary = st.text_input("일정 제목")

            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("시작 날짜")
                start_time = st.time_input("시작 시간")
            with col2:
                end_date = st.date_input("종료 날짜")
                end_time = st.time_input("종료 시간")

            location = st.text_input("장소", placeholder="선택사항")
            description = st.text_area("설명", placeholder="선택사항", height=100)
            attendees = st.text_input("참석자", placeholder="이메일 주소 (쉼표로 구분하여 여러 명 지정 가능)")

            submitted = st.form_submit_button("일정 추가", use_container_width=True)
            if submitted:
                if not summary:
                    st.error("일정 제목은 필수 입력 항목입니다.")
                else:
                    with st.spinner("일정 추가 중..."):
                        try:
                            # from calendar_utils import create_calendar_event # 상단에서 이미 import 함
                            # from datetime import datetime # 상단에서 이미 import 함

                            start_datetime = datetime.combine(start_date, start_time)
                            end_datetime = datetime.combine(end_date, end_time)
                            attendee_list = [email.strip() for email in attendees.split(',') if email.strip()] if attendees else None

                            event = create_calendar_event(
                                st.session_state.calendar_service,
                                summary=summary,
                                location=location,
                                description=description,
                                start_time=start_datetime,
                                end_time=end_datetime,
                                attendees=attendee_list
                            )

                            if event:
                                success_msg = f"일정이 성공적으로 추가되었습니다. (ID: {event['id']})"
                                st.success(success_msg)

                                # 2. 새 thread_id 생성 (유지)
                                st.session_state.thread_id = random_uuid()
                                print(f"DEBUG: Calendar form submitted. New thread_id: {st.session_state.thread_id}. Context reset.")

                                # 3. 사용자 표시용 히스토리 업데이트 (유지)
                                st.session_state.history.append({"role": "assistant", "content": f"✅ {success_msg} 다른 도움이 필요하시면 말씀해주세요."})
                                
                                # 4. 폼 숨기기 및 새로고침 (유지)
                                st.session_state.show_calendar_form_area = False
                                st.rerun()
                            else:
                                error_msg = "일정 추가에 실패했습니다."
                                st.error(error_msg)
                                # 오류 메시지를 히스토리에 추가
                                st.session_state.history.append({"role": "assistant", "content": f"❌ {error_msg}"})
                        except Exception as e:
                            error_msg = f"일정 추가 중 오류 발생: {str(e)}"
                            st.error(error_msg)
                            # 오류 메시지를 히스토리에 추가
                            st.session_state.history.append({"role": "assistant", "content": f"❌ {error_msg}"})

    # --- 기본 세션 초기화 (초기화되지 않은 경우) ---
    if not st.session_state.session_initialized:
        # with st.spinner("🦋 비서 '나비'를 깨우고 있어요... (초기 설정 중)"): # 스피너 제거
        success = False
        try:
             success = st.session_state.event_loop.run_until_complete(initialize_session())
        except Exception as initial_init_e:
             print(f"Critical error during initial session initialization: {initial_init_e}")
             st.error(f"❌ 시스템 초기화 중 심각한 오류 발생: {initial_init_e}. 페이지를 새로고침하거나 관리자에게 문의하세요.")
             st.stop() # 치명적 오류 시 중단

        if success:
            # 초기 인사말 재생성 시도
            if st.session_state.initial_greeting is None:
                 try:
                     greeting = st.session_state.event_loop.run_until_complete(
                         run_initial_tools_and_summarize()
                     )
                     st.session_state.initial_greeting = greeting
                     # 히스토리 맨 앞에 새 인사말 삽입
                     if not st.session_state.history:
                         st.session_state.history.insert(0, {"role": "assistant", "content": greeting})
                     # 히스토리 업데이트 로직 추가
                     if st.session_state.history:
                         st.session_state.history[0]["content"] = greeting
                 except Exception as e:
                     print(f"Error running initial summary function: {e}")
                     # 오류 발생 시 대체 메시지로 history 업데이트 또는 삽입
                     error_greeting = "안녕하세요! 비서 나비입니다. 정보를 다시 불러오는 중 문제가 발생했어요." 
                     st.session_state.initial_greeting = error_greeting
                     if st.session_state.history:
                          st.session_state.history[0]["content"] = error_greeting
                # st.stop() # 초기화 성공 후에는 중단하지 않음
            else:
                # initialize_session 내부에서 이미 오류 메시지를 표시했을 것이므로 추가 메시지는 생략
                st.error("❌ 초기화에 실패했습니다. 페이지를 새로고침하거나 설정을 확인해주세요.")
                st.stop() # 초기화 실패 시 중단


    # --- 추가: 인증 후 인사말 재생성 플래그 확인 및 실행 ---
    if st.session_state.get("needs_greeting_regeneration", False):
        print("DEBUG: Regenerating greeting based on flag (likely after Google Auth).")
        try:
            new_greeting = st.session_state.event_loop.run_until_complete(
                run_initial_tools_and_summarize()
            )
            st.session_state.initial_greeting = new_greeting
            # 히스토리 맨 앞 업데이트 또는 삽입
            if st.session_state.history: # history가 있으면 첫 메시지 업데이트
                st.session_state.history[0]["content"] = new_greeting
            else: # history가 비었으면 맨 앞에 삽입
                st.session_state.history.insert(0, {"role": "assistant", "content": new_greeting})
            # 초기화 성공 후 딱 한 번만 초기 인사말 생성 시도
            st.session_state.needs_greeting_regeneration = False # 플래그 리셋
        except Exception as e_regen:
            print(f"Error regenerating greeting based on flag: {e_regen}")
            # 오류 발생 시 대체 메시지로 history 업데이트 또는 삽입
            error_greeting = "안녕하세요! 비서 나비입니다. 정보를 다시 불러오는 중 문제가 발생했어요." 
            st.session_state.initial_greeting = error_greeting
            if st.session_state.history:
                st.session_state.history[0]["content"] = error_greeting
            st.session_state.needs_greeting_regeneration = False # 오류 시에도 일단 플래그 리셋
        st.rerun() # 오류 메시지라도 표시


    # --- 추가: 보류 중인 어시스턴트 메시지 히스토리에 추가 --- START
    if "pending_assistant_entry" in st.session_state and st.session_state.pending_assistant_entry:
        entry_to_add = st.session_state.pop("pending_assistant_entry")
        # 마지막 메시지가 이미 assistant 메시지인지 확인 후 추가 또는 업데이트
        if st.session_state.history and st.session_state.history[-1]["role"] == "assistant":
             st.session_state.history[-1] = entry_to_add # 마지막 항목 업데이트
        else:
             st.session_state.history.append(entry_to_add) # 새 항목 추가
        print("DEBUG: Added pending assistant entry to history.")
        # 이 변경 사항을 즉시 반영하기 위해 rerun이 필요할 수 있지만,
        # 바로 뒤에 print_message()가 오므로 일단 생략해 봄.
    # --- 추가: 보류 중인 어시스턴트 메시지 히스토리에 추가 --- END

    # --- 대화 기록 먼저 출력 --- START
    print_message()
    # --- 대화 기록 먼저 출력 --- END

    # --- 메인 스크립트 플로우: 조건부 rerun 처리 (입력창 앞에 위치) --- START
    if st.session_state.get("rerun_needed", False):
        print("DEBUG (Main Loop Before Input): Rerun needed flag detected. Executing st.rerun().")
        st.session_state.rerun_needed = False # 플래그 리셋 후 rerun
        # rerun 전에 폼 렌더링은 불필요하므로 여기서 바로 rerun
        st.rerun()
    # --- 메인 스크립트 플로우: 조건부 rerun 처리 --- END

    # --- 동적 폼 렌더링 (입력창 앞에 위치) --- START
    if st.session_state.get("show_email_form_area", False):
        render_email_form()

    if st.session_state.get("show_calendar_form_area", False):
        render_calendar_form()
    # --- 동적 폼 렌더링 --- END

    # --- 사용입력 및 처리 (항상 페이지 하단에 위치하도록 맨 마지막에 배치) --- START
    if user_query := st.chat_input("💬 질문을 입력하세요"):
        if st.session_state.session_initialized:
            # 사용자 메시지 기록 추가 및 즉시 표시
            st.session_state.history.append({"role": "user", "content": user_query})
            st.chat_message("user").markdown(user_query)

            # 어시스턴트 응답 스트리밍 준비 및 표시
            with st.chat_message("assistant"):
                text_placeholder = st.empty() # 스트리밍용 플레이스홀더
                
                # 폼 표시 상태 초기화 (새 질문 시작 시 - 입력 처리 시작 시점에 수행)
                st.session_state.show_email_form_area = False
                st.session_state.show_calendar_form_area = False

                # 비동기 작업 실행
                resp, final_text, final_tool_results, formatted_tool_results_for_history = (
                    st.session_state.event_loop.run_until_complete(
                        process_query(user_query, text_placeholder) # 플레이스홀더 전달
                    )
                )

                # 응답 완료 후, 어시스턴트 메시지를 임시 변수에 저장
                if "error" in resp:
                    # 에러 발생 시에도 임시 변수에 저장 (오류 메시지로)
                    st.session_state.pending_assistant_entry = {"role": "assistant", "content": f"❌ {resp['error']}"}
                else:
                    # 성공 응답을 임시 변수에 저장
                    history_entry = {"role": "assistant", "content": final_text}
                    if formatted_tool_results_for_history:
                        history_entry["tool_output"] = "\n---\n".join(formatted_tool_results_for_history)
                    st.session_state.pending_assistant_entry = history_entry
                
            # 여기서 바로 history에 추가하지 않음

            # UI 갱신 및 다음 단계(pending entry 처리)를 위해 rerun 호출
            st.rerun()

        else:
            st.warning("⏳ 시스템이 아직 초기화 중입니다. 잠시 후 다시 시도해주세요.")
    # --- 사용입력 및 처리 --- END

# ==========================
#      탭 2: 정보 검색
# ==========================
with tab2:
    st.title("🔍 관심분야 보고서")

    # --- 관심 분야 브리핑 --- START
    interests = st.session_state.get("user_interests", "")
    briefing_result = st.session_state.get("briefing_result")
    last_briefed = st.session_state.get("last_briefed_interests")

    # 관심 분야가 있고, (결과가 없거나 or 마지막 브리핑된 관심사와 현재 관심사가 다를 때) 검색 수행 -> 조건 수정: 관심 분야가 있으면 항상 검색 수행
    if interests: # <<< 수정된 조건: 관심 분야가 존재하면 항상 브리핑 생성 시도
        # 브리핑 실행 로직은 컨테이너 밖에 위치 (스피너 표시 때문)
        if briefing_result is None: # 아직 브리핑 결과가 없으면 검색 시도
            if not st.session_state.session_initialized or not st.session_state.mcp_client:
                st.warning("시스템이 아직 준비되지 않아 관심 분야 브리핑을 생성할 수 없습니다.")
            else:
                search_tool = None
                try:
                    client = st.session_state.mcp_client
                    tools = client.get_tools()
                    search_tool = next((t for t in tools if t.name in ['pplx_search', 'perplexity_search']), None)
                except Exception as e:
                    st.error(f"브리핑을 위한 검색 도구를 찾는 중 오류 발생: {e}")

                if not search_tool:
                    st.error("Perplexity 검색 도구를 찾을 수 없습니다. MCP 설정을 확인해주세요.")
                else:
                    with st.spinner(f"'{interests}' 관련 보고서 작성중..."):
                        try:
                            loop = st.session_state.event_loop
                            search_prompt = f"Summarize the latest developments and key information about: {interests}. Provide a concise overview suitable for a briefing."
                            print(f"DEBUG: Running briefing search for: {interests}")
                            result = loop.run_until_complete(search_tool.ainvoke({"query": search_prompt}))
                            st.session_state.briefing_result = result
                            briefing_result = result
                            print(f"DEBUG: Briefing search complete for: {interests}")
                        except Exception as e:
                            st.error(f"관심 분야 브리핑 생성 중 오류 발생: {e}")
                            st.session_state.briefing_result = f"오류로 인해 브리핑 생성에 실패했습니다: {e}"
                            briefing_result = st.session_state.briefing_result

    # 브리핑 결과 표시 컨테이너 또는 안내 메시지
    if interests and briefing_result:
        with st.container(border=True):
            st.subheader(f"✨ '{interests}' 관심 분야 브리핑")
            st.markdown(briefing_result)
        st.divider() # 브리핑과 직접 검색 사이 구분선
    elif not interests: # 관심 분야가 없을 때 안내 메시지 표시
        st.info("💡 사이드바의 '관심 분야 설정'에서 관심사를 등록하고 맞춤 보고서를 받아보세요!")
        st.divider() # 안내 메시지와 직접 검색 사이 구분선
    # --- 관심 분야 브리핑 --- END

    # --- 사용자 직접 검색 --- START
    with st.container(border=True):
        st.subheader("직접 검색하기") # 섹션 제목 추가
        search_query = st.text_input("검색어 입력", key="search_query_input", label_visibility="collapsed") # 라벨 숨김

        if st.button("검색 실행", key="search_button"):
            if not search_query:
                st.warning("검색어를 입력해주세요.")
            elif not st.session_state.session_initialized or not st.session_state.mcp_client:
                st.error("시스템이 아직 준비되지 않았습니다. 잠시 후 다시 시도해주세요.")
            else:
                search_tool = None
                try:
                    client = st.session_state.mcp_client
                    tools = client.get_tools()
                    search_tool = next((t for t in tools if t.name == 'perplexity_search'), None)
                except Exception as e:
                    st.error(f"검색 도구를 찾는 중 오류 발생: {e}")

                if not search_tool:
                    st.error("Perplexity 검색 도구를 찾을 수 없습니다. MCP 설정을 확인해주세요.")
                else:
                    with st.spinner("Perplexity AI에 문의 중..."):
                        try:
                            loop = st.session_state.event_loop
                            search_result = loop.run_until_complete(search_tool.ainvoke({"query": search_query}))
                            
                            # 검색 결과 표시 (컨테이너 내부)
                            st.markdown("--- *검색 결과* ---") # 결과 구분선 추가
                            st.markdown(search_result)
                        except Exception as e:
                            st.error(f"검색 실행 중 오류 발생: {e}")
    # --- 사용자 직접 검색 --- END
