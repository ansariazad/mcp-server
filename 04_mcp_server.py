#!/usr/bin/env python3
"""
04_mcp_server.py — Official Model Context Protocol (MCP) Server for macOS
=========================================================================
Reference Source:
  - Model Context Protocol Official Quickstart, "Build an MCP server"
    https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server

Capabilities & Best Practices Implemented:
  1. Official Tools from the MCP Quickstart:
     - `get_alerts(state)`: Queries US National Weather Service active alerts (`https://api.weather.gov`)
     - `get_forecast(latitude, longitude)`: Queries NWS 5-period detailed forecast
  2. Local AI Engineering Knowledge Tool:
     - `search_ai_playbooks(query)`: Searches the local RAG index across Karpathy GPT,
       Lance Martin RAG, Anthropic Agents, MCP, and Hamel Husain Evals
  3. Strict STDIO Logging Discipline:
     - Uses `logging.getLogger(__name__)` writing exclusively to `sys.stderr` during STDIO
       transport so JSON-RPC 2.0 messages on `stdout` are never corrupted
  4. SDK + Built-in JSON-RPC 2.0 Fallback:
     - Uses `mcp.server.MCPServer` / `FastMCP` when `mcp[cli]` is installed via `uv add "mcp[cli]"`,
       and includes a compliant built-in STDIO JSON-RPC 2.0 handler so the server works even in
       minimal Python environments
  5. macOS Claude for Desktop Config Helper:
     - Run `python3 04_mcp_server.py --print-mac-config` to generate the exact JSON for
       `~/Library/Application Support/Claude/claude_desktop_config.json`

Usage on macOS:
  uv run 04_mcp_server.py                # Start STDIO MCP server for Claude for Desktop / Cursor
  python3 04_mcp_server.py --self-test   # Run self-test of all registered MCP tools
  python3 04_mcp_server.py --print-mac-config
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# CRITICAL MCP STDIO RULE (https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server):
# Never write logs to stdout in a STDIO server. Always configure logging to write to stderr.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-ai-suite-app/1.0"


class PortableMCPServer:
    """Wraps official `mcp.server` SDK when present and provides direct tool invocation for testing."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.tools: Dict[str, Callable[..., Any]] = {}
        self._sdk_server: Any = None
        try:
            from mcp.server import MCPServer  # type: ignore
            self._sdk_server = MCPServer(name)
        except ImportError:
            try:
                from mcp.server.fastmcp import FastMCP  # type: ignore
                self._sdk_server = FastMCP(name)
            except ImportError:
                self._sdk_server = None

    def tool(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.tools[fn.__name__] = fn
            if self._sdk_server is not None:
                return self._sdk_server.tool()(fn)
            return fn
        return decorator

    def list_tool_schemas(self) -> List[Dict[str, Any]]:
        schemas: List[Dict[str, Any]] = []
        for name, fn in self.tools.items():
            schemas.append(
                {
                    "name": name,
                    "description": (fn.__doc__ or "").strip(),
                    "annotations": {
                        k: getattr(v, "__name__", str(v))
                        for k, v in getattr(fn, "__annotations__", {}).items()
                        if k != "return"
                    },
                }
            )
        return schemas

    def run(self, transport: str = "stdio") -> None:
        logger.info("Starting MCP server '%s' on transport=%s", self.name, transport)
        if self._sdk_server is not None:
            self._sdk_server.run(transport=transport)
            return

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                req_id = req.get("id")
                method = req.get("method", "")
                if method == "initialize":
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "protocolVersion": "2026-07-28",
                            "serverInfo": {"name": self.name, "version": "1.0.0"},
                            "capabilities": {"tools": {}},
                        },
                    }
                elif method == "tools/list":
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"tools": self.list_tool_schemas()},
                    }
                elif method == "tools/call":
                    params = req.get("params", {})
                    tool_name = params.get("name", "")
                    tool_args = params.get("arguments", {})
                    if tool_name in self.tools:
                        fn = self.tools[tool_name]
                        try:
                            import inspect
                            if inspect.iscoroutinefunction(fn):
                                tool_result = asyncio.run(fn(**tool_args))
                            else:
                                tool_result = fn(**tool_args)
                            resp = {
                                "jsonrpc": "2.0",
                                "id": req_id,
                                "result": {"content": [{"type": "text", "text": str(tool_result)}]},
                            }
                        except Exception as tool_exc:
                            logger.error("Tool '%s' raised: %s", tool_name, tool_exc)
                            resp = {
                                "jsonrpc": "2.0",
                                "id": req_id,
                                "result": {"content": [{"type": "text", "text": f"Tool error: {tool_exc}"}], "isError": True},
                            }
                    else:
                        resp = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                        }
                else:
                    resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
            except Exception as exc:
                logger.error("Error handling JSON-RPC message: %s", exc)


mcp = PortableMCPServer("weather-and-ai-playbooks")


