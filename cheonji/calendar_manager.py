import os
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class CalendarManager:
    def __init__(self, credentials):
        """
        Google Calendar API를 사용하여 캘린더 작업을 수행하는 클래스
        
        Args:
            credentials: Google OAuth 인증 정보
        """
        self.service = build('calendar', 'v3', credentials=credentials)
    
    def list_events(self, params):
        """
        캘린더 일정 조회
        
        Args:
            params (dict): 조회 파라미터
                - time_min (str, optional): 시작 시간 (ISO 형식)
                - time_max (str, optional): 종료 시간 (ISO 형식)
                - max_results (int, optional): 최대 결과 수
                - calendar_id (str, optional): 캘린더 ID
                
        Returns:
            dict: 조회된 일정 목록
        """
        try:
            # 기본값 설정
            calendar_id = params.get('calendar_id', 'primary')
            max_results = params.get('max_results', 10)
            
            # 시간 범위 설정
            now = datetime.utcnow().isoformat() + 'Z'  # 'Z'는 UTC 시간대를 의미
            time_min = params.get('time_min', now)
            
            # time_max가 없으면 기본값으로 30일 후로 설정
            if 'time_max' not in params:
                time_max = (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z'
            else:
                time_max = params.get('time_max')
            
            # API 호출
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # 결과 가공
            processed_events = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                processed_event = {
                    'id': event['id'],
                    'summary': event.get('summary', '(제목 없음)'),
                    'start': start,
                    'end': end,
                    'location': event.get('location', ''),
                    'description': event.get('description', '')
                }
                processed_events.append(processed_event)
            
            return {
                'events': processed_events,
                'total': len(processed_events)
            }
            
        except HttpError as error:
            print(f'캘린더 일정 조회 중 오류 발생: {error}')
            return {
                'error': str(error),
                'events': [],
                'total': 0
            }
    
    def create_event(self, params):
        """
        캘린더 일정 생성
        
        Args:
            params (dict): 일정 파라미터
                - summary (str): 일정 제목
                - start (str): 시작 시간 (ISO 형식 또는 날짜)
                - end (str, optional): 종료 시간 (ISO 형식 또는 날짜)
                - location (str, optional): 위치
                - description (str, optional): 설명
                - calendar_id (str, optional): 캘린더 ID
                
        Returns:
            dict: 생성된 일정 정보
        """
        try:
            # 필수 파라미터 확인
            if 'summary' not in params or 'start' not in params:
                return {
                    'error': '일정 제목과 시작 시간은 필수입니다.',
                    'success': False
                }
            
            # 기본값 설정
            calendar_id = params.get('calendar_id', 'primary')
            
            # 종료 시간이 없으면 시작 시간 + 1시간으로 설정
            if 'end' not in params:
                # 날짜 형식인지 확인
                if 'T' not in params['start']:  # 날짜만 있는 경우 (YYYY-MM-DD)
                    start_date = datetime.fromisoformat(params['start'])
                    end_date = (start_date + timedelta(days=1)).isoformat()
                    params['end'] = end_date
                else:  # 시간까지 있는 경우 (YYYY-MM-DDTHH:MM:SS)
                    start_datetime = datetime.fromisoformat(params['start'].replace('Z', '+00:00'))
                    end_datetime = (start_datetime + timedelta(hours=1)).isoformat()
                    params['end'] = end_datetime
            
            # 이벤트 데이터 구성
            event = {
                'summary': params['summary'],
                'location': params.get('location', ''),
                'description': params.get('description', ''),
            }
            
            # 날짜 형식인지 시간 형식인지 확인하여 설정
            if 'T' not in params['start']:  # 날짜만 있는 경우
                event['start'] = {'date': params['start']}
                event['end'] = {'date': params['end']}
            else:  # 시간까지 있는 경우
                event['start'] = {'dateTime': params['start'], 'timeZone': 'Asia/Seoul'}
                event['end'] = {'dateTime': params['end'], 'timeZone': 'Asia/Seoul'}
            
            # API 호출
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()
            
            return {
                'success': True,
                'event': {
                    'id': created_event['id'],
                    'summary': created_event.get('summary', ''),
                    'start': created_event['start'].get('dateTime', created_event['start'].get('date')),
                    'end': created_event['end'].get('dateTime', created_event['end'].get('date')),
                    'location': created_event.get('location', ''),
                    'description': created_event.get('description', '')
                }
            }
            
        except Exception as error:
            print(f'캘린더 일정 생성 중 오류 발생: {error}')
            return {
                'error': str(error),
                'success': False
            }
    
    def update_event(self, params):
        """
        캘린더 일정 수정
        
        Args:
            params (dict): 수정 파라미터
                - event_id (str): 수정할 일정 ID
                - summary (str, optional): 일정 제목
                - start (str, optional): 시작 시간 (ISO 형식 또는 날짜)
                - end (str, optional): 종료 시간 (ISO 형식 또는 날짜)
                - location (str, optional): 위치
                - description (str, optional): 설명
                - calendar_id (str, optional): 캘린더 ID
                
        Returns:
            dict: 수정된 일정 정보
        """
        try:
            # 필수 파라미터 확인
            if 'event_id' not in params:
                return {
                    'error': '수정할 일정 ID는 필수입니다.',
                    'success': False
                }
            
            # 기본값 설정
            calendar_id = params.get('calendar_id', 'primary')
            event_id = params['event_id']
            
            # 기존 이벤트 가져오기
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # 수정할 필드 업데이트
            if 'summary' in params:
                event['summary'] = params['summary']
            
            if 'location' in params:
                event['location'] = params['location']
                
            if 'description' in params:
                event['description'] = params['description']
            
            # 시작 시간 수정
            if 'start' in params:
                if 'T' not in params['start']:  # 날짜만 있는 경우
                    event['start'] = {'date': params['start']}
                else:  # 시간까지 있는 경우
                    event['start'] = {'dateTime': params['start'], 'timeZone': 'Asia/Seoul'}
            
            # 종료 시간 수정
            if 'end' in params:
                if 'T' not in params['end']:  # 날짜만 있는 경우
                    event['end'] = {'date': params['end']}
                else:  # 시간까지 있는 경우
                    event['end'] = {'dateTime': params['end'], 'timeZone': 'Asia/Seoul'}
            
            # API 호출
            updated_event = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            return {
                'success': True,
                'event': {
                    'id': updated_event['id'],
                    'summary': updated_event.get('summary', ''),
                    'start': updated_event['start'].get('dateTime', updated_event['start'].get('date')),
                    'end': updated_event['end'].get('dateTime', updated_event['end'].get('date')),
                    'location': updated_event.get('location', ''),
                    'description': updated_event.get('description', '')
                }
            }
            
        except Exception as error:
            print(f'캘린더 일정 수정 중 오류 발생: {error}')
            return {
                'error': str(error),
                'success': False
            }
    
    def delete_event(self, params):
        """
        캘린더 일정 삭제
        
        Args:
            params (dict): 삭제 파라미터
                - event_id (str): 삭제할 일정 ID
                - calendar_id (str, optional): 캘린더 ID
                
        Returns:
            dict: 삭제 결과
        """
        try:
            # 필수 파라미터 확인
            if 'event_id' not in params:
                return {
                    'error': '삭제할 일정 ID는 필수입니다.',
                    'success': False
                }
            
            # 기본값 설정
            calendar_id = params.get('calendar_id', 'primary')
            event_id = params['event_id']
            
            # API 호출
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            return {
                'success': True,
                'message': '일정이 성공적으로 삭제되었습니다.'
            }
            
        except Exception as error:
            print(f'캘린더 일정 삭제 중 오류 발생: {error}')
            return {
                'error': str(error),
                'success': False
            }
