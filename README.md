# 나만의 비서 나비: LangGraph + MCP 에이전트

[![Korean](https://img.shields.io/badge/Language-한국어-red)](README.md)
[![GitHub](https://img.shields.io/badge/GitHub-langgraph--mcp--agents-black?logo=github)](https://github.com/Minhokei/langgraph-mcp-agents) <!-- 저장소 URL을 실제 URL로 변경하세요 -->
[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-≥3.10-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-0.2.0-orange)](https://github.com/Minhokei/langgraph-mcp-agents) <!-- 버전은 적절히 수정하세요 -->

![project demo](./assets/project-demo.png)
<!-- 실제 나비 비서 스크린샷으로 교체하는 것이 좋습니다. -->

## 프로젝트 개요

**나만의 비서 나비(Nabi)**는 LangGraph ReAct 에이전트와 MCP(Model Context Protocol)를 활용하여 사용자의 일상을 돕는 AI 비서 애플리케이션입니다. Streamlit으로 구축된 웹 인터페이스를 통해 사용자와 상호작용하며, Upstage Solar LLM을 기반으로 작동합니다.

나비는 MCP를 통해 다양한 도구와 연동됩니다:
*   **날씨 정보**: 사용자의 현재 위치를 기반으로 날씨를 알려줍니다 (`mcp_server_local.py`).
*   **Google Workspace 연동**: Google 계정 인증을 통해 Gmail 확인/검색/전송 및 Google Calendar 일정 조회/추가 기능을 제공합니다 (`gsuite_mcp_server.py`).
*   **정보 검색 및 브리핑**: Perplexity AI를 사용하여 웹 검색을 수행하고, 사용자가 설정한 관심 분야에 대한 최신 정보 보고서를 제공합니다 (`pplx_search_mcp_server.py`).

## 주요 기능

*   **대화형 AI 비서**: Upstage Solar LLM 기반의 자연스러운 대화 기능
*   **날씨 정보 조회**: 현재 위치 기반 실시간 날씨 정보 제공
*   **Google 계정 연동 (OAuth)**:
    *   Gmail: 받은 편지함 확인, 이메일 검색, 이메일 작성 및 전송
    *   Google Calendar: 다가오는 일정 확인, 새로운 일정 추가
*   **관심 분야 보고서**: 설정된 관심사에 대한 최신 정보 자동 브리핑
*   **직접 웹 검색**: Perplexity AI를 통한 실시간 정보 검색
*   **Streamlit 기반 웹 인터페이스**: 사용자 친화적인 UI 제공

## 아키텍처

![project architecture](./assets/architecture.png)
<!-- 아키텍처 다이어그램이 현재 구조를 정확히 반영하는지 확인하세요. Upstage, Perplexity 등이 포함되면 좋습니다. -->

1.  **Streamlit UI (`app_KOR.py`)**: 사용자와 상호작용하는 웹 프론트엔드.
2.  **LangGraph ReAct Agent**: 사용자의 요청을 이해하고 적절한 도구를 선택 및 실행하는 핵심 로직 (Upstage Solar LLM 사용).
3.  **MCP 클라이언트 (`langchain-mcp-adapters`)**: LangGraph 에이전트와 MCP 서버 간의 통신을 중개.
4.  **MCP 서버 (`mcp_server_*.py`)**: 특정 기능을 제공하는 독립적인 프로세스.
    *   `weather`: 날씨 정보 제공 (OpenWeatherMap API 사용)
    *   `gsuite`: Gmail 및 Google Calendar 기능 제공 (Google API 사용)
    *   `pplx_search`: 웹 검색 기능 제공 (Perplexity AI API 사용)
    *   **참고:** 현재 구현에서는 Streamlit 앱이 시작될 때 `MultiServerMCPClient`를 통해 이 서버들을 로컬에서 `stdio` 전송 방식으로 자동 실행하려고 시도합니다.

## 설치

1.  **저장소 클론**:
    ```bash
    git clone https://github.com/Minhokei/langgraph-mcp-agents.git # 실제 저장소 URL로 변경하세요
    cd langgraph-mcp-agents
    ```

2.  **가상 환경 생성 및 의존성 설치 (`uv` 사용 권장)**:
    *   `uv`가 설치되어 있지 않다면 먼저 설치합니다: `pip install uv`
    *   가상 환경을 생성하고 활성화합니다:
        ```bash
        uv venv
        source .venv/bin/activate  # Linux/macOS
        # .venv\Scripts\activate  # Windows
        ```
    *   `requirements.txt` 파일의 의존성을 설치합니다:
        ```bash
        uv pip install -r requirements.txt
        ```

## 사전 준비: API 키 및 Google Cloud 설정

애플리케이션을 실행하기 전에 필요한 API 키와 Google Cloud 설정을 완료해야 합니다.

1.  **Google Cloud 설정**:
    *   Google Cloud Console ([https://console.cloud.google.com/](https://console.cloud.google.com/))에서 새 프로젝트를 생성하거나 기존 프로젝트를 사용합니다.
    *   **Gmail API**와 **Google Calendar API**를 검색하여 "사용 설정"합니다.
    *   "API 및 서비스" > "사용자 인증 정보"로 이동합니다.
    *   "+ 사용자 인증 정보 만들기" > "OAuth 클라이언트 ID"를 선택합니다.
    *   "애플리케이션 유형"으로 **"웹 애플리케이션"**을 선택합니다.
    *   "승인된 리디렉션 URI" 섹션에서 "+ URI 추가"를 클릭하고 다음 URI를 **모두** 추가합니다(하나는 로컬 개발용, 다른 하나는 배포 시 필요할 수 있음):
        *   `http://localhost:8501/callback`
        *   (배포 시 사용할 URI, 예: `https://your-app-domain.com/callback`)
    *   "만들기"를 클릭하면 클라이언트 ID와 클라이언트 보안 비밀이 표시됩니다. **JSON 다운로드** 버튼을 클릭하여 `credentials.json` 파일을 다운로드하고 프로젝트 루트 디렉토리에 저장합니다.
    *   "OAuth 동의 화면"을 설정해야 할 수도 있습니다. 테스트 사용자를 추가하거나 앱을 게시해야 합니다.

2.  **API 키 준비**:
    *   **Upstage AI API 키**: [https://console.upstage.ai/](https://console.upstage.ai/) 에서 가입하고 API 키를 발급받습니다.
    *   **OpenWeatherMap API 키**: [https://openweathermap.org/](https://openweathermap.org/) 에서 가입하고 API 키를 발급받습니다 (무료 플랜 가능).
    *   **Perplexity AI API 키**: [https://docs.perplexity.ai/](https://docs.perplexity.ai/) 에서 가입하고 API 키를 발급받습니다.

## `.env` 파일 설정

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고, `.env.example` 파일을 참고하여 다음과 같이 API 키와 설정을 입력합니다.

```dotenv
# .env

# Upstage API Key
UPSTAGE_API_KEY="여러분의 Upstage API 키"

# OpenWeatherMap API Key
WEATHERMAP_API_KEY="여러분의 OpenWeatherMap API 키"

# Perplexity AI API Key
PERPLEXITY_API_KEY="여러분의 Perplexity AI API 키"

# Google OAuth Credentials File Path
# Google Cloud Console에서 다운로드한 credentials.json 파일의 경로
# 예: GOOGLE_CREDENTIALS_PATH="./credentials.json" (프로젝트 루트에 저장한 경우)
GOOGLE_CREDENTIALS_PATH="여러분의 credentials.json 파일 경로"

# Google OAuth Redirect URI
# 로컬 개발 시: http://localhost:8501/callback
# 배포 시: 배포된 앱의 callback URI (Google Cloud Console에 등록한 URI와 일치해야 함)
REDIRECT_URI="http://localhost:8501/callback"

# (선택) LangSmith 추적 설정
# LANGSMITH_TRACING="true"
# LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
# LANGSMITH_API_KEY="여러분의 LangSmith API 키"
# LANGSMITH_PROJECT="여러분의 LangSmith 프로젝트 이름"
```

**중요**: `.gitignore` 파일에 `.env`와 `credentials.json`, `token.pickle`, `interests.pickle`이 포함되어 있는지 확인하여 민감 정보가 Git에 커밋되지 않도록 하세요.

## 사용법

1.  **가상 환경 활성화**:
    ```bash
    source .venv/bin/activate  # Linux/macOS
    # .venv\Scripts\activate  # Windows
    ```

2.  **Streamlit 애플리케이션 실행**:
    ```bash
    streamlit run app_KOR.py
    ```
    앱이 실행되면 자동으로 MCP 서버들(`weather`, `gsuite`, `pplx_search`)을 로컬 프로세스로 실행하려고 시도합니다.

3.  **웹 브라우저에서 앱 접속**: 터미널에 표시된 URL(기본값: `http://localhost:8501`)로 접속합니다.

4.  **Google 계정 연동 (필요시)**:
    *   사이드바의 "Google 계정 연동" 섹션에서 "Google 계정 연동하기" 버튼을 클릭합니다.
    *   Google 로그인 및 동의 화면을 진행합니다.
    *   성공적으로 연동되면 사이드바에 "✅ Google 계정이 연동되었습니다." 메시지가 표시됩니다. 이제 Gmail 및 캘린더 관련 기능을 사용할 수 있습니다.

5.  **관심 분야 설정 (선택)**:
    *   사이드바의 "관심 분야 설정" 섹션에서 관심사를 입력하고 "관심 분야 저장" 버튼을 클릭합니다.
    *   저장 시 자동으로 해당 관심사에 대한 보고서 생성이 시작됩니다.

6.  **나비 비서와 대화**:
    *   "🦋 나비 비서" 탭 하단의 입력창에 질문이나 요청을 입력합니다.
    *   나비는 질문을 분석하고 필요에 따라 연동된 도구(날씨, Gmail, 캘린더, 검색)를 사용하여 답변을 생성합니다.

7.  **관심분야 보고서 확인**:
    *   "🔍 관심분야 보고서" 탭으로 이동합니다.
    *   관심 분야가 설정되어 있다면 자동으로 생성된 최신 정보 브리핑을 확인할 수 있습니다.
    *   하단의 입력창을 통해 직접 원하는 키워드로 웹 검색을 수행할 수도 있습니다.

## 배포 관련 참고사항

현재 설정 (`transport: "stdio"`를 사용하여 로컬 MCP 서버 실행)은 **Streamlit Cloud와 같은 표준 플랫폼에 직접 배포하기에는 적합하지 않습니다.** 이러한 플랫폼은 보통 단일 앱 프로세스 실행을 가정하며, 앱 내에서 별도의 백그라운드 서버 프로세스를 안정적으로 실행하는 것을 지원하지 않을 수 있습니다.

실제 서비스 배포를 위해서는 다음과 같은 접근 방식을 고려해야 합니다:

1.  **MCP 서버 분리 및 네트워크 통신**:
    *   각 MCP 서버(`weather`, `gsuite`, `pplx_search`)를 별도의 서버(예: Docker 컨테이너, 클라우드 함수, VM 등)에 배포합니다.
    *   `app_KOR.py`의 `mcp_config` 설정을 수정하여 `stdio` 대신 `tcp` 전송 방식을 사용하고, 각 MCP 서버의 네트워크 주소와 포트를 지정합니다.
2.  **Docker Compose 활용**: 전체 애플리케이션 스택(Streamlit 앱, MCP 서버들)을 Docker Compose로 묶어 컨테이너화하여 배포합니다. 이는 의존성 관리와 프로세스 관리에 용이합니다.

## 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다. 자세한 내용은 [LICENSE](https://opensource.org/licenses/MIT) 파일을 참고하세요.

## 참고 및 기반 프로젝트

이 "나비 비서" 애플리케이션은 LangGraph와 MCP(Model Context Protocol)를 통합하는 방법을 보여주는 [teddylee777/langgraph-mcp-agents](https://github.com/teddylee777/langgraph-mcp-agents) 프로젝트를 기반으로 개발되었습니다. 해당 프로젝트는 MCP 도구를 Streamlit 인터페이스를 통해 관리하고 LangGraph ReAct 에이전트와 상호작용하는 기본적인 틀을 제공합니다.

주요 참고 라이브러리는 다음과 같습니다:
*   `langchain-mcp-adapters`: [https://github.com/langchain-ai/langchain-mcp-adapters](https://github.com/langchain-ai/langchain-mcp-adapters)

