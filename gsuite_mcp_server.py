from mcp.server.fastmcp import FastMCP
import os
from google_auth import (
    create_oauth_flow, get_authorization_url, fetch_token, 
    save_credentials, load_credentials, is_authenticated,
    build_gmail_service, build_calendar_service
)
from gmail_utils import (
    list_emails, search_emails, get_email_content, 
    send_email, modify_email_labels
)
from calendar_utils import (
    list_upcoming_events, create_calendar_event, 
    format_event_for_display
)

# Initialize FastMCP server with configuration
mcp = FastMCP(
    "GSuite",  # Name of the MCP server
    instructions="Google Workspace 도구를 사용하여 Gmail과 캘린더를 관리할 수 있습니다.",
    host="0.0.0.0",
    port=8006,
)

# Gmail 관련 도구
@mcp.tool()
async def list_emails_tool(max_results: int = 10, label_ids: str = "INBOX") -> str:
    """
    Gmail 받은편지함에서 최근 이메일 목록을 조회합니다.
    
    Args:
        max_results: 조회할 최대 이메일 수 (기본값: 10)
        label_ids: 조회할 라벨 ID (기본값: "INBOX", 쉼표로 구분하여 여러 개 지정 가능)
        
    Returns:
        str: 이메일 목록 정보
    """
    credentials = load_credentials()
    if not credentials:
        return "Google 계정 인증이 필요합니다."
    
    service = build_gmail_service(credentials)
    label_id_list = label_ids.split(',')
    emails = list_emails(service, max_results=max_results, label_ids=label_id_list)
    
    if not emails:
        return "조회된 이메일이 없습니다."
    
    result = "이메일 목록:\n\n"
    for email in emails:
        formatted = format_email_for_display(email)
        result += f"제목: {formatted['subject']}\n"
        result += f"발신자: {formatted['from']}\n"
        result += f"날짜: {formatted['date']}\n"
        result += f"내용 미리보기: {formatted['snippet']}\n"
        result += f"ID: {formatted['id']}\n"
        result += "-" * 50 + "\n"
    
    return result

@mcp.tool()
async def search_emails_tool(query: str, max_results: int = 10) -> str:
    """
    Gmail에서 특정 쿼리로 이메일을 검색합니다.
    
    Args:
        query: 검색 쿼리 (예: "from:example@gmail.com", "subject:안녕")
        max_results: 조회할 최대 이메일 수 (기본값: 10)
        
    Returns:
        str: 검색된 이메일 목록 정보
    """
    credentials = load_credentials()
    if not credentials:
        return "Google 계정 인증이 필요합니다."
    
    service = build_gmail_service(credentials)
    emails = search_emails(service, query=query, max_results=max_results)
    
    if not emails:
        return f"'{query}' 검색 결과가 없습니다."
    
    result = f"'{query}' 검색 결과:\n\n"
    for email in emails:
        formatted = format_email_for_display(email)
        result += f"제목: {formatted['subject']}\n"
        result += f"발신자: {formatted['from']}\n"
        result += f"날짜: {formatted['date']}\n"
        result += f"내용 미리보기: {formatted['snippet']}\n"
        result += f"ID: {formatted['id']}\n"
        result += "-" * 50 + "\n"
    
    return result

@mcp.tool()
async def send_email_tool(to: str, subject: str, body: str, cc: str = "", bcc: str = "", html: bool = False) -> str:
    """
    Gmail을 통해 이메일을 전송합니다.
    
    Args:
        to: 수신자 이메일 주소 (쉼표로 구분하여 여러 명 지정 가능)
        subject: 이메일 제목
        body: 이메일 본문
        cc: 참조 수신자 (선택, 쉼표로 구분하여 여러 명 지정 가능)
        bcc: 숨은 참조 수신자 (선택, 쉼표로 구분하여 여러 명 지정 가능)
        html: HTML 형식 여부 (기본값: False)
        
    Returns:
        str: 이메일 전송 결과
    """
    credentials = load_credentials()
    if not credentials:
        return "Google 계정 인증이 필요합니다."
    
    service = build_gmail_service(credentials)
    
    # 쉼표로 구분된 이메일 주소를 리스트로 변환
    to_list = [email.strip() for email in to.split(',') if email.strip()]
    cc_list = [email.strip() for email in cc.split(',') if email.strip()] if cc else None
    bcc_list = [email.strip() for email in bcc.split(',') if email.strip()] if bcc else None
    
    sent_message = send_email(service, to_list, subject, body, cc=cc_list, bcc=bcc_list, html=html)
    
    if sent_message:
        return f"이메일이 성공적으로 전송되었습니다. (ID: {sent_message['id']})"
    else:
        return "이메일 전송에 실패했습니다."