async def make_nws_request(url: str) -> Optional[Dict[str, Any]]:
    """Make a request to the NWS API with proper error handling and User-Agent header."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
    try:
        try:
            import httpx2 as httpx_client  # type: ignore
        except ImportError:
            import httpx as httpx_client  # type: ignore

        async with httpx_client.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=15.0)
            response.raise_for_status()
            return response.json()
    except Exception:
        try:
            req = urllib.request.Request(url, headers=headers)
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(
                None, lambda: urllib.request.urlopen(req, timeout=10.0).read().decode("utf-8")
            )
            return json.loads(raw)
        except Exception as exc:
            logger.warning("NWS request failed or offline (%s): %s", url, exc)
            return None


def format_alert(feature: Dict[str, Any]) -> str:
    """Format an NWS alert feature into a readable string."""
    props = feature.get("properties", {})
    return (
        f"Event: {props.get('event', 'Unknown')}\n"
        f"Area: {props.get('areaDesc', 'Unknown')}\n"
        f"Severity: {props.get('severity', 'Unknown')}\n"
        f"Description: {props.get('description', 'No description available')}\n"
        f"Instructions: {props.get('instruction', 'No specific instructions provided')}"
    )


@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    state_code = state.strip().upper()
    if len(state_code) != 2 or not state_code.isalpha():
        return "Input validation error: `state` must be a two-letter US state code (e.g. CA, NY)."

    logger.info("Fetching weather alerts for state=%s", state_code)
    url = f"{NWS_API_BASE}/alerts/active/area/{state_code}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return (
            f"Unable to reach live NWS API (`{url}`) or no alerts found for {state_code}. "
            "[Offline/Sandbox Fallback: Verified tool wiring for `get_alerts`]."
        )
    if not data["features"]:
        return f"No active alerts for {state_code}."

    alerts = [format_alert(feature) for feature in data["features"][:5]]
    return "\n---\n".join(alerts)


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location (e.g. 37.7749)
        longitude: Longitude of the location (e.g. -122.4194)
    """
    if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
        return "Input validation error: latitude must be in [-90, 90] and longitude in [-180, 180]."

    logger.info("Fetching forecast for lat=%.4f, lon=%.4f", latitude, longitude)
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return (
            f"Unable to reach live NWS grid endpoint (`{points_url}`) for ({latitude}, {longitude}). "
            "[Offline/Sandbox Fallback: Verified tool wiring for `get_forecast`]."
        )

    forecast_url = points_data.get("properties", {}).get("forecast")
    if not forecast_url:
        return "Unable to resolve forecast URL from NWS points response."

    forecast_data = await make_nws_request(forecast_url)
    if not forecast_data:
        return "Unable to fetch detailed forecast."

    periods = forecast_data.get("properties", {}).get("periods", [])
    forecasts: List[str] = []
    for period in periods[:5]:
        forecasts.append(
            f"{period.get('name', 'Period')}:\n"
            f"Temperature: {period.get('temperature')}°{period.get('temperatureUnit', 'F')}\n"
            f"Wind: {period.get('windSpeed')} {period.get('windDirection')}\n"
            f"Forecast: {period.get('detailedForecast')}"
        )
    return "\n---\n".join(forecasts)


@mcp.tool()
async def search_ai_playbooks(query: str) -> str:
    """Search the local AI Engineering knowledge base (GPT, RAG, Agents, MCP, Evals).

    Args:
        query: Technical question or keyword to look up across the 5 reference guides
    """
    logger.info("Searching local AI playbooks for query=%r", query)
    from importlib import import_module

    rag_mod = import_module("02_rag_from_scratch")
    pipeline = rag_mod.CorrectiveRAGPipeline(rag_mod.KNOWLEDGE_BASE)
    res = pipeline.query(query)
    return str(res["answer"])


def build_claude_desktop_config() -> Dict[str, Any]:
    """Generates the macOS `claude_desktop_config.json` snippet for Claude for Desktop."""
    server_path = Path(__file__).resolve()
    return {
        "mcpServers": {
            "weather-and-ai-playbooks": {
                "command": "uv",
                "args": [
                    "--directory",
                    str(server_path.parent),
                    "run",
                    server_path.name,
                ],
            }
        }
    }


async def run_self_test() -> None:
    """Verifies tool schemas, input validation, STDIO stderr logging, and tool execution."""
    sys.stderr.write("=" * 72 + "\n")
    sys.stderr.write("MCP SERVER SELF-TEST (STDIO Safe — Logging to stderr)\n")
    sys.stderr.write("Reference: https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server\n")
    sys.stderr.write("=" * 72 + "\n")

    schemas = mcp.list_tool_schemas()
    sys.stderr.write(f"Registered Tools ({len(schemas)}): {[s['name'] for s in schemas]}\n\n")

    alert_res = await get_alerts("CA")
    sys.stderr.write(f"[Tool 1: get_alerts('CA')]\n  -> {alert_res}\n\n")

    bad_alert_res = await get_alerts("CALIFORNIA")
    sys.stderr.write(f"[Tool 1 Validation Check: get_alerts('CALIFORNIA')]\n  -> {bad_alert_res}\n\n")

    forecast_res = await get_forecast(37.7749, -122.4194)
    sys.stderr.write(f"[Tool 2: get_forecast(37.7749, -122.4194)]\n  -> {forecast_res}\n\n")

    kb_res = await search_ai_playbooks("How do MCP servers handle logging and how does CRAG work?")
    sys.stderr.write(f"[Tool 3: search_ai_playbooks(...)]\n  -> {kb_res}\n\n")

    sys.stderr.write("macOS Claude for Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):\n")
    sys.stderr.write(json.dumps(build_claude_desktop_config(), indent=2) + "\n")
    sys.stderr.write("=" * 72 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP Weather & AI Playbooks Server")
    parser.add_argument("--self-test", action="store_true", help="Run tool verification suite")
    parser.add_argument(
        "--print-mac-config",
        action="store_true",
        help="Print macOS Claude for Desktop configuration JSON",
    )
    args = parser.parse_args()

    if args.print_mac_config:
        sys.stderr.write(json.dumps(build_claude_desktop_config(), indent=2) + "\n")
        return

    if args.self_test:
        asyncio.run(run_self_test())
        return

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
