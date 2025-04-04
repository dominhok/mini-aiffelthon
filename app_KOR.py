import streamlit as st
import asyncio
import nest_asyncio
import json
import anyio
import os
from pathlib import Path

# nest_asyncio 적용: 이미 실행 중인 이벤트 루프 내에서 중첩 호출 허용
nest_asyncio.apply()

# 전역 이벤트 루프 생성 및 재사용
if "event_loop" not in st.session_state:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    st.session_state.event_loop = loop

# anyio 백엔드 설정
os.environ["ANYIO_BACKEND"] = "asyncio"

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_teddynote.messages import astream_graph, random_uuid
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.messages.tool import ToolMessage
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

# 사이드바 최상단에 저자 정보 추가 (다른 사이드바 요소보다 먼저 배치)
st.sidebar.markdown("### 🦋 나만의 비서: 나비")
st.sidebar.divider()  # 구분선 추가

# 기존 페이지 타이틀 및 설명
# 웹 페이지의 타이틀과 설명이다.
st.title("🦋 나만의 비서: 나비")
st.markdown("✨ **나비, 당신의 하루를 더 가볍게 만들어줄 스마트 비서!** ✨")

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

if "thread_id" not in st.session_state:
    st.session_state.thread_id = random_uuid()

### Google 인증 관련 상수
REDIRECT_URI = "http://localhost:8501/callback"

# --- 사용자 정의 예외 --- START
class StopStreamAndRerun(Exception):
    """콜백에서 스트림 중단 및 rerun 필요 신호를 보내기 위한 예외"""
    pass
# --- 사용자 정의 예외 --- END

# --- 함수 정의 부분 ---

def print_message():
    """
    채팅 기록을 화면에 출력합니다.

    사용자와 어시스턴트의 메시지를 구분하여 화면에 표시하고,
    도구 호출 정보는 확장 가능한 패널로 표시합니다.
    """
    # 전체 메시지 기록을 순회하며 표시
    for message in st.session_state.history:
        if message["role"] == "user":
            st.chat_message("user").markdown(message["content"])
        elif message["role"] == "assistant":
            st.chat_message("assistant").markdown(message["content"])
            # 도구 결과가 저장되어 있으면 확장 패널로 표시
            if "tool_output" in message and message["tool_output"]:
                with st.expander("🔧 도구 실행 결과", expanded=False):
                    st.markdown(message["tool_output"])
        elif message["role"] == "assistant_tool":
            # 이 형식은 더 이상 사용되지 않을 가능성이 높음
            with st.expander("🔧 도구 호출 정보 (구 버전)", expanded=False):
                st.markdown(message["content"])
    
    # 마지막 메시지 특별 처리 로직 제거
    # if st.session_state.history:
    #     last_message = st.session_state.history[-1]
    #     if last_message["role"] != "assistant":
    #         ...


def get_streaming_callback(text_placeholder, tool_placeholder):
    accumulated_text = []
    expander_content_lines = [] # 현재 턴의 확장 패널 내용 관리
    tool_results = []
    formatted_tool_results_for_history = [] # 히스토리 저장용

    def callback_func(message: dict):
        nonlocal accumulated_text, expander_content_lines, tool_results, formatted_tool_results_for_history
        message_content = message.get("content", None)
        update_expander = False # 확장 패널 업데이트 플래그 복원

        if isinstance(message_content, AIMessageChunk):
            # 에이전트 텍스트 처리
            if hasattr(message_content, "content") and isinstance(message_content.content, str):
                 accumulated_text.append(message_content.content)
                 complete_response = "".join(accumulated_text)
                 text_placeholder.markdown(complete_response) # 메인 채팅창 업데이트

            # 도구 호출 청크 처리
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
                            # if user_intent_confirmed:
                            #    ...

        elif isinstance(message_content, ToolMessage):
            # ToolMessage 처리: 내부 저장 + history용 포맷 + expander 즉시 업데이트
            tool_result_str = str(message_content.content)
            tool_name = message_content.name
            print(f"DEBUG (Callback): Received ToolMessage for {tool_name}. Storing, formatting, AND updating expander.")

            # 결과 내부 저장
            try:
                result_data = json.loads(tool_result_str)
                tool_results.append(result_data)
            except json.JSONDecodeError:
                tool_results.append(tool_result_str)

            # 결과 포맷팅 (history 저장용) - 모든 도구 결과 원본 그대로 표시
            formatted_result = ""
            try: # JSON 시도
                parsed_res = json.loads(tool_result_str)
                formatted_result = f"```json\n{json.dumps(parsed_res, indent=2, ensure_ascii=False)}\n```"
            except json.JSONDecodeError: # 텍스트 처리
                # 모든 텍스트 응답을 원본 그대로 표시 (특별 처리 없음)
                formatted_result = f"```text\n{tool_result_str}\n```"

            # 포맷된 결과를 두 리스트 모두에 추가
            result_info = f"**결과 ({tool_name}):**\n{formatted_result}"
            expander_content_lines.append(result_info) # 현재 턴 expander용
            formatted_tool_results_for_history.append(result_info) # 히스토리 저장용

            update_expander = True # 확장 패널 업데이트 필요

        # 확장 패널 내용 즉시 업데이트 로직 복원
        if update_expander and expander_content_lines:
            with tool_placeholder.expander("🔧 도구 실행 결과", expanded=False):
                st.markdown("\n---\n".join(expander_content_lines))

        return None

    return callback_func, accumulated_text, tool_results, formatted_tool_results_for_history


