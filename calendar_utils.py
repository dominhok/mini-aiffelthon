import os
from datetime import datetime, timedelta
from googleapiclient.errors import HttpError

def list_upcoming_events(service, max_results=10, time_min=None):
    """
    캘린더에서 다가오는 일정을 조회합니다.
    
    Args:
        service: 구글 캘린더 API 서비스 객체
        max_results: 최대 조회 결과 수 (기본값: 10)
        time_min: 조회 시작 시간 (기본값: 현재 시간)
        
    Returns:
        events: 일정 목록
    """
    if time_min is None:
        time_min = datetime.utcnow().isoformat() + 'Z'  # 'Z'는 UTC 시간을 의미
    
    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        return events
    
    except HttpError as error:
        print(f'캘린더 일정 조회 중 오류 발생: {error}')
        return []

def create_calendar_event(service, summary, location=None, description=None, 
                         start_time=None, end_time=None, attendees=None, timezone='Asia/Seoul'):
    """
    캘린더에 새 일정을 추가합니다.
    
    Args:
        service: 구글 캘린더 API 서비스 객체
        summary: 일정 제목
        location: 장소 (선택)
        description: 설명 (선택)
        start_time: 시작 시간 (datetime 객체, 기본값: 현재 시간 + 1시간)
        end_time: 종료 시간 (datetime 객체, 기본값: 시작 시간 + 1시간)
        attendees: 참석자 이메일 목록 (선택)
        timezone: 시간대 (기본값: 'Asia/Seoul')
        
    Returns:
        event: 생성된 일정 정보
    """
    # 기본 시작/종료 시간 설정
    if start_time is None:
        start_time = datetime.now() + timedelta(hours=1)
    
    if end_time is None:
        end_time = start_time + timedelta(hours=1)
    
    # 이벤트 본문 생성
    event_body = {
        'summary': summary,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': timezone,
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': timezone,
        },
    }
    
    # 선택적 필드 추가
    if location:
        event_body['location'] = location
    
    if description:
        event_body['description'] = description
    
    if attendees:
        event_body['attendees'] = [{'email': email} for email in attendees]
    
    try:
        event = service.events().insert(calendarId='primary', body=event_body).execute()
        return event
    
    except HttpError as error:
        print(f'캘린더 일정 생성 중 오류 발생: {error}')
        return None

def format_event_for_display(event):
    """
    캘린더 일정을 표시용 형식으로 변환합니다.
    
    Args:
        event: 캘린더 일정 객체
        
    Returns:
        formatted_event: 표시용으로 형식화된 일정 정보
    """
    start = event['start'].get('dateTime', event['start'].get('date'))
    
    # 날짜/시간 형식 변환
    if 'T' in start:  # dateTime 형식 (날짜+시간)
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        start_str = start_dt.strftime('%Y년 %m월 %d일 %H:%M')
    else:  # date 형식 (종일 일정)
        start_dt = datetime.fromisoformat(start)
        start_str = start_dt.strftime('%Y년 %m월 %d일 (종일)')
    
    # 기본 정보
    formatted_event = {
        'id': event['id'],
        'summary': event.get('summary', '(제목 없음)'),
        'start': start_str,
        'link': event.get('htmlLink', '')
    }
    
    # 선택적 정보
    if 'location' in event and event['location']:
        formatted_event['location'] = event['location']
    
    if 'description' in event and event['description']:
        formatted_event['description'] = event['description']
    
    if 'attendees' in event:
        formatted_event['attendees'] = [attendee.get('email') for attendee in event['attendees']]
    
    return formatted_event
