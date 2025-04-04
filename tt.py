import asyncio
from mcp.client.stdio import stdio_client, StdioServerParameters

async def test_weather_tool(lat, lon):
    server_params = StdioServerParameters( 
        command= "python" , 
        args=["/Users/user/minithon/mcp_server_local.py"] 
    ) 

    async with stdio_client(server=server_params) as (read_stream, write_stream):
        print("✅ Connected to MCP server!")

lat, lon = 37.7749, -122.4194  # 샌프란시스코 좌표
asyncio.run(test_weather_tool(lat, lon))




