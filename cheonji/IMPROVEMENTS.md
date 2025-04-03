# 캘린더 어시스턴트 개선 사항 문서

## 개요
이 문서는 캘린더 어시스턴트 애플리케이션의 문제점을 분석하고 개선한 내용을 설명합니다.

## 발견된 문제점
1. **일정 추가 오류**: 일정 제목과 시작 시간을 명시했음에도 인식하지 못하는 문제
2. **비 캘린더 쿼리 처리**: 날씨와 같은 캘린더와 관련 없는 쿼리에 대해 불필요하게 캘린더 API를 호출하는 문제

## 구현된 개선 사항

### 1. LLM 프롬프트 엔지니어링 개선
- **파일**: `llm_processor.py`
- **변경 내용**:
  - 일정 정보 추출에 대한 구체적인 지침 추가
  - 비 캘린더 쿼리 구분 로직 포함
  - 예시를 통한 정확한 정보 추출 유도
- **개선 효과**:
  - LLM이 사용자 쿼리에서 일정 정보를 더 정확하게 추출
  - 캘린더 관련 쿼리와 비 캘린더 쿼리를 명확히 구분

### 2. 쿼리 분류 로직 구현
- **파일**: `app.py`
- **변경 내용**:
  - `handle_non_calendar_query` 함수 추가
  - `process_user_query` 함수에 비 캘린더 쿼리 처리 로직 추가
- **개선 효과**:
  - 캘린더와 관련 없는 쿼리에 대해 적절한 응답 제공
  - 불필요한 캘린더 API 호출 방지

### 3. 일정 정보 추출 및 검증 강화
- **파일**: `event_utils.py` (신규)
- **변경 내용**:
  - `extract_and_validate_event_info` 유틸리티 함수 구현
  - 다양한 날짜/시간 형식 처리 기능 추가
  - 누락된 정보 자동 보완 기능 구현
- **개선 효과**:
  - 사용자가 다양한 형태로 입력한 일정 정보를 정확하게 처리
  - 날짜/시간 형식 오류 감소
  - 일정 생성 성공률 향상

### 4. 비 캘린더 쿼리 처리 개선
- **파일**: `app.py`
- **변경 내용**:
  - 비 캘린더 쿼리에 대한 별도 처리 로직 구현
  - 일반적인 질문에 대한 응답 생성 기능 추가
- **개선 효과**:
  - 날씨 등 캘린더와 관련 없는 쿼리에 대한 적절한 응답 제공
  - 사용자 경험 향상

## 코드 변경 요약

### llm_processor.py
```python
# 시스템 프롬프트 개선
system_prompt = """
당신은 Google Calendar API와 연동된 캘린더 어시스턴트입니다.
사용자의 자연어 쿼리를 분석하여 적절한 캘린더 작업으로 변환해야 합니다.

지원하는 작업 유형:
1. list_events: 일정 조회
2. create_event: 일정 생성
3. update_event: 일정 수정
4. delete_event: 일정 삭제
5. non_calendar: 캘린더와 관련 없는 쿼리

일정 생성 시 반드시 다음 정보를 추출해야 합니다:
- summary: 일정 제목 (필수)
- start: 시작 시간 (필수, ISO 형식 또는 명확한 날짜/시간)
- end: 종료 시간 (선택, 없으면 시작 시간 + 1시간)
- location: 위치 (선택)

예시:
쿼리: "오늘 오후 3시부터 5시까지 '나비' 팀 회의 일정 추가해줘"
응답: {
  "action": "create_event",
  "parameters": {
    "summary": "나비 팀 회의",
    "start": "2025-04-03T15:00:00",
    "end": "2025-04-03T17:00:00"
  },
  "description": "오늘 오후 3시부터 5시까지 나비 팀 회의 일정을 추가합니다."
}

쿼리: "오늘 서울 날씨는?"
응답: {
  "action": "non_calendar",
  "parameters": {},
  "description": "이 질문은 캘린더와 관련이 없습니다."
}
"""
```

### app.py
```python
# 비 캘린더 쿼리 처리 함수 추가
def handle_non_calendar_query(query):
    """
    캘린더와 관련 없는 쿼리에 대한 응답 생성
    """
    # OpenAI API를 사용하여 일반 응답 생성
    # ...

# 사용자 쿼리 처리 함수 개선
def process_user_query(query):
    # ...
    
    # 캘린더와 관련 없는 쿼리 처리
    if action == 'non_calendar':
        response = handle_non_calendar_query(query)
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        return response, {"type": "general_response", "description": description}
    
    # 일정 생성 시 검증 강화
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
    # ...
```

### event_utils.py (신규)
```python
def extract_and_validate_event_info(params):
    """
    일정 정보를 추출하고 검증하는 유틸리티 함수
    """
    # 필수 파라미터 검증
    # 날짜/시간 형식 변환 및 검증
    # 누락된 정보 자동 보완
    # ...
```

## 테스트 결과
개선된 애플리케이션은 다음과 같은 쿼리를 성공적으로 처리할 수 있습니다:

1. **일정 추가**:
   - "오늘 오후 3시부터 5시까지 '나비' 팀 회의 일정 추가해줘"
   - "2025년 4월 4일 오후 5시부터 오후 7시까지 '나비' 팀의 회의 일정 추가"
   - "다음 주 월요일 10시에 치과 예약 일정 추가해줘"

2. **비 캘린더 쿼리**:
   - "오늘 서울 날씨는?"
   - "내일 비 올까?"
   - "한국의 수도는?"

## 향후 개선 사항
1. **리디렉션 자동 처리**: 현재 사용자가 인증 코드를 수동으로 복사해야 함
2. **날짜/시간 인식 개선**: 더 다양한 형식의 날짜/시간 표현 지원
3. **일정 시각화**: 캘린더 뷰를 통한 일정 시각화 기능 추가
4. **다국어 지원**: 영어, 일본어 등 다양한 언어 지원

## 결론
이번 개선을 통해 캘린더 어시스턴트 애플리케이션의 주요 문제점을 해결하고, 사용자 경험을 크게 향상시켰습니다. 특히 일정 정보 추출 및 검증 강화와 비 캘린더 쿼리 처리 개선을 통해 애플리케이션의 정확성과 유용성이 크게 향상되었습니다.
