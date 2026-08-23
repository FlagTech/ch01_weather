from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from weather import __version__

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
IP_LOCATION_URL = "https://ipapi.co/json/"
USER_AGENT = f"personal-weather/{__version__}"


TEXT = {
    "zh-TW": {
        "current_weather": "即時天氣",
        "location": "地點",
        "time": "時間",
        "temperature": "氣溫",
        "feels_like": "體感溫度",
        "humidity": "相對濕度",
        "precipitation": "降水",
        "wind": "風速",
        "cloud_cover": "雲量",
        "day": "白天",
        "night": "夜晚",
        "detected": "依 IP 推測",
        "not_found": "找不到「{location}」對應的地點。",
        "network_error": "無法連線至天氣服務，請確認網路連線後再試。",
        "ip_error": "無法透過 IP 判斷目前位置；請直接輸入地名。",
        "service_error": "天氣服務回傳了無法使用的資料。",
    },
    "en": {
        "current_weather": "Current weather",
        "location": "Location",
        "time": "Time",
        "temperature": "Temperature",
        "feels_like": "Feels like",
        "humidity": "Humidity",
        "precipitation": "Precipitation",
        "wind": "Wind speed",
        "cloud_cover": "Cloud cover",
        "day": "Daytime",
        "night": "Nighttime",
        "detected": "Estimated from IP",
        "not_found": "No location found for \"{location}\".",
        "network_error": "Could not reach the weather service. Check your network and try again.",
        "ip_error": "Could not estimate your location from IP. Please provide a location.",
        "service_error": "The weather service returned unusable data.",
    },
}

WEATHER_CODES = {
    0: ("晴朗", "Clear sky"), 1: ("大致晴朗", "Mainly clear"),
    2: ("局部多雲", "Partly cloudy"), 3: ("陰天", "Overcast"),
    45: ("有霧", "Fog"), 48: ("霧淞", "Depositing rime fog"),
    51: ("毛毛雨（弱）", "Light drizzle"), 53: ("毛毛雨（中）", "Moderate drizzle"),
    55: ("毛毛雨（強）", "Dense drizzle"), 56: ("凍毛毛雨（弱）", "Light freezing drizzle"),
    57: ("凍毛毛雨（強）", "Dense freezing drizzle"),
    61: ("小雨", "Slight rain"), 63: ("中雨", "Moderate rain"), 65: ("大雨", "Heavy rain"),
    66: ("凍雨（弱）", "Light freezing rain"), 67: ("凍雨（強）", "Heavy freezing rain"),
    71: ("小雪", "Slight snow"), 73: ("中雪", "Moderate snow"), 75: ("大雪", "Heavy snow"),
    77: ("雪粒", "Snow grains"), 80: ("陣雨（弱）", "Slight rain showers"),
    81: ("陣雨（中）", "Moderate rain showers"), 82: ("陣雨（強）", "Violent rain showers"),
    85: ("陣雪（弱）", "Slight snow showers"), 86: ("陣雪（強）", "Heavy snow showers"),
    95: ("雷雨", "Thunderstorm"), 96: ("雷雨伴隨小冰雹", "Thunderstorm with slight hail"),
    99: ("雷雨伴隨大冰雹", "Thunderstorm with heavy hail"),
}

# Official Taiwanese administrative-area names used for a country-scoped lookup.
# They avoid unrelated same-named points of interest and overseas locations.
TAIWAN_ALIASES = {
    "台北": "臺北市", "新北": "新北市", "桃園": "桃園市",
    "台中": "臺中市", "台南": "臺南市", "高雄": "高雄市",
    "基隆": "基隆市", "新竹": "新竹市", "嘉義": "嘉義市",
    "新竹縣": "新竹縣", "嘉義縣": "嘉義縣", "馬祖": "連江縣",
    "宜蘭": "宜蘭縣", "苗栗": "苗栗縣", "彰化": "彰化縣",
    "南投": "南投縣", "雲林": "雲林縣", "屏東": "屏東縣",
    "台東": "臺東縣", "花蓮": "花蓮縣", "澎湖": "澎湖縣",
    "金門": "金門縣", "連江": "連江縣",
}


class WeatherError(Exception):
    """An error that can be shown directly to a command-line user."""


@dataclass(frozen=True)
class Place:
    name: str
    latitude: float
    longitude: float
    country: str | None = None
    admin1: str | None = None

    @property
    def label(self) -> str:
        parts = [self.name]
        country = {"台湾": "臺灣", "台灣": "臺灣"}.get(self.country or "", self.country)
        if country and country not in parts:
            parts.append(country)
        return ", ".join(parts)


def get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=10) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise WeatherError("network_error") from exc


def contains_cjk(text: str) -> bool:
    """Return whether a query contains a CJK unified ideograph."""
    return any("\u4e00" <= character <= "\u9fff" for character in text)


def is_administrative_result(result: dict[str, Any]) -> bool:
    """Keep only city/area-like Nominatim results, never businesses or POIs."""
    category = result.get("category") or result.get("class")
    kind = result.get("type")
    if category == "boundary" and kind == "administrative":
        return True
    return category == "place" and kind in {
        "city", "town", "village", "municipality", "county", "state", "region",
    }


