import streamlit as st
import asyncio
import nest_asyncio
import json
import anyio
import os

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
from gmail_utils import format_email_for_display
from calendar_utils import format_event_for_display

# 환경 변수 로드 (.env 파일에서 API 키 등의 설정을 가져옴)
load_dotenv(override=True)

# 페이지 설정: 제목, 아이콘, 레이아웃 구성
# 브라우저 탭에 표시될 제목과 아이콘이다.
st.set_page_config(page_title="Agent with MCP Tools", page_icon="🧠", layout="wide")

# 사이드바 최상단에 저자 정보 추가 (다른 사이드바 요소보다 먼저 배치)
st.sidebar.markdown("### ✍️ Made by [테디노트](https://youtube.com/c/teddynote) 🚀")
st.sidebar.divider()  # 구분선 추가

# 기존 페이지 타이틀 및 설명
# 웹 페이지의 타이틀과 설명이다.
st.title("🤖 Agent with MCP Tools")
st.markdown("✨ MCP 도구를 활용한 ReAct 에이전트에게 질문해보세요.")

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

if "thread_id" not in st.session_state:
    st.session_state.thread_id = random_uuid()

### Google 인증 관련 상수
REDIRECT_URI = "http://localhost:8501/callback"

# --- 함수 정의 부분 ---


def print_message():
    """
    채팅 기록을 화면에 출력합니다.

    사용자와 어시스턴트의 메시지를 구분하여 화면에 표시하고,
    도구 호출 정보는 확장 가능한 패널로 표시합니다.
    """
    for message in st.session_state.history:
        if message["role"] == "user":
            st.chat_message("user").markdown(message["content"])
        elif message["role"] == "assistant":
            st.chat_message("assistant").markdown(message["content"])
        elif message["role"] == "assistant_tool":
            with st.expander("🔧 도구 호출 정보", expanded=False):
                st.markdown(message["content"])


def get_streaming_callback(text_placeholder, tool_placeholder):
    """
    스트리밍 콜백 함수를 생성합니다.

    매개변수:
        text_placeholder: 텍스트 응답을 표시할 Streamlit 컴포넌트
        tool_placeholder: 도구 호출 정보를 표시할 Streamlit 컴포넌트

    반환값:
        callback_func: 스트리밍 콜백 함수
        accumulated_text: 누적된 텍스트 응답을 저장하는 리스트
        accumulated_tool: 누적된 도구 호출 정보를 저장하는 리스트
    """
    accumulated_text = []
    accumulated_tool = []

    def callback_func(message: dict):
        nonlocal accumulated_text, accumulated_tool
        message_content = message.get("content", None)

        if isinstance(message_content, AIMessageChunk):
            if hasattr(message_content, "content"):
                if isinstance(message_content.content, str):
                    # 직접 문자열인 경우
                    accumulated_text.append(message_content.content)
                elif isinstance(message_content.content, list):
                    # 리스트인 경우 각 항목 처리
                    for chunk in message_content.content:
                        if isinstance(chunk, str):
                            accumulated_text.append(chunk)
                        elif isinstance(chunk, dict):
                            if chunk.get("type") == "text":
                                accumulated_text.append(chunk.get("text", ""))
                            elif chunk.get("type") == "tool_use":
                                if "partial_json" in chunk:
                                    accumulated_tool.append(chunk["partial_json"])
                                elif hasattr(message_content, "tool_call_chunks"):
                                    for tool_chunk in message_content.tool_call_chunks:
                                        accumulated_tool.append(
                                            "\n```json\n" + str(tool_chunk) + "\n```\n"
                                        )
                    # 도구 호출 정보만 실시간으로 표시
                    if accumulated_tool:
                        with tool_placeholder.expander("🔧 도구 호출 정보", expanded=True):
                            st.markdown("".join(accumulated_tool))
        elif isinstance(message_content, ToolMessage):
            accumulated_tool.append(
                "\n```json\n" + str(message_content.content) + "\n```\n"
            )
            with tool_placeholder.expander("🔧 도구 호출 정보", expanded=True):
                st.markdown("".join(accumulated_tool))
        
        # 누적된 전체 텍스트를 한번에 표시
        if accumulated_text:
            complete_response = "".join(accumulated_text)
            text_placeholder.markdown(complete_response)
        
        return None

    return callback_func, accumulated_text, accumulated_tool


