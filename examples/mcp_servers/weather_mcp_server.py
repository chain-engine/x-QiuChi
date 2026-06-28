"""
real weather query example using OpenWeatherMap API.

Run from the repository root:
    uv run examples/mcp_servers/weather_mcp_server/weather_mcp_real.py
"""

import os
import httpx
from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("RealWeatherService", json_response=True, port=8000)

# Get API key from environment variable
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")
if not OPENWEATHER_API_KEY:
    raise EnvironmentError("Please set the OPENWEATHER_API_KEY environment variable.")

BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


@mcp.tool()
def get_weather(city: str) -> dict:
    """
    Get current weather for a city using OpenWeatherMap API.

    Args:
        city (str): Name of the city (e.g., "London", "Beijing").

    Returns:
        dict: Contains temperature (°C), condition, humidity, and city name.
              On error, returns {"error": reason}.
    """
    try:
        params = {
            "q": city,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric"  # 返回摄氏度
        }
        response = httpx.get(BASE_URL, params=params, timeout=10.0)
        data = response.json()

        if response.status_code == 200:
            return {
                "city": data["name"],
                "temperature": round(data["main"]["temp"]),
                "condition": data["weather"][0]["description"].capitalize(),
                "humidity": data["main"]["humidity"]
            }
        elif response.status_code == 404:
            return {"error": f"City '{city}' not found."}
        else:
            return {"error": f"OpenWeather API error: {data.get('message', 'Unknown error')}"}

    except httpx.RequestError as e:
        return {"error": f"Network error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


@mcp.prompt()
def weather_outfit_advice(city: str) -> str:
    """Generate a prompt asking for outfit advice based on real-time weather."""
    return f"Given today's weather in {city}, what should I wear? Be specific and practical."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")