def find_taiwan_alias(query: str, language: str) -> Place | None:
    normalized = query.replace("臺", "台")
    official_name = TAIWAN_ALIASES.get(normalized) or TAIWAN_ALIASES.get(normalized.removesuffix("市").removesuffix("縣"))
    if not official_name:
        return None
    api_language = "zh" if language == "zh-TW" else "en"
    results = get_json(NOMINATIM_URL, {
        "q": official_name, "format": "jsonv2", "limit": 10,
        "addressdetails": 1, "countrycodes": "tw", "accept-language": api_language,
    })
    result = next((item for item in results if isinstance(item, dict) and is_administrative_result(item)), None) if isinstance(results, list) else None
    if result is None:
        return None
    try:
        country = "臺灣" if language == "zh-TW" else "Taiwan"
        name = query if language == "zh-TW" else (result.get("name") or result["display_name"].split(",", 1)[0])
        return Place(name, float(result["lat"]), float(result["lon"]), country)
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherError("service_error") from exc


def find_taiwan_place(query: str, language: str) -> Place | None:
    """Find a Taiwanese match for an ambiguous Chinese place name, if present."""
    api_language = "zh" if language == "zh-TW" else "en"
    results = get_json(NOMINATIM_URL, {
        "q": query,
        "format": "jsonv2",
        "limit": 10,
        "addressdetails": 1,
        "countrycodes": "tw",
        "accept-language": api_language,
    })
    if not isinstance(results, list):
        return None
    result = next((item for item in results if isinstance(item, dict) and is_administrative_result(item)), None)
    if result is None:
        return None
    try:
        address = result.get("address", {})
        name = result.get("name") or result["display_name"].split(",", 1)[0]
        country = address.get("country") or ("臺灣" if language == "zh-TW" else "Taiwan")
        return Place(name, float(result["lat"]), float(result["lon"]), country)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise WeatherError("service_error") from exc


def find_place(query: str, language: str) -> Place:
    api_language = "zh" if language == "zh-TW" else "en"
    # Names such as 桃園 also exist in China. For Chinese input, look for a
    # Taiwanese match first; only fall back to the worldwide search if absent.
    if contains_cjk(query):
        taiwan_alias = find_taiwan_alias(query, language)
        if taiwan_alias:
            return taiwan_alias
        taiwan_place = find_taiwan_place(query, language)
        if taiwan_place:
            return taiwan_place
    data = get_json(GEOCODING_URL, {"name": query, "count": 1, "language": api_language, "format": "json"})
    results = data.get("results", [])
    if results:
        result = results[0]
        try:
            return Place(result["name"], float(result["latitude"]), float(result["longitude"]), result.get("country"), result.get("admin1"))
        except (KeyError, TypeError, ValueError) as exc:
            raise WeatherError("service_error") from exc

    # Open-Meteo accepts many translated names, but not every Chinese place name.
    # Nominatim is a secondary geocoder so a query such as "台北" remains useful.
    fallback = get_json(NOMINATIM_URL, {"q": query, "format": "jsonv2", "limit": 10, "addressdetails": 1, "accept-language": api_language})
    if not isinstance(fallback, list):
        raise WeatherError("not_found")
    result = next((item for item in fallback if isinstance(item, dict) and is_administrative_result(item)), None)
    if result is None:
        raise WeatherError("not_found")
    try:
        address = result.get("address", {})
        name = result.get("name") or result["display_name"].split(",", 1)[0]
        return Place(name, float(result["lat"]), float(result["lon"]), address.get("country"))
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherError("service_error") from exc


def locate_by_ip() -> Place:
    data = get_json(IP_LOCATION_URL)
    try:
        return Place(data["city"], float(data["latitude"]), float(data["longitude"]), data.get("country_name"), data.get("region"))
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherError("ip_error") from exc


def get_weather(place: Place) -> dict[str, Any]:
    data = get_json(FORECAST_URL, {
        "latitude": place.latitude, "longitude": place.longitude,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,cloud_cover,wind_speed_10m",
        "timezone": "auto",
    })
    if not isinstance(data.get("current"), dict):
        raise WeatherError("service_error")
    return data


def format_weather(place: Place, data: dict[str, Any], language: str, was_detected: bool) -> str:
    t = TEXT[language]
    current = data["current"]
    units = data.get("current_units", {})
    code = int(current.get("weather_code", -1))
    condition = WEATHER_CODES.get(code, ("未知", "Unknown"))[0 if language == "zh-TW" else 1]
    phase = t["day"] if current.get("is_day") else t["night"]
    detected = f" ({t['detected']})" if was_detected else ""

    def measure(key: str) -> str:
        unit = units.get(key, "")
        return f"{current.get(key, '—')}{unit}"

    return "\n".join((
        f"{t['current_weather']}: {condition} ({phase})",
        f"{t['location']}: {place.label}{detected}",
        f"{t['time']}: {current.get('time', '—')} ({data.get('timezone_abbreviation', data.get('timezone', ''))})",
        f"{t['temperature']}: {measure('temperature_2m')}",
        f"{t['feels_like']}: {measure('apparent_temperature')}",
        f"{t['humidity']}: {measure('relative_humidity_2m')}",
        f"{t['precipitation']}: {measure('precipitation')}",
        f"{t['wind']}: {measure('wind_speed_10m')}",
        f"{t['cloud_cover']}: {measure('cloud_cover')}",
    ))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Look up current weather by place name or current IP location.")
    parser.add_argument("location", nargs="*", help="Place name in Chinese or English")
    parser.add_argument("--lang", choices=("zh-TW", "en"), default="zh-TW", help="Output language (default: zh-TW)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main() -> None:
    # Windows consoles can default to a legacy code page that cannot represent
    # all Chinese place names returned by a geocoder. UTF-8 keeps output intact.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    query = " ".join(args.location).strip()
    try:
        was_detected = not bool(query)
        place = find_place(query, args.lang) if query else locate_by_ip()
        print(format_weather(place, get_weather(place), args.lang, was_detected))
    except WeatherError as exc:
        message = TEXT[args.lang][str(exc)]
        if str(exc) == "not_found":
            message = message.format(location=query)
        print(message, file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
