"""
weather_broker.py

Adapter module for the Open-Meteo API. Mirrors the role of alpaca_broker.py
from Day 3: owns all HTTP calls + response parsing so the MCP tool layer
stays thin (no raw `requests` calls inside @mcp.tool functions).

Open-Meteo requires no API key and no signup, so there's no secrets
handling here. If you later add WeatherAPI.com or NWS as a second source,
follow the same `_secret()` / WorkspaceClient().secrets.get_secret()
pattern Day 3 used for the Alpaca keys.
"""

from __future__ import annotations

import requests
from typing import Any

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

_WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


class WeatherAPIError(Exception):
    """Raised on geocoding failures, API outages, or malformed responses."""


def _wmo_to_text(code: int) -> str:
    return _WMO_CODES.get(code, f"Unknown conditions (code {code})")


def geocode(location: str) -> dict[str, Any]:
    """Resolve a free-text location (city, city+state, city+country) to lat/lon.

    Raises WeatherAPIError if the location can't be resolved or the
    upstream API fails, rather than letting a bad location silently
    propagate into a garbage forecast.
    """
    try:
        resp = requests.get(
            GEOCODE_URL, params={"name": location, "count": 1}, timeout=10
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise WeatherAPIError(f"Geocoding service unavailable: {e}") from e

    data = resp.json()
    results = data.get("results")
    if not results:
        raise WeatherAPIError(f"Could not resolve location: '{location}'")

    top = results[0]
    return {
        "name": top["name"],
        "region": top.get("admin1", ""),
        "country": top.get("country", ""),
        "latitude": top["latitude"],
        "longitude": top["longitude"],
        "timezone": top.get("timezone", "auto"),
    }


def fetch_current_conditions(location: str) -> dict[str, Any]:
    """Current temperature, conditions, humidity, wind for a location."""
    geo = geocode(location)
    try:
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": geo["latitude"],
                "longitude": geo["longitude"],
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": geo["timezone"],
            },
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise WeatherAPIError(f"Forecast service unavailable: {e}") from e

    cur = resp.json().get("current")
    if not cur:
        raise WeatherAPIError("Malformed response from forecast API (no 'current' block)")

    return {
        "location": f"{geo['name']}, {geo['region'] or geo['country']}",
        "temperature_f": cur["temperature_2m"],
        "humidity_pct": cur["relative_humidity_2m"],
        "wind_mph": cur["wind_speed_10m"],
        "conditions": _wmo_to_text(cur["weather_code"]),
        "observed_at": cur["time"],
    }


def fetch_forecast(location: str, days: int = 3) -> dict[str, Any]:
    """Multi-day forecast: high/low temp, precip chance, conditions per day."""
    days = max(1, min(days, 16))  # Open-Meteo caps daily forecast at 16 days
    geo = geocode(location)
    try:
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": geo["latitude"],
                "longitude": geo["longitude"],
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                "temperature_unit": "fahrenheit",
                "timezone": geo["timezone"],
                "forecast_days": days,
            },
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise WeatherAPIError(f"Forecast service unavailable: {e}") from e

    daily = resp.json().get("daily")
    if not daily:
        raise WeatherAPIError("Malformed response from forecast API (no 'daily' block)")

    days_out = []
    for i, date in enumerate(daily["time"]):
        days_out.append({
            "date": date,
            "high_f": daily["temperature_2m_max"][i],
            "low_f": daily["temperature_2m_min"][i],
            "precip_chance_pct": daily["precipitation_probability_max"][i],
            "conditions": _wmo_to_text(daily["weather_code"][i]),
        })

    return {
        "location": f"{geo['name']}, {geo['region'] or geo['country']}",
        "days": days_out,
    }
