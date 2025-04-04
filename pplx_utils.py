import os
import httpx
from dotenv import load_dotenv

# .env 파일에서 API 키 로드
load_dotenv()
api_key = os.getenv("PERPLEXITY_API_KEY")
if not api_key:
    raise ValueError("PERPLEXITY_API_KEY 환경 변수가 설정되지 않았습니다.")

# API 관련 설정
HEADERS = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
API_URL = "https://api.perplexity.ai/chat/completions"
MODEL = "sonar"  # 가장 저렴한 온라인 모델


def ask_perplexity(question: str, system_prompt: str = "You are an AI assistant.") -> str:
    """
    Perplexity API에 질문을 보내고 응답을 문자열로 반환합니다.

    Args:
        question (str): 사용자 질문
        system_prompt (str): 시스템 역할 정의 메시지 (기본값: 일반 어시스턴트)

    Returns:
        str: Perplexity AI의 응답 텍스트
    """
    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
    }

    try:
        response = httpx.post(API_URL, headers=HEADERS, json=data, timeout=30.0)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as http_err:
        return f"❌ HTTP 오류 발생: {http_err.response.status_code} - {http_err.response.text}"
    except Exception as e:
        return f"❌ 예외 발생: {str(e)}"
