import os
import openai
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# OpenAI API 키 설정
openai.api_key = os.getenv('OPENAI_API_KEY')

class LLMProcessor:
    def __init__(self):
        self.model = "gpt-4o-mini"  # 또는 다른 적절한 모델
    
    def process_query(self, query, user_context=None):
        """
        사용자 쿼리를 처리하여 캘린더 작업으로 변환
        
        Args:
            query (str): 사용자의 자연어 쿼리
            user_context (dict, optional): 사용자 컨텍스트 정보
            
        Returns:
            dict: 처리된 작업 정보 (작업 유형, 파라미터 등)
        """
        # 시스템 프롬프트 설정
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
        
        응답은 항상 JSON 형식으로 다음 구조를 따라야 합니다:
        {
            "action": "작업 유형",
            "parameters": {
                "param1": "값1",
                "param2": "값2",
                ...
            },
            "description": "사용자에게 보여줄 설명"
        }
        
        일정 생성/수정 시 summary와 start는 반드시 포함해야 합니다.
        날짜와 시간은 가능한 ISO 형식(YYYY-MM-DDTHH:MM:SS)으로 변환하세요.
        """
        
        # 사용자 컨텍스트가 있으면 추가
        context_prompt = ""
        if user_context:
            context_prompt = f"사용자 컨텍스트: {user_context}\n"
        
        try:
            # OpenAI API 호출
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context_prompt + query}
                ],
                response_format={"type": "json_object"}
            )
            
            # 응답 추출 및 파싱
            result = response.choices[0].message.content
            
            # 디버깅용 출력
            print(f"LLM 응답: {result}")
            
            # 결과 반환
            import json
            return json.loads(result)
            
        except Exception as e:
            print(f"LLM 처리 중 오류 발생: {e}")
            # 오류 발생 시 기본 응답
            return {
                "action": "error",
                "parameters": {},
                "description": f"죄송합니다. 요청을 처리하는 중 오류가 발생했습니다: {str(e)}"
            }
    
    def generate_response(self, calendar_data, query):
        """
        캘린더 데이터를 기반으로 사용자 친화적인 응답 생성
        
        Args:
            calendar_data (dict): 캘린더 API에서 반환된 데이터
            query (str): 원래 사용자 쿼리
            
        Returns:
            str: 사용자 친화적인 응답
        """
        try:
            # 시스템 프롬프트 설정
            system_prompt = """
            당신은 Google Calendar 데이터를 사용자 친화적인 방식으로 설명하는 어시스턴트입니다.
            제공된 캘린더 데이터를 분석하고 사용자의 원래 질문에 대한 명확하고 유용한 응답을 생성하세요.
            응답은 자연스러운 한국어로 작성하고, 일정이 있다면 날짜, 시간, 제목, 위치 등 중요한 정보를 포함해야 합니다.
            """
            
            # 캘린더 데이터를 문자열로 변환
            import json
            calendar_data_str = json.dumps(calendar_data, ensure_ascii=False)
            
            # OpenAI API 호출
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"원래 사용자 질문: {query}\n\n캘린더 데이터: {calendar_data_str}"}
                ]
            )
            
            # 응답 추출
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"응답 생성 중 오류 발생: {e}")
            return f"캘린더 정보를 처리했지만 응답 생성 중 오류가 발생했습니다: {str(e)}"
