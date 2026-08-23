from weather.cli import Place, contains_cjk, format_weather, is_administrative_result


def test_detects_chinese_place_names() -> None:
    assert contains_cjk("基隆")
    assert not contains_cjk("Keelung")


def test_rejects_businesses_from_geocoding_results() -> None:
    assert not is_administrative_result({"class": "amenity", "type": "hairdresser"})
    assert is_administrative_result({"category": "place", "type": "city"})
    assert is_administrative_result({"category": "boundary", "type": "administrative"})


def test_formats_traditional_chinese_weather() -> None:
    output = format_weather(
        Place("Taipei", 25.0, 121.5, "Taiwan"),
        {"current": {"weather_code": 0, "is_day": 1, "time": "2026-08-19T12:00", "temperature_2m": 30, "apparent_temperature": 35, "relative_humidity_2m": 70, "precipitation": 0, "wind_speed_10m": 12, "cloud_cover": 10}, "current_units": {"temperature_2m": "°C", "apparent_temperature": "°C", "relative_humidity_2m": "%", "precipitation": "mm", "wind_speed_10m": "km/h", "cloud_cover": "%"}, "timezone_abbreviation": "CST"},
        "zh-TW", False,
    )
    assert "即時天氣: 晴朗 (白天)" in output
    assert "氣溫: 30°C" in output


def test_formats_english_weather() -> None:
    output = format_weather(
        Place("London", 51.5, -0.1),
        {"current": {"weather_code": 61, "is_day": 0, "time": "2026-08-19T12:00", "temperature_2m": 18, "apparent_temperature": 18, "relative_humidity_2m": 80, "precipitation": 1, "wind_speed_10m": 10, "cloud_cover": 90}, "current_units": {}, "timezone": "Europe/London"},
        "en", False,
    )
    assert "Current weather: Slight rain (Nighttime)" in output
    assert "Location: London" in output