async def process_query(query, text_placeholder, tool_placeholder, timeout_seconds=300):
    """
    사용자 질문을 처리하고 응답을 생성합니다.
    """
    try:
        if st.session_state.agent:
            streaming_callback, accumulated_text_obj, final_tool_results, formatted_tool_results_for_history = (
                get_streaming_callback(text_placeholder, tool_placeholder)
            )
            response = None # 응답 변수 초기화
            final_text = "" # 최종 텍스트 초기화
            try:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                async with anyio.create_task_group() as tg:
                    response = await asyncio.wait_for(
                        astream_graph(
                            st.session_state.agent,
                            {"messages": [HumanMessage(content=query)]},
                            callback=streaming_callback,
                            config=RunnableConfig(
                                recursion_limit=200,
                                thread_id=st.session_state.thread_id,
                                max_concurrency=1,
                            ),
                        ),
                        timeout=timeout_seconds,
                    )

                await asyncio.sleep(2)
                final_text = "".join(accumulated_text_obj).strip()

            except StopStreamAndRerun:
                # 콜백에서 스트림 중단 요청 감지
                print("DEBUG (process_query): StopStreamAndRerun caught. Stream stopped early for rerun.")
                # final_text는 콜백에서 예외 발생 전까지 누적된 내용이 될 수 있음
                final_text = "".join(accumulated_text_obj).strip() 
                # 응답 객체는 None 또는 부분적인 상태일 수 있음, 오류 방지 위해 빈 dict 설정
                response = {} 

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
            
            agent = create_react_agent(
                model,
                tools,
                checkpointer=MemorySaver(),
                prompt="""You are an intelligent and helpful assistant using tools. Respond in Korean.

                **Available Tools:** You have tools for weather (`get_weather`), Gmail (`list_emails_tool`, `search_emails_tool`, `send_email_tool`, `modify_email_tool`), and Google Calendar (`list_events_tool`, `create_event_tool`).

                **CRITICAL RULE for Email/Calendar:**
                If the user asks to send an email OR create a calendar event:
                1.  You MUST attempt to call the corresponding tool (`send_email_tool` or `create_event_tool`) IMMEDIATELY in your first action.
                2.  Call the tool even if you have no details (use empty arguments: {}).
                3.  DO NOT ask the user for details like recipient, subject, time, etc., in the chat for these requests. The system will handle missing information.

                For any other request (listing emails, weather, general chat), identify the correct tool or answer directly if appropriate.

                **Handling Tool Results (ToolMessage):**
                - If the tool returns data (like email lists, weather info, success/error messages), incorporate this information into your final response to the user. Be clear and helpful.
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
                    st.rerun()
            except Exception as e:
                st.error(f"인증 오류: {str(e)}")
        
        # 5. 인증 버튼
        if st.button("Google 계정 연동하기", type="primary", use_container_width=True):
            auth_url = get_authorization_url(st.session_state.flow)
            st.markdown(
                f'<a href="{auth_url}" target="_self">인증 진행하기</a>',
                unsafe_allow_html=True
            )
    else:
        st.success("✅ Google 계정이 연동되었습니다.")
        if st.button("연동 해제", use_container_width=True):
            token_path = Path("token.pickle")
            if token_path.exists():
                token_path.unlink()
            st.session_state.google_authenticated = False
            st.session_state.gmail_service = None
            st.session_state.calendar_service = None
            st.rerun()


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
                        from gmail_utils import send_email
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
                            st.session_state.history.append({"role": "assistant", "content": f"✅ {success_msg}"})
                            st.session_state.show_email_form_area = False # 성공 시 폼 숨김
                            st.session_state.just_submitted_form = True # 폼 제출 성공 플래그 설정
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
            # 폼 제출 후 rerun이 필요할 수 있음 (상태 변경 반영 위해) - 제거
            # st.rerun()

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
                        from calendar_utils import create_calendar_event
                        from datetime import datetime

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
                            st.session_state.history.append({"role": "assistant", "content": f"✅ {success_msg}"})
                            st.session_state.show_calendar_form_area = False # 성공 시 폼 숨김
                            st.session_state.just_submitted_form = True # 폼 제출 성공 플래그 설정
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
            # 폼 제출 후 rerun이 필요할 수 있음 (상태 변경 반영 위해) - 제거
            # st.rerun()

# --- 사이드바 UI: MCP 도구 추가 인터페이스로 변경 ---
with st.sidebar.expander("MCP 도구 추가", expanded=False):
    default_config = """{
  "weather": {
    "command": "python",
    "args": ["./mcp_server_local.py"],
    "transport": "stdio"
  },
  "gsuite": {
    "command": "python",
    "args": ["./gsuite_mcp_server.py"],
    "transport": "stdio"
  }
}"""
    # pending config가 없으면 기존 mcp_config_text 기반으로 생성
    if "pending_mcp_config" not in st.session_state:
        try:
            st.session_state.pending_mcp_config = json.loads(
                st.session_state.get("mcp_config_text", default_config)
            )
        except Exception as e:
            st.error(f"초기 pending config 설정 실패: {e}")

    # 개별 도구 추가를 위한 UI
    st.subheader("개별 도구 추가")
    st.markdown(
        """
    **하나의 도구**를 JSON 형식으로 입력하세요:
    
    ```json
    {
      "도구이름": {
        "command": "실행 명령어",
        "args": ["인자1", "인자2", ...],
        "transport": "stdio"
      }
    }
    ```    
    ⚠️ **중요**: JSON을 반드시 중괄호(`{}`)로 감싸야 합니다.
    """
    )

    # 보다 명확한 예시 제공
    example_json = {
        "github": {
            "command": "npx",
            "args": [
                "-y",
                "@smithery/cli@latest",
                "run",
                "@smithery-ai/github",
                "--config",
                '{"githubPersonalAccessToken":"your_token_here"}',
            ],
            "transport": "stdio",
        }
    }

    default_text = json.dumps(example_json, indent=2, ensure_ascii=False)

    new_tool_json = st.text_area(
        "도구 JSON",
        default_text,
        height=250,
    )

    # 추가하기 버튼
    if st.button(
        "도구 추가",
        type="primary",
        key="add_tool_button",
        use_container_width=True,
    ):
        try:
            # 입력값 검증
            if not new_tool_json.strip().startswith(
                "{"
            ) or not new_tool_json.strip().endswith("}"):
                st.error("JSON은 중괄호({})로 시작하고 끝나야 합니다.")
                st.markdown('올바른 형식: `{ "도구이름": { ... } }`')
            else:
                # JSON 파싱
                parsed_tool = json.loads(new_tool_json)

                # mcpServers 형식인지 확인하고 처리
                if "mcpServers" in parsed_tool:
                    # mcpServers 안의 내용을 최상위로 이동
                    parsed_tool = parsed_tool["mcpServers"]
                    st.info("'mcpServers' 형식이 감지되었습니다. 자동으로 변환합니다.")

                # 입력된 도구 수 확인
                if len(parsed_tool) == 0:
                    st.error("최소 하나 이상의 도구를 입력해주세요.")
                else:
                    # 모든 도구에 대해 처리
                    success_tools = []
                    for tool_name, tool_config in parsed_tool.items():
                        # URL 필드 확인 및 transport 설정
                        if "url" in tool_config:
                            # URL이 있는 경우 transport를 "sse"로 설정
                            tool_config["transport"] = "sse"
                            st.info(
                                f"'{tool_name}' 도구에 URL이 감지되어 transport를 'sse'로 설정했습니다."
                            )
                        elif "transport" not in tool_config:
                            # URL이 없고 transport도 없는 경우 기본값 "stdio" 설정
                            tool_config["transport"] = "stdio"

                        # 필수 필드 확인
                        if "command" not in tool_config and "url" not in tool_config:
                            st.error(
                                f"'{tool_name}' 도구 설정에는 'command' 또는 'url' 필드가 필요합니다."
                            )
                        elif "command" in tool_config and "args" not in tool_config:
                            st.error(
                                f"'{tool_name}' 도구 설정에는 'args' 필드가 필요합니다."
                            )
                        elif "command" in tool_config and not isinstance(
                            tool_config["args"], list
                        ):
                            st.error(
                                f"'{tool_name}' 도구의 'args' 필드는 반드시 배열([]) 형식이어야 합니다."
                            )
                        else:
                            # pending_mcp_config에 도구 추가
                            st.session_state.pending_mcp_config[tool_name] = tool_config
                            success_tools.append(tool_name)

                    # 성공 메시지
                    if success_tools:
                        if len(success_tools) == 1:
                            st.success(
                                f"{success_tools[0]} 도구가 추가되었습니다. 적용하려면 '적용하기' 버튼을 눌러주세요."
                            )
                        else:
                            tool_names = ", ".join(success_tools)
                            st.success(
                                f"총 {len(success_tools)}개 도구({tool_names})가 추가되었습니다. 적용하려면 '적용하기' 버튼을 눌러주세요."
                            )
        except json.JSONDecodeError as e:
            st.error(f"JSON 파싱 에러: {e}")
            st.markdown(
                f"""
            **수정 방법**:
            1. JSON 형식이 올바른지 확인하세요.
            2. 모든 키는 큰따옴표(")로 감싸야 합니다.
            3. 문자열 값도 큰따옴표(")로 감싸야 합니다.
            4. 문자열 내에서 큰따옴표를 사용할 경우 이스케이프(\\")해야 합니다.
            """
            )
        except Exception as e:
            st.error(f"오류 발생: {e}")

    # 구분선 추가
    st.divider()

    # 현재 설정된 도구 설정 표시 (읽기 전용)
    st.subheader("현재 도구 설정 (읽기 전용)")
    st.code(
        json.dumps(st.session_state.pending_mcp_config, indent=2, ensure_ascii=False)
    )

# --- 등록된 도구 목록 표시 및 삭제 버튼 추가 ---
with st.sidebar.expander("등록된 도구 목록", expanded=True):
    try:
        pending_config = st.session_state.pending_mcp_config
    except Exception as e:
        st.error("유효한 MCP 도구 설정이 아닙니다.")
    else:
        # pending config의 키(도구 이름) 목록을 순회하며 표시
        for tool_name in list(pending_config.keys()):
            col1, col2 = st.columns([8, 2])
            col1.markdown(f"- **{tool_name}**")
            if col2.button("삭제", key=f"delete_{tool_name}"):
                # pending config에서 해당 도구 삭제 (즉시 적용되지는 않음)
                del st.session_state.pending_mcp_config[tool_name]
                st.success(
                    f"{tool_name} 도구가 삭제되었습니다. 적용하려면 '적용하기' 버튼을 눌러주세요."
                )

with st.sidebar:

    # 적용하기 버튼: pending config를 실제 설정에 반영하고 세션 재초기화
    if st.button(
        "도구설정 적용하기",
        key="apply_button",
        type="primary",
        use_container_width=True,
    ):
        # 적용 중 메시지 표시
        apply_status = st.empty()
        with apply_status.container():
            st.warning("🔄 변경사항을 적용하고 있습니다. 잠시만 기다려주세요...")
            progress_bar = st.progress(0)

            # 설정 저장
            st.session_state.mcp_config_text = json.dumps(
                st.session_state.pending_mcp_config, indent=2, ensure_ascii=False
            )

            # 세션 초기화 준비
            st.session_state.session_initialized = False
            st.session_state.agent = None
            st.session_state.mcp_client = None

            # 진행 상태 업데이트
            progress_bar.progress(30)

            # 초기화 실행
            success = st.session_state.event_loop.run_until_complete(
                initialize_session(st.session_state.pending_mcp_config)
            )

            # 진행 상태 업데이트
            progress_bar.progress(100)

            if success:
                st.success("✅ 새로운 MCP 도구 설정이 적용되었습니다.")
            else:
                st.error("❌ 새로운 MCP 도구 설정 적용에 실패하였습니다.")

        # 페이지 새로고침
        st.rerun()


# --- 기본 세션 초기화 (초기화되지 않은 경우) ---
if not st.session_state.session_initialized:
    st.info("🔄 MCP 서버와 에이전트를 초기화합니다. 잠시만 기다려주세요...")
    success = st.session_state.event_loop.run_until_complete(initialize_session())
    if success:
        st.success(
            f"✅ 초기화 완료! {st.session_state.tool_count}개의 도구가 로드되었습니다."
        )
    else:
        st.error("❌ 초기화에 실패했습니다. 페이지를 새로고침해 주세요.")


# Google 서비스 초기화 (인증된 경우)
if not st.session_state.google_authenticated and is_authenticated():
    initialize_google_services()

# --- 대화 기록 출력 ---
print_message()

# --- 사용자 입력 및 처리 ---
user_query = st.chat_input("💬 질문을 입력하세요")
if user_query:
    if st.session_state.session_initialized:
        st.chat_message("user").markdown(user_query)
        # 사용자 메시지를 받자마자 히스토리에 추가
        st.session_state.history.append({"role": "user", "content": user_query})

        with st.chat_message("assistant"):
            tool_placeholder = st.empty()
            text_placeholder = st.empty()
            resp, final_text, final_tool_results, formatted_tool_results_for_history = (
                st.session_state.event_loop.run_until_complete(
                    process_query(user_query, text_placeholder, tool_placeholder)
                )
            )
        if "error" in resp:
            st.error(resp["error"])
        else:
            # 에이전트의 최종 응답 및 포맷된 도구 결과를 히스토리에 추가
            if final_text or formatted_tool_results_for_history: # 텍스트 또는 도구 결과가 있으면 기록
                history_entry = {"role": "assistant", "content": final_text}
                if formatted_tool_results_for_history:
                    # 도구 결과 내용을 개행으로 합쳐서 저장
                    history_entry["tool_output"] = "\n---\n".join(formatted_tool_results_for_history)
                # rerun 플래그가 False일 때만 최종 응답 기록 (폼 표시 시 불완전 응답 방지)
                if not st.session_state.get("rerun_needed", False):
                     st.session_state.history.append(history_entry)
    else:
        st.warning("⏳ 시스템이 아직 초기화 중입니다. 잠시 후 다시 시도해주세요.")

# --- 메인 스크립트 플로우: 조건부 rerun 처리 --- START
if st.session_state.get("rerun_needed", False):
    print("DEBUG (Main Loop): Rerun needed flag detected. Executing st.rerun().")
    st.session_state.rerun_needed = False # 플래그 리셋
    st.rerun()
# --- 메인 스크립트 플로우: 조건부 rerun 처리 --- END

# --- 동적 폼 렌더링 --- (스크립트 하단에 추가)
if st.session_state.get("show_email_form_area", False):
    render_email_form()

if st.session_state.get("show_calendar_form_area", False):
    render_calendar_form()

# --- 사이드바: 시스템 정보 표시 ---
with st.sidebar:
    st.subheader("🔧 시스템 정보")
    st.write(f"🛠️ MCP 도구 수: {st.session_state.get('tool_count', '초기화 중...')}")
    st.write("🧠 모델: Solar Pro")

    # 구분선 추가 (시각적 분리)
    st.divider()

    # 사이드바 최하단에 대화 초기화 버튼 추가
    if st.button("🔄 대화 초기화", use_container_width=True, type="primary"):
        # thread_id 초기화
        st.session_state.thread_id = random_uuid()

        # 대화 히스토리 초기화
        st.session_state.history = []

        # 알림 메시지
        st.success("✅ 대화가 초기화되었습니다.")

        # 페이지 새로고침
        st.rerun()