@mcp.tool()
async def modify_email_tool(msg_id: str, action: str) -> str:
    """
    Gmail 이메일의 라벨을 수정합니다.
    
    Args:
        msg_id: 이메일 ID
        action: 수행할 작업 (archive, trash, unread, read)
        
    Returns:
        str: 라벨 수정 결과
    """
    credentials = load_credentials()
    if not credentials:
        return "Google 계정 인증이 필요합니다."
    
    service = build_gmail_service(credentials)
    
    add_labels = []
    remove_labels = []
    
    if action.lower() == 'archive':
        remove_labels = ['INBOX']
    elif action.lower() == 'trash':
        add_labels = ['TRASH']
        remove_labels = ['INBOX']
    elif action.lower() == 'unread':
        add_labels = ['UNREAD']
        remove_labels = ['READ']
    elif action.lower() == 'read':
        add_labels = ['READ']
        remove_labels = ['UNREAD']
    else:
        return f"지원하지 않는 작업입니다: {action}"
    
    modified_message = modify_email_labels(service, msg_id, add_labels=add_labels, remove_labels=remove_labels)
    
    if modified_message:
        return f"이메일 라벨이 성공적으로 수정되었습니다. (ID: {modified_message['id']})"
    else:
        return "이메일 라벨 수정에 실패했습니다."

# 캘린더 관련 도구
@mcp.tool()
async def list_events_tool(max_results: int = 10) -> str:
    """
    Google 캘린더에서 다가오는 일정을 조회합니다.
    
    Args:
        max_results: 조회할 최대 일정 수 (기본값: 10)
        
    Returns:
        str: 일정 목록 정보
    """
    credentials = load_credentials()
    if not credentials:
        return "Google 계정 인증이 필요합니다."
    
    service = build_calendar_service(credentials)
    events = list_upcoming_events(service, max_results=max_results)
    
    if not events:
        return "다가오는 일정이 없습니다."
    
    result = "다가오는 일정 목록:\n\n"
    for event in events:
        formatted = format_event_for_display(event)
        result += f"제목: {formatted['summary']}\n"
        result += f"시작: {formatted['start']}\n"
        
        if 'location' in formatted:
            result += f"장소: {formatted['location']}\n"
        
        if 'description' in formatted:
            result += f"설명: {formatted['description']}\n"
        
        result += f"ID: {formatted['id']}\n"
        result += "-" * 50 + "\n"
    
    return result

@mcp.tool()
async def create_event_tool(summary: str, start_datetime: str, end_datetime: str, 
                           location: str = "", description: str = "", attendees: str = "") -> str:
    """
    Google 캘린더에 새 일정을 추가합니다.
    
    Args:
        summary: 일정 제목
        start_datetime: 시작 시간 (YYYY-MM-DD HH:MM 형식)
        end_datetime: 종료 시간 (YYYY-MM-DD HH:MM 형식)
        location: 장소 (선택)
        description: 설명 (선택)
        attendees: 참석자 이메일 주소 (선택, 쉼표로 구분하여 여러 명 지정 가능)
        
    Returns:
        str: 일정 생성 결과
    """
    credentials = load_credentials()
    if not credentials:
        return "Google 계정 인증이 필요합니다."
    
    service = build_calendar_service(credentials)
    
    # 날짜/시간 문자열을 datetime 객체로 변환
    try:
        start_time = datetime.strptime(start_datetime, "%Y-%m-%d %H:%M")
        end_time = datetime.strptime(end_datetime, "%Y-%m-%d %H:%M")
    except ValueError:
        return "날짜/시간 형식이 올바르지 않습니다. YYYY-MM-DD HH:MM 형식으로 입력해주세요."
    
    # 참석자 목록 처리
    attendee_list = [email.strip() for email in attendees.split(',') if email.strip()] if attendees else None
    
    event = create_calendar_event(
        service, 
        summary=summary, 
        location=location, 
        description=description,
        start_time=start_time, 
        end_time=end_time, 
        attendees=attendee_list
    )
    
    if event:
        return f"일정이 성공적으로 생성되었습니다. (ID: {event['id']})"
    else:
        return "일정 생성에 실패했습니다."

if __name__ == "__main__":
    # Print a message indicating the server is starting
    print("GSuite MCP 서버가 실행 중입니다...")
    
    # Start the MCP server with stdio transport for local development
    mcp.run(transport="stdio")
