import os
import json
from datetime import datetime, timedelta

def extract_and_validate_event_info(params):
    """
    일정 정보를 추출하고 검증하는 유틸리티 함수
    
    Args:
        params (dict): LLM에서 추출한 일정 파라미터
            
    Returns:
        dict: 검증 및 변환된 일정 파라미터
    """
    validated_params = params.copy()
    
    # 필수 파라미터 검증
    if 'summary' not in validated_params or not validated_params['summary']:
        raise ValueError("일정 제목이 누락되었습니다.")
    
    if 'start' not in validated_params or not validated_params['start']:
        raise ValueError("시작 시간이 누락되었습니다.")
    
    # 날짜/시간 형식 변환 및 검증
    try:
        # 시작 시간 처리
        if isinstance(validated_params['start'], str):
            # ISO 형식이 아닌 경우 변환 시도
            if 'T' not in validated_params['start'] and ':' not in validated_params['start']:
                # 날짜만 있는 경우 (YYYY-MM-DD)
                try:
                    # 형식 검증
                    datetime.fromisoformat(validated_params['start'])
                except ValueError:
                    # 다른 형식일 수 있으므로 현재 날짜로 설정
                    validated_params['start'] = datetime.now().date().isoformat()
            elif 'T' not in validated_params['start'] and ':' in validated_params['start']:
                # 시간만 있는 경우 (HH:MM:SS) - 오늘 날짜 추가
                try:
                    time_parts = validated_params['start'].split(':')
                    hour = int(time_parts[0])
                    minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                    
                    today = datetime.now().date()
                    time = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
                    validated_params['start'] = time.isoformat()
                except (ValueError, IndexError):
                    # 형식이 잘못된 경우 현재 시간으로 설정
                    validated_params['start'] = datetime.now().isoformat()
            else:
                # ISO 형식 검증
                try:
                    datetime.fromisoformat(validated_params['start'].replace('Z', '+00:00'))
                except ValueError:
                    # 형식이 잘못된 경우 현재 시간으로 설정
                    validated_params['start'] = datetime.now().isoformat()
    except Exception as e:
        print(f"시작 시간 처리 중 오류 발생: {e}")
        raise ValueError(f"시작 시간 형식이 올바르지 않습니다: {str(e)}")
    
    # 종료 시간 처리
    if 'end' not in validated_params or not validated_params['end']:
        # 시작 시간이 날짜만 있는 경우
        if 'T' not in validated_params['start']:
            # 하루 종일 일정으로 간주하고 다음 날로 설정
            start_date = datetime.fromisoformat(validated_params['start'])
            end_date = (start_date + timedelta(days=1)).isoformat()
            validated_params['end'] = end_date
        else:
            # 시간이 있는 경우 1시간 후로 설정
            start_datetime = datetime.fromisoformat(validated_params['start'].replace('Z', '+00:00'))
            end_datetime = (start_datetime + timedelta(hours=1)).isoformat()
            validated_params['end'] = end_datetime
    else:
        # 종료 시간이 있는 경우 형식 검증
        try:
            if 'T' not in validated_params['end'] and ':' not in validated_params['end']:
                # 날짜만 있는 경우 (YYYY-MM-DD)
                datetime.fromisoformat(validated_params['end'])
            elif 'T' not in validated_params['end'] and ':' in validated_params['end']:
                # 시간만 있는 경우 (HH:MM:SS) - 오늘 날짜 추가
                time_parts = validated_params['end'].split(':')
                hour = int(time_parts[0])
                minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                
                today = datetime.now().date()
                time = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
                validated_params['end'] = time.isoformat()
            else:
                # ISO 형식 검증
                datetime.fromisoformat(validated_params['end'].replace('Z', '+00:00'))
        except ValueError:
            # 형식이 잘못된 경우 시작 시간 + 1시간으로 설정
            if 'T' not in validated_params['start']:
                # 날짜만 있는 경우
                start_date = datetime.fromisoformat(validated_params['start'])
                end_date = (start_date + timedelta(days=1)).isoformat()
                validated_params['end'] = end_date
            else:
                # 시간이 있는 경우
                start_datetime = datetime.fromisoformat(validated_params['start'].replace('Z', '+00:00'))
                end_datetime = (start_datetime + timedelta(hours=1)).isoformat()
                validated_params['end'] = end_datetime
    
    return validated_params