async def process_query(query, text_placeholder, tool_placeholder, timeout_seconds=120):
    """
    사용자 질문을 처리하고 응답을 생성합니다.
    """
    try:
        if st.session_state.agent:
            streaming_callback, accumulated_text_obj, accumulated_tool_obj = (
                get_streaming_callback(text_placeholder, tool_placeholder)
            )
            try:
                # 현재 이벤트 루프 확인 및 설정
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

                # 응답 생성이 완료될 때까지 충분히 대기
                await asyncio.sleep(2)

                final_text = "".join(accumulated_text_obj)
                final_tool = "".join(accumulated_tool_obj)

                # 응답이 불완전한 경우 추가로 대기
                max_retries = 3
                retry_count = 0
                while (not final_text or 
                       final_text.strip().endswith(("...", "…")) or 
                       "thinking" in final_text.lower()) and retry_count < max_retries:
                    await asyncio.sleep(2)
                    final_text = "".join(accumulated_text_obj)
                    retry_count += 1

                # 응답이 있는 경우에만 화면에 표시
                if final_text.strip():
                    text_placeholder.markdown(final_text)
                if final_tool.strip():
                    with tool_placeholder.expander("🔧 도구 호출 정보", expanded=True):
                        st.markdown(final_tool)

                return response, final_text, final_tool

            except asyncio.TimeoutError:
                error_msg = f"⏱️ 요청 시간이 {timeout_seconds}초를 초과했습니다. 나중에 다시 시도해 주세요."
                return {"error": error_msg}, error_msg, ""
            except Exception as e:
                error_msg = f"처리 중 오류 발생: {str(e)}"
                return {"error": error_msg}, error_msg, ""
        else:
            return (
                {"error": "🚫 에이전트가 초기화되지 않았습니다."},
                "🚫 에이전트가 초기화되지 않았습니다.",
                "",
            )
    except Exception as e:
        import traceback
        error_msg = f"❌ 쿼리 처리 중 오류 발생: {str(e)}\n{traceback.format_exc()}"
        return {"error": error_msg}, error_msg, ""


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
                prompt="Use your tools to answer the question. Answer in Korean.",
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
        
        if st.button("Google 계정 연동하기", type="primary", use_container_width=True):
            flow = create_oauth_flow(REDIRECT_URI)
            auth_url = get_authorization_url(flow)
            st.session_state.flow = flow
            st.markdown(f"[Google 계정 인증하기]({auth_url})")
            st.info("위 링크를 클릭하여 Google 계정에 로그인하고 권한을 허용해주세요.")
            
        # 인증 코드 입력 필드
        auth_code = st.text_input("인증 코드 입력", placeholder="Google 인증 후 받은 코드를 입력하세요")
        if auth_code and st.button("인증 완료", use_container_width=True):
            try:
                credentials = fetch_token(st.session_state.flow, auth_code)
                save_credentials(credentials)
                if initialize_google_services():
                    st.success("✅ Google 계정 연동이 완료되었습니다!")
                    st.rerun()
            except Exception as e:
                st.error(f"인증 오류: {str(e)}")
    else:
        st.success("✅ Google 계정이 연동되었습니다.")
        if st.button("연동 해제", use_container_width=True):
            # 토큰 파일 삭제
            token_path = Path("token.pickle")
            if token_path.exists():
                token_path.unlink()
            st.session_state.google_authenticated = False
            st.session_state.gmail_service = None
            st.session_state.calendar_service = None
            st.info("Google 계정 연동이 해제되었습니다.")
            st.rerun()

