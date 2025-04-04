import os
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from datetime import datetime

# .env 파일 로드
load_dotenv()

# 환경 변수에서 API 키와 API URL 가져오기
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
WEATHER_API_URL = os.getenv("WEATHER_API_URL")

# MCP 서버 초기화
mcp = FastMCP(
    "Weather",
    instructions="You are a weather assistant that provides real-time weather updates based on the user's location.",
    host="0.0.0.0",
    port=8005,
)


@mcp.tool()
async def get_weather(lat: float, lon: float) -> str:
    """
    사용자의 위도, 경도를 기반으로 현재 날씨 정보를 가져옴.

    Args:
        lat (float): 위도
        lon (float): 경도

    Returns:
        str: 현재 날씨 정보
    """
    try:
        # OpenWeatherMap API 요청
        params = {"lat": lat, "lon": lon, "appid": WEATHER_API_KEY, "units": "metric"}
        response = requests.get(WEATHER_API_URL, params=params)
        data = response.json()

        if response.status_code == 200:
            temp = data["main"]["temp"]
            weather_desc = data["weather"][0]["description"]
            location_name = data["name"]

            # 현재 날짜와 시간 (로컬 타임존 기준)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            return f"[{now}] {location_name}의 기온은 {temp}°C, 날씨는 {weather_desc}입니다."

        else:
            return "날씨 정보를 불러오는 데 실패했습니다. 다시 시도해주세요."

    except Exception as e:
        return f"날씨 정보를 가져오는 중 오류 발생: {str(e)}"

@mcp.tool()
async def get_user_location() -> dict:
    """
    사용자의 IP 주소를 기반으로 위도와 경도를 반환합니다.

    Returns:
        dict: {'lat': float, 'lon': float, 'city': str}
    """
    try:
        response = requests.get("http://ip-api.com/json/")
        data = response.json()

        if response.status_code == 200 and data["status"] == "success":
            return {"lat": data["lat"], "lon": data["lon"], "city": data["city"]}
        else:
            return {"error": "위치 정보를 불러오지 못했습니다."}
    except Exception as e:
        return {"error": f"위치 정보를 가져오는 중 오류 발생: {str(e)}"}



if __name__ == "__main__":
    mcp.run(transport="stdio")

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server with configuration
mcp = FastMCP(
    "Weather",  # Name of the MCP server
    instructions="You are a weather assistant that can answer questions about the weather in a given location.",  # Instructions for the LLM on how to use this tool
    host="0.0.0.0",  # Host address (0.0.0.0 allows connections from any IP)
    port=8005,  # Port number for the server
)


@mcp.tool()
async def get_weather(location: str) -> str:
    """
    Get current weather information for the specified location.

    This function simulates a weather service by returning a fixed response.
    In a production environment, this would connect to a real weather API.

    Args:
        location (str): The name of the location (city, region, etc.) to get weather for

    Returns:
        str: A string containing the weather information for the specified location
    """
    # Return a mock weather response
    # In a real implementation, this would call a weather API
    return f"It's always Sunny in {location}"


if __name__ == "__main__":
    # Start the MCP server with stdio transport
    # stdio transport allows the server to communicate with clients
    # through standard input/output streams, making it suitable for
    # local development and testing
    mcp.run(transport="stdio")
