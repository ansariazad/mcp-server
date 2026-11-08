# MCP Server

**mcp-server** is a portable Model Context Protocol (MCP) STDIO server that exposes real-world tools — US weather alerts, 7-day forecasts, and AI engineering knowledge search — over JSON-RPC 2.0 on stdin/stdout. Compatible with Claude Desktop, Cursor, any MCP client, or spawnable as a subprocess from your own agent code.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-JSON--RPC_2.0-orange)
![Claude Desktop](https://img.shields.io/badge/Claude_Desktop-Compatible-blueviolet)
![NWS API](https://img.shields.io/badge/NWS_API-No_Key_Required-green)
![License](https://img.shields.io/badge/License-MIT-green)

---

## What is this?

A production-grade MCP STDIO server implementing the official [MCP Quickstart](https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server) tools plus a local AI knowledge search tool. It uses the official `mcp[cli]` SDK when installed and falls back to a hand-built JSON-RPC 2.0 STDIO handler so it works in minimal Python environments too.

Critical design decisions:
- **stdout is sacred** — all logs write to `stderr` only via `logging.basicConfig(stream=sys.stderr)`, keeping JSON-RPC messages on stdout uncorrupted
- **Dual SDK + fallback** — tries `mcp.server.MCPServer` → `FastMCP` → built-in STDIO handler in order
- **Self-test mode** — `--self-test` flag invokes all tools directly for quick verification

---

## Key Features

- **`get_alerts(state)`** — queries [api.weather.gov](https://api.weather.gov) for active NWS weather alerts for any US state; no API key needed
- **`get_forecast(lat, lon)`** — fetches 5-period detailed weather forecast from NWS for any lat/lon coordinate
- **`search_ai_playbooks(query)`** — searches a local RAG index covering GPT architecture, RAG techniques, Anthropic agent patterns, MCP protocol, and LLM evals
- **Claude Desktop config helper** — run `--print-mac-config` to generate the exact JSON snippet to paste into `claude_desktop_config.json`
- **Self-test mode** — `--self-test` calls all 3 tools and prints results directly (no MCP client needed)
- **STDIO logging discipline** — zero `print()` calls on stdout; verified by Level 1 eval assertion

---

## MCP Protocol Flow

```
MCP Client (Claude Desktop / Agent)
        │
        │   stdin: {"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}
        ▼
┌─────────────────────────────────────────────────┐
│              04_mcp_server.py                    │
│                                                  │
│  PortableMCPServer                               │
│    ├─ tools/list    → registered tool schemas    │
│    └─ tools/call    → invoke tool function       │
│         ├─ get_alerts(state)                     │
│         ├─ get_forecast(latitude, longitude)     │
│         └─ search_ai_playbooks(query)            │
└─────────────────────────────────────────────────┘
        │
        │   stdout: {"jsonrpc":"2.0","id":1,"result":{"content":[...]}}
        ▼
MCP Client receives tool result
```

---

## Tools Reference

| Tool | Parameters | Returns | API Used |
|------|-----------|---------|----------|
| `get_alerts` | `state: str` (2-letter, e.g. `"CA"`) | Active weather alerts text | `api.weather.gov/alerts/active?area={state}` |
| `get_forecast` | `latitude: float`, `longitude: float` | 5-period forecast text | `api.weather.gov/points/{lat},{lon}/forecast` |
| `search_ai_playbooks` | `query: str` | Relevant AI engineering knowledge chunks | Local RAG index (TF-IDF) |

---

## Prerequisites

**Python 3.11+** required.

### macOS
```bash
brew install python@3.11

# Install MCP SDK (optional — built-in fallback works without it)
pip install "mcp[cli]"
# Or with uv:
uv add "mcp[cli]"
```

### Windows / Linux
```bash
pip install "mcp[cli]"
```

> [!TIP]
> The server works with zero dependencies using the built-in JSON-RPC 2.0 fallback handler. Install `mcp[cli]` only if you want the official SDK features (resource subscriptions, prompts, etc.).

---

## Quick Start

### 1. Run as standalone MCP STDIO server
```bash
# With uv (recommended for Claude Desktop)
uv run 04_mcp_server.py

# With python directly
python3 04_mcp_server.py
```

### 2. Self-test all tools
```bash
python3 04_mcp_server.py --self-test
```

**Expected output:**
```
[self-test] get_alerts(CA):
  No active weather alerts for CA

[self-test] get_forecast(37.7749, -122.4194):
  Tuesday: Partly cloudy. High near 68°F...

[self-test] search_ai_playbooks("How does CRAG work?"):
  CRAG grades retrieved documents for relevance, discards below-threshold chunks...
```

### 3. Print Claude Desktop config
```bash
python3 04_mcp_server.py --print-mac-config
```

---

## Claude Desktop Integration

Add this to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ai-engineering": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "mcp[cli]",
        "mcp",
        "run",
        "/path/to/mcp-server/04_mcp_server.py"
      ],
      "cwd": "/path/to/mcp-server"
    }
  }
}
```

Then restart Claude Desktop — the tools will appear in the tool picker.

> [!NOTE]
> Replace `/path/to/mcp-server` with the actual path where you cloned this repo.

---

## Cursor / VS Code Integration

Add to `.cursor/mcp.json` or the Cursor MCP settings:

```json
{
  "mcpServers": {
    "ai-engineering": {
      "command": "python3",
      "args": ["/path/to/mcp-server/04_mcp_server.py"]
    }
  }
}
```

---

## Spawn from Your Own Agent

```python
import subprocess, json

proc = subprocess.Popen(
    ["python3", "04_mcp_server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    cwd="/path/to/mcp-server"
)

# Call get_alerts
req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
       "params": {"name": "get_alerts", "arguments": {"state": "CA"}}}
proc.stdin.write(json.dumps(req) + "\n")
proc.stdin.flush()

response = json.loads(proc.stdout.readline())
print(response["result"]["content"][0]["text"])
```

---

## Environment Variables

No API keys required. The NWS API is free and public.

| Variable | Description | Default |
|----------|-------------|---------|
| *(none required)* | — | — |

---

## File Structure

```
mcp-server/
├── 04_mcp_server.py     # MCP STDIO server (tools + JSON-RPC 2.0 fallback)
├── setup_and_run_mac.sh # macOS setup script
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
├── .gitignore
└── README.md
```

---

## Eval Results

Tested by [`ai-evals-suite`](https://github.com/ansariazad/ai-evals-suite):

| Assertion | Result |
|-----------|--------|
| `L1_MCP_Server_Zero_Stdout_Print_Calls` | ✅ PASS — zero print() on stdout |
| `L1_MCP_STDIO_End_To_End_Tool_Invocation` | ✅ PASS — all 3 tools called & responded |

---

## References

- [MCP Specification](https://spec.modelcontextprotocol.io/) — Anthropic
- [MCP Quickstart: Build a Server](https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server)
- [NWS Web API](https://www.weather.gov/documentation/services-web-api) — National Weather Service
- [Claude Desktop MCP Docs](https://modelcontextprotocol.io/quickstart/user)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)

---

## Contributing

Pull requests welcome! Suggested additions: Google Maps geocoding tool, Wikipedia search, local file system tools.

---

## License

MIT © 2026

---

## Author

**Azad Ansari** — [GitHub](https://github.com/ansariazad) | [AutoShorts](https://github.com/ansariazad/AutoShorts)
