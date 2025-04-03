import streamlit as st
import os
import json
from datetime import datetime, timedelta
from google_auth import get_google_auth_url, handle_auth_callback, get_credentials, build_calendar_service
from llm_processor import LLMProcessor
from calendar_manager import CalendarManager
from event_utils import extract_and_validate_event_info
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="캘린더 어시스턴트",
    page_icon="📅",
    layout="wide"
)

# 세션 상태 초기화
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'credentials' not in st.session_state:
    st.session_state.credentials = None
if 'flow' not in st.session_state:
    st.session_state.flow = None
if 'calendar_service' not in st.session_state:
    st.session_state.calendar_service = None
if 'llm_processor' not in st.session_state:
    st.session_state.llm_processor = LLMProcessor()
if 'calendar_manager' not in st.session_state:
    st.session_state.calendar_manager = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# 인증 상태 확인
def check_auth():
    credentials, need_auth = get_credentials()
    if not need_auth:
        st.session_state.authenticated = True
        st.session_state.credentials = credentials
        st.session_state.calendar_service = build_calendar_service(credentials)
        st.session_state.calendar_manager = CalendarManager(credentials)
    return need_auth

# 비 캘린더 쿼리 처리
def handle_non_calendar_query(query):
    """
    캘린더와 관련 없는 쿼리에 대한 응답 생성
    
    Args:
        query (str): 사용자의 자연어 쿼리
        
    Returns:
        str: 사용자 친화적인 응답
    """
    try:
        import openai
        from dotenv import load_dotenv
        import os
        
        # 환경 변수 로드
        load_dotenv()
        
        # OpenAI API 키 설정
        openai.api_key = os.getenv('OPENAI_API_KEY')
        
        # 시스템 프롬프트 설정
        system_prompt = """
        당신은 도움이 되는 어시스턴트입니다. 
        캘린더 관련 질문이 아닌 일반적인 질문에 대해 유용한 응답을 제공하세요.
        응답은 자연스러운 한국어로 작성하세요.
        """
        
        # OpenAI API 호출
        response = openai.chat.completions.create(
            model="gpt-4o",  # 또는 다른 적절한 모델
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
        )
        
        # 응답 추출
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"비 캘린더 쿼리 처리 중 오류 발생: {e}")
        return f"죄송합니다. 질문을 처리하는 중 오류가 발생했습니다: {str(e)}"

# 사용자 쿼리 처리
def process_user_query(query):
    try:
        # LLM을 사용하여 쿼리 처리
        llm_response = st.session_state.llm_processor.process_query(query)
        
        # 디버깅용 출력
        st.session_state.chat_history.append({"role": "user", "content": query})
        
        # 액션 실행
        action = llm_response.get('action', '')
        parameters = llm_response.get('parameters', {})
        description = llm_response.get('description', '')
        
        # 캘린더와 관련 없는 쿼리 처리
        if action == 'non_calendar':
            response = handle_non_calendar_query(query)
            st.session_state.chat_history.append({"role": "assistant", "content": response})
            return response, {"type": "general_response", "description": description}
        
        # 캘린더 작업 수행
        calendar_data = {}
        if action == 'list_events':
            calendar_data = st.session_state.calendar_manager.list_events(parameters)
        elif action == 'create_event':
            # 필수 파라미터 검증
            if 'summary' not in parameters or 'start' not in parameters:
                error_message = "일정을 추가하려면 제목과 시작 시간이 필요합니다. 다시 시도해주세요."
                st.session_state.chat_history.append({"role": "assistant", "content": error_message})
                return error_message, {"error": "필수 파라미터 누락"}
            
            try:
                # 일정 정보 추출 및 검증
                validated_params = extract_and_validate_event_info(parameters)
                calendar_data = st.session_state.calendar_manager.create_event(validated_params)
            except ValueError as e:
                error_message = f"일정 정보 검증 중 오류가 발생했습니다: {str(e)}"
                st.session_state.chat_history.append({"role": "assistant", "content": error_message})
                return error_message, {"error": str(e)}
        elif action == 'update_event':
            try:
                # 일정 정보 추출 및 검증
                validated_params = extract_and_validate_event_info(parameters)
                calendar_data = st.session_state.calendar_manager.update_event(validated_params)
            except ValueError as e:
                error_message = f"일정 정보 검증 중 오류가 발생했습니다: {str(e)}"
                st.session_state.chat_history.append({"role": "assistant", "content": error_message})
                return error_message, {"error": str(e)}
        elif action == 'delete_event':
            calendar_data = st.session_state.calendar_manager.delete_event(parameters)
        elif action == 'error':
            calendar_data = {"error": description}
        
        # 사용자 친화적인 응답 생성
        response = st.session_state.llm_processor.generate_response(calendar_data, query)
        
        # 채팅 기록에 추가
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        
        return response, calendar_data
    
    except Exception as e:
        error_message = f"쿼리 처리 중 오류가 발생했습니다: {str(e)}"
        st.session_state.chat_history.append({"role": "assistant", "content": error_message})
        return error_message, {"error": str(e)}

