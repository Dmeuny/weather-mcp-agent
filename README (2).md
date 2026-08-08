# Weather Prediction MCP Server + Agent

## Architecture

```
User question
     │
     ▼
Databricks Agent Bricks agent  ──external MCP──►  weather_mcp_server.py (FastMCP, streamable-HTTP)
     │                                                    │
     ▼                                             weather_broker.py
Final answer                                      (Open-Meteo HTTP calls)
```

Same split as Day 3's Alpaca pattern: the MCP layer stays thin, all
HTTP/parsing logic lives in the broker module.

## Weather API + auth

**Open-Meteo** — no signup, no API key, ~10,000 calls/day (non-commercial
use). Chosen specifically to avoid secrets management for v1; the
`_secret()` pattern from `alpaca_broker.py` is documented above in case
a keyed API (WeatherAPI.com, NWS alerts) gets layered in later.

## Tools

| Tool | Purpose |
|---|---|
| `get_current_weather(location)` | Current temp, humidity, wind, conditions |
| `get_forecast(location, days)` | Multi-day high/low/precip forecast (1-16 days) |
| `predict_umbrella_needed(location, date)` | Derived recommendation: >40% precip chance → "yes", 20-40% → "maybe", <20% → "no" |

## Setup

1. `cd mcp_server && pip install -r requirements.txt`
2. Deploy as a Databricks App: `databricks apps deploy` (or via the UI, pointing at this folder — same steps as Day 3's `mcp_server/`)
3. Register the deployed app URL as an external MCP server in Agent Bricks (Day 3 README, "Register the MCP server as an external MCP")
4. Build the Agent Bricks agent, attach this MCP server as a tool, and set the system prompt below.

## Agent system prompt

```
You are a weather assistant. You have access to three tools:
get_current_weather, get_forecast, and predict_umbrella_needed.

Rules:
- Never state a temperature, forecast, or recommendation you did not
  get from a tool call. If you haven't called a tool yet for the
  location in question, call one before answering.
- If a tool returns an "error" key, tell the user what went wrong
  (e.g. "I couldn't resolve that location") and ask them to clarify
  rather than guessing or making up data.
- For umbrella/packing/travel-prep questions, use
  predict_umbrella_needed and explain the reasoning (precip %) in
  your answer, not just yes/no.
- For multi-day questions ("this weekend", "next 3 days"), use
  get_forecast and summarize day by day.
```

## Demo (fill in after deploying)

1. **"Will it rain in Chicago tomorrow?"** → [paste tool calls + answer]
2. **"Should I bring a jacket to Austin this weekend?"** → [paste tool calls + answer]
3. **"What's the weather like in Denver right now?"** → [paste tool calls + answer]
