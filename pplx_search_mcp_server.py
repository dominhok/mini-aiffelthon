from mcp.server.fastmcp import FastMCP
from pplx_utils import ask_perplexity

# MCP 서버 초기화
mcp = FastMCP(
    "PerplexitySearch",  # MCP 서버 이름
    instructions="You are a Perplexity search assistant. Use this tool **only** when the user explicitly asks to 'search for', 'find information about', 'look up', or similar phrases indicating a clear web search intent. Do **not** use this tool for simple greetings, everyday conversation, or requests that can be handled by other available tools (like weather, email, calendar).",
    host="0.0.0.0",
    port=8006,
)

# MCP 도구로 등록된 함수
@mcp.tool()
async def perplexity_search(query: str) -> str:
    """
    Perplexity에 검색 질의를 보내고 결과를 반환합니다.

    Args:
        query (str): 사용자 질의
    Returns:
        str: Perplexity AI의 응답
    """
    return ask_perplexity(query)


if __name__ == "__main__":
    # stdio를 통해 MCP 서버 실행 (CLI나 다른 MCP 시스템에서 사용 가능)
    mcp.run(transport="stdio")