# 메인 앱 UI
def main():
    st.title("📅 캘린더 어시스턴트")
    
    # 사이드바
    with st.sidebar:
        st.header("정보")
        st.info("이 앱은 자연어로 구글 캘린더를 조회하고 관리할 수 있게 해줍니다.")
        
        if st.session_state.authenticated:
            st.success("✅ 구글 계정 연결됨")
            if st.button("로그아웃"):
                # 토큰 파일 삭제 및 세션 초기화
                if os.path.exists("token.pickle"):
                    os.remove("token.pickle")
                st.session_state.authenticated = False
                st.session_state.credentials = None
                st.session_state.calendar_service = None
                st.session_state.calendar_manager = None
                st.rerun()
        else:
            st.warning("⚠️ 구글 계정 연결 필요")
    
    # 인증 필요 확인
    need_auth = check_auth()
    
    # 인증 처리
    if need_auth:
        st.header("구글 캘린더 연결")
        st.write("캘린더 어시스턴트를 사용하려면 구글 계정에 연결해야 합니다.")
        
        if st.button("구글 계정으로 로그인"):
            auth_url, flow = get_google_auth_url()
            st.session_state.flow = flow
            st.markdown(f"[구글 로그인 페이지로 이동]({auth_url})")
            st.info("로그인 후 리디렉션된 페이지의 URL에서 'code=' 다음에 오는 코드를 복사하세요.")
            
        auth_code = st.text_input("인증 코드를 입력하세요:")
        if auth_code and st.session_state.flow:
            credentials = handle_auth_callback(st.session_state.flow, auth_code)
            if credentials:
                st.session_state.authenticated = True
                st.session_state.credentials = credentials
                st.session_state.calendar_service = build_calendar_service(credentials)
                st.session_state.calendar_manager = CalendarManager(credentials)
                st.success("인증 성공! 페이지를 새로고침합니다.")
                st.rerun()
            else:
                st.error("인증에 실패했습니다. 다시 시도해주세요.")
    
    # 인증 완료 후 메인 기능
    else:
        st.header("캘린더 어시스턴트와 대화하기")
        st.write("자연어로 질문하면 캘린더 정보를 조회하고 관리해 드립니다.")
        
        # 사용 예시
        with st.expander("💡 사용 예시"):
            st.markdown("""
            - "다음 주 일정을 알려줘"
            - "내일 회의 일정이 있어?"
            - "다음 달 15일에 약속 있어?"
            - "오늘 오후 3시에 팀 미팅 추가해줘"
            - "다음 주 월요일 10시에 치과 예약 일정 추가해줘"
            """)
        
        # 채팅 기록 표시
        chat_container = st.container()
        with chat_container:
            for message in st.session_state.chat_history:
                if message["role"] == "user":
                    st.markdown(f"**사용자**: {message['content']}")
                else:
                    st.markdown(f"**어시스턴트**: {message['content']}")
        
        # 사용자 입력
        user_query = st.text_input("질문을 입력하세요:", placeholder="예: 이번 주 일정을 알려줘")
        
        if user_query:
            with st.spinner("처리 중..."):
                response, calendar_data = process_user_query(user_query)
                
                # 디버깅 정보 (개발 중에만 표시)
                with st.expander("디버깅 정보"):
                    st.json(calendar_data)

if __name__ == "__main__":
    main()
