import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from googleapiclient.errors import HttpError

def list_emails(service, max_results=10, query=None, label_ids=None):
    """
    Gmail에서 이메일 목록을 조회합니다.
    
    Args:
        service: 구글 Gmail API 서비스 객체
        max_results: 최대 조회 결과 수 (기본값: 10)
        query: 검색 쿼리 (선택)
        label_ids: 라벨 ID 목록 (선택, 기본값: ['INBOX'])
        
    Returns:
        messages: 이메일 목록
    """
    if label_ids is None:
        label_ids = ['INBOX']
    
    try:
        # 이메일 목록 조회
        result = service.users().messages().list(
            userId='me',
            labelIds=label_ids,
            q=query,
            maxResults=max_results
        ).execute()
        
        messages = result.get('messages', [])
        
        # 각 이메일의 상세 정보 조회
        detailed_messages = []
        for message in messages:
            msg = service.users().messages().get(
                userId='me', 
                id=message['id'],
                format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()
            
            detailed_messages.append(msg)
        
        return detailed_messages
    
    except HttpError as error:
        print(f'이메일 목록 조회 중 오류 발생: {error}')
        return []

def search_emails(service, query, max_results=10):
    """
    Gmail에서 특정 쿼리로 이메일을 검색합니다.
    
    Args:
        service: 구글 Gmail API 서비스 객체
        query: 검색 쿼리 (예: "from:example@gmail.com", "subject:안녕")
        max_results: 최대 조회 결과 수 (기본값: 10)
        
    Returns:
        messages: 검색된 이메일 목록
    """
    return list_emails(service, max_results=max_results, query=query)

def get_email_content(service, msg_id):
    """
    특정 이메일의 내용을 조회합니다.
    
    Args:
        service: 구글 Gmail API 서비스 객체
        msg_id: 이메일 ID
        
    Returns:
        content: 이메일 내용
    """
    try:
        message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        
        # 이메일 헤더 정보 추출
        headers = {}
        for header in message['payload']['headers']:
            headers[header['name']] = header['value']
        
        # 이메일 본문 추출
        parts = [message['payload']]
        body = ""
        
        while parts:
            part = parts.pop(0)
            
            if 'parts' in part:
                parts.extend(part['parts'])
            
            if 'body' in part and 'data' in part['body']:
                body_data = part['body']['data']
                body += base64.urlsafe_b64decode(body_data).decode('utf-8')
        
        return {
            'id': message['id'],
            'threadId': message['threadId'],
            'labelIds': message.get('labelIds', []),
            'snippet': message.get('snippet', ''),
            'headers': headers,
            'body': body
        }
    
    except HttpError as error:
        print(f'이메일 내용 조회 중 오류 발생: {error}')
        return None

def send_email(service, to, subject, body, cc=None, bcc=None, html=False):
    """
    이메일을 전송합니다.
    
    Args:
        service: 구글 Gmail API 서비스 객체
        to: 수신자 이메일 주소 (문자열 또는 목록)
        subject: 이메일 제목
        body: 이메일 본문
        cc: 참조 수신자 (선택)
        bcc: 숨은 참조 수신자 (선택)
        html: HTML 형식 여부 (기본값: False)
        
    Returns:
        sent_message: 전송된 이메일 정보
    """
    try:
        # 이메일 메시지 생성
        message = MIMEMultipart()
        message['to'] = to if isinstance(to, str) else ', '.join(to)
        message['subject'] = subject
        
        if cc:
            message['cc'] = cc if isinstance(cc, str) else ', '.join(cc)
        
        if bcc:
            message['bcc'] = bcc if isinstance(bcc, str) else ', '.join(bcc)
        
        # 본문 추가
        if html:
            msg = MIMEText(body, 'html')
        else:
            msg = MIMEText(body, 'plain')
        
        message.attach(msg)
        
        # 메시지를 base64url 인코딩
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        # 이메일 전송
        sent_message = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        
        return sent_message
    
    except HttpError as error:
        print(f'이메일 전송 중 오류 발생: {error}')
        return None

def modify_email_labels(service, msg_id, add_labels=None, remove_labels=None):
    """
    이메일의 라벨을 수정합니다.
    
    Args:
        service: 구글 Gmail API 서비스 객체
        msg_id: 이메일 ID
        add_labels: 추가할 라벨 목록 (선택)
        remove_labels: 제거할 라벨 목록 (선택)
        
    Returns:
        modified_message: 수정된 이메일 정보
    """
    if add_labels is None:
        add_labels = []
    
    if remove_labels is None:
        remove_labels = []
    
    try:
        modified_message = service.users().messages().modify(
            userId='me',
            id=msg_id,
            body={
                'addLabelIds': add_labels,
                'removeLabelIds': remove_labels
            }
        ).execute()
        
        return modified_message
    
    except HttpError as error:
        print(f'이메일 라벨 수정 중 오류 발생: {error}')
        return None

def format_email_for_display(message):
    """
    이메일을 표시용 형식으로 변환합니다.
    
    Args:
        message: Gmail API에서 반환한 이메일 객체
        
    Returns:
        formatted_email: 표시용으로 형식화된 이메일 정보
    """
    # 헤더 정보 추출
    headers = {}
    for header in message['payload']['headers']:
        name = header['name'].lower()
        if name in ['from', 'to', 'subject', 'date']:
            headers[name] = header['value']
    
    # 기본 정보
    formatted_email = {
        'id': message['id'],
        'threadId': message['threadId'],
        'snippet': message.get('snippet', '(내용 없음)'),
        'from': headers.get('from', '(발신자 없음)'),
        'to': headers.get('to', '(수신자 없음)'),
        'subject': headers.get('subject', '(제목 없음)'),
        'date': headers.get('date', '(날짜 없음)'),
        'labels': message.get('labelIds', [])
    }
    
    return formatted_email
