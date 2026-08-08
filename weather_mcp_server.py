"""
weather_mcp_server.py

MCP server exposing weather tools, following the same FastMCP +
streamable-HTTP pattern as Day 3's mcp_server/alpaca_mcp_server.py.

Tool functions are thin wrappers over weather_broker.py — no raw
`requests` calls live here. Every tool catches WeatherAPIError and
returns a clean error dict instead of letting a stack trace bubble
up to the agent.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from weather_broker import (
    WeatherAPIError,
    fetch_current_conditions,
    fetch_forecast,
)

mcp = FastMCP("weather-server")


@mcp.tool()
def get_current_weather(location: str) -> dict:
    """Get current weather conditions for a location.

    Args:
        location: Free-text location, e.g. "Chicago", "Austin, TX",
            "Denver, Colorado". City name is resolved via geocoding,
            so exact zip/lat-lon is not required.

    Returns:
        On success: dict with location, temperature_f, humidity_pct,
        wind_mph, conditions, observed_at.
        On failure: dict with a single "error" key describing what
        went wrong (bad location, upstream API outage). Never raises.
    """
    try:
        return fetch_current_conditions(location)
    except WeatherAPIError as e:
        return {"error": str(e)}


@mcp.tool()
def get_forecast(location: str, days: int = 3) -> dict:
    """Get a multi-day weather forecast for a location.

    Args:
        location: Free-text location, e.g. "Chicago", "Austin, TX".
        days: Number of days to forecast, 1-16 (default 3). Values
            outside this range are clamped.

    Returns:
        On success: dict with location and a "days" list, each entry
        containing date, high_f, low_f, precip_chance_pct, conditions.
        On failure: dict with a single "error" key. Never raises.
    """
    try:
        return fetch_forecast(location, days)
    except WeatherAPIError as e:
        return {"error": str(e)}


@mcp.tool()
def predict_umbrella_needed(location: str, date: str | None = None) -> dict:
    """Recommend whether to bring an umbrella, based on forecast precip chance.

    This is a derived judgment call, not a passthrough of raw API data:
    it pulls the forecast, finds the requested date (or the nearest
    upcoming day if no date given), and applies a fixed threshold —
    precipitation chance > 40% triggers a "bring an umbrella" call.
    Between 20-40% it hedges ("maybe"); under 20% it says no.

    Args:
        location: Free-text location, e.g. "Chicago", "Austin, TX".
        date: ISO date string (YYYY-MM-DD) within the next 16 days.
            If omitted, uses the next available forecast day.

    Returns:
        On success: dict with location, date, precip_chance_pct,
        recommendation ("yes"/"maybe"/"no"), and a one-line reason.
        On failure: dict with a single "error" key. Never raises.
    """
    try:
        forecast = fetch_forecast(location, days=16)
    except WeatherAPIError as e:
        return {"error": str(e)}

    day_entry = None
    if date:
        day_entry = next((d for d in forecast["days"] if d["date"] == date), None)
        if day_entry is None:
            return {"error": f"No forecast available for date '{date}' (out of 16-day range)"}
    else:
        day_entry = forecast["days"][0]

    pct = day_entry["precip_chance_pct"]
    if pct > 40:
        rec, reason = "yes", f"{pct}% chance of precipitation exceeds the 40% threshold"
    elif pct >= 20:
        rec, reason = "maybe", f"{pct}% chance of precipitation is borderline (20-40% range)"
    else:
        rec, reason = "no", f"{pct}% chance of precipitation is low"

    return {
        "location": forecast["location"],
        "date": day_entry["date"],
        "precip_chance_pct": pct,
        "recommendation": rec,
        "reason": reason,
    }


if __name__ == "__main__":
    # Streamable-HTTP transport, same as Day 3's Databricks App entrypoint.
    mcp.run(transport="streamable-http")