# --- Gmail 탭 ---
if st.session_state.google_authenticated:
    tab1, tab2 = st.tabs(["📧 Gmail", "📅 캘린더"])
    
    with tab1:
        st.header("Gmail")
        
        # 이메일 목록 조회
        if st.button("받은편지함 조회", use_container_width=True):
            with st.spinner("이메일을 불러오는 중..."):
                try:
                    from gmail_utils import list_emails
                    emails = list_emails(st.session_state.gmail_service, max_results=10)
                    
                    if not emails:
                        st.info("받은편지함에 이메일이 없습니다.")
                    else:
                        for email in emails:
                            formatted = format_email_for_display(email)
                            with st.expander(f"📧 {formatted['subject']}"):
                                st.write(f"**발신자:** {formatted['from']}")
                                st.write(f"**날짜:** {formatted['date']}")
                                st.write(f"**내용 미리보기:** {formatted['snippet']}")
                                st.write(f"**ID:** {formatted['id']}")
                except Exception as e:
                    st.error(f"이메일 조회 중 오류 발생: {str(e)}")
        
        # 이메일 검색
        search_query = st.text_input("이메일 검색", placeholder="검색어를 입력하세요 (예: from:example@gmail.com)")
        if search_query and st.button("검색", use_container_width=True):
            with st.spinner("검색 중..."):
                try:
                    from gmail_utils import search_emails
                    emails = search_emails(st.session_state.gmail_service, query=search_query)
                    
                    if not emails:
                        st.info(f"'{search_query}' 검색 결과가 없습니다.")
                    else:
                        for email in emails:
                            formatted = format_email_for_display(email)
                            with st.expander(f"📧 {formatted['subject']}"):
                                st.write(f"**발신자:** {formatted['from']}")
                                st.write(f"**날짜:** {formatted['date']}")
                                st.write(f"**내용 미리보기:** {formatted['snippet']}")
                                st.write(f"**ID:** {formatted['id']}")
                except Exception as e:
                    st.error(f"이메일 검색 중 오류 발생: {str(e)}")
        
        # 이메일 전송
        with st.expander("✉️ 이메일 보내기"):
            to = st.text_input("받는 사람", placeholder="example@gmail.com (쉼표로 구분하여 여러 명 지정 가능)")
            subject = st.text_input("제목")
            body = st.text_area("내용", height=150)
            cc = st.text_input("참조 (CC)", placeholder="선택사항")
            bcc = st.text_input("숨은 참조 (BCC)", placeholder="선택사항")
            html_format = st.checkbox("HTML 형식")
            
            if st.button("전송", use_container_width=True):
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
                                st.success(f"이메일이 성공적으로 전송되었습니다. (ID: {sent_message['id']})")
                            else:
                                st.error("이메일 전송에 실패했습니다.")
                        except Exception as e:
                            st.error(f"이메일 전송 중 오류 발생: {str(e)}")
    
    # --- 캘린더 탭 ---
    with tab2:
        st.header("캘린더")
        
        # 일정 목록 조회
        if st.button("다가오는 일정 조회", use_container_width=True):
            with st.spinner("일정을 불러오는 중..."):
                try:
                    from calendar_utils import list_upcoming_events
                    events = list_upcoming_events(st.session_state.calendar_service)
                    
                    if not events:
                        st.info("다가오는 일정이 없습니다.")
                    else:
                        for event in events:
                            formatted = format_event_for_display(event)
                            with st.expander(f"📅 {formatted['summary']}"):
                                st.write(f"**시작:** {formatted['start']}")
                                
                                if 'location' in formatted:
                                    st.write(f"**장소:** {formatted['location']}")
                                
                                if 'description' in formatted:
                                    st.write(f"**설명:** {formatted['description']}")
                                
                                if 'attendees' in formatted:
                                    st.write(f"**참석자:** {', '.join(formatted['attendees'])}")
                                
                                st.write(f"**ID:** {formatted['id']}")
                                if 'link' in formatted:
                                    st.markdown(f"[캘린더에서 보기]({formatted['link']})")
                except Exception as e:
                    st.error(f"일정 조회 중 오류 발생: {str(e)}")
        
        # 일정 추가
        with st.expander("📝 일정 추가하기"):
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
            
            if st.button("일정 추가", use_container_width=True):
                if not summary:
                    st.error("일정 제목은 필수 입력 항목입니다.")
                else:
                    with st.spinner("일정 추가 중..."):
                        try:
                            from calendar_utils import create_calendar_event
                            from datetime import datetime, timezone
                            
                            # datetime 객체 생성
                            start_datetime = datetime.combine(start_date, start_time)
                            end_datetime = datetime.combine(end_date, end_time)
                            
                            # 참석자 목록 처리
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
                                st.success(f"일정이 성공적으로 추가되었습니다. (ID: {event['id']})")
                            else:
                                st.error("일정 추가에 실패했습니다.")
                        except Exception as e:
                            st.error(f"일정 추가 중 오류 발생: {str(e)}")


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


# --- 대화 기록 출력 ---
print_message()

# --- 사용자 입력 및 처리 ---
user_query = st.chat_input("💬 질문을 입력하세요")
if user_query:
    if st.session_state.session_initialized:
        st.chat_message("user").markdown(user_query)
        with st.chat_message("assistant"):
            tool_placeholder = st.empty()
            text_placeholder = st.empty()
            resp, final_text, final_tool = (
                st.session_state.event_loop.run_until_complete(
                    process_query(user_query, text_placeholder, tool_placeholder)
                )
            )
        if "error" in resp:
            st.error(resp["error"])
        else:
            st.session_state.history.append({"role": "user", "content": user_query})
            st.session_state.history.append(
                {"role": "assistant", "content": final_text}
            )
            if final_tool.strip():
                st.session_state.history.append(
                    {"role": "assistant_tool", "content": final_tool}
                )
            st.rerun()
    else:
        st.warning("⏳ 시스템이 아직 초기화 중입니다. 잠시 후 다시 시도해주세요.")

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
