import requests

def get_location():
    """
    IP 기반으로 위치 정보를 가져옵니다.
    https://ipinfo.io/json 을 호출하여 위도와 경도를 추출합니다.
    """
    try:
        response = requests.get("https://ipinfo.io/json")
        response.raise_for_status()
        data = response.json()
        loc = data.get("loc")
        if loc:
            lat_str, lon_str = loc.split(',')
            return float(lat_str), float(lon_str)
    except Exception as e:
        print("위치 정보를 가져오는 중 오류 발생:", e)
    return None, None

def get_weather(lat, lon, api_key):
    """
    OpenWeatherMap API를 사용하여 주어진 위도와 경도의 날씨 정보를 가져옵니다.
    'units' 파라미터는 섭씨 온도를 반환하도록 설정합니다.
    """
    try:
        url = "http://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": api_key,
            "units": "metric"  # 섭씨 온도
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("날씨 정보를 가져오는 중 오류 발생:", e)
    return None

def main():
    lat, lon = get_location()
    if lat is None or lon is None:
        print("위치 정보를 가져올 수 없습니다.")
        return

    print(f"감지된 위치: 위도 {lat}, 경도 {lon}")

    # OpenWeatherMap API 키를 입력하세요.
    api_key = "c3fc357863254c9e5183d866d09fd2d0"
    
    weather = get_weather(lat, lon, api_key)
    if weather:
        # 원하는 정보(예: 날씨 설명, 온도)를 출력합니다.
        description = weather["weather"][0]["description"]
        temperature = weather["main"]["temp"]
        print(f"현재 날씨: {description}, 온도: {temperature}°C")
    else:
        print("날씨 정보를 가져올 수 없습니다.")

if __name__ == "__main__":
    main()
