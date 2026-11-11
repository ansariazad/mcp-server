# 🔌 MCP Server — Model Context Protocol STDIO Server for Claude Desktop & Agents

> **Real weather alerts. Real forecasts. Real AI knowledge search. Over JSON-RPC 2.0 on stdin/stdout.**

A portable, production-grade MCP STDIO server exposing 3 tools — US weather alerts, 7-day forecasts, and AI engineering knowledge search. Compatible with **Claude Desktop**, **Cursor**, any MCP client, or spawnable as a subprocess from your own agent. No API key needed.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-JSON--RPC_2.0-F97316)](https://spec.modelcontextprotocol.io)
[![Claude Desktop](https://img.shields.io/badge/Claude_Desktop-Compatible-6366F1)](https://claude.ai/download)
[![NWS API](https://img.shields.io/badge/NWS_API-Free,_No_Key-22c55e)](https://www.weather.gov/documentation/services-web-api)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e)](LICENSE)
[![Stars](https://img.shields.io/github/stars/ansariazad/mcp-server?style=social)](https://github.com/ansariazad/mcp-server/stargazers)

---

## 📺 Demo

```
$ python3 04_mcp_server.py --self-test

━━━ MCP Server Self-Test ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Tool 1] get_alerts(state="CA")
         → "No active weather alerts for California."

[Tool 2] get_forecast(latitude=37.7749, longitude=-122.4194)
         → "Tuesday: Partly Cloudy. High near 68°F.
            Tuesday Night: Mostly clear. Low around 52°F.
            Wednesday: Sunny. High near 72°F."

[Tool 3] search_ai_playbooks(query="How does CRAG work?")
         → "Corrective RAG grades each retrieved chunk for
            relevance. Below-threshold chunks trigger a global
            fallback search to avoid hallucination..."

[✓] All 3 tools operational
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 📑 Table of Contents

- [Why This Exists](#-why-this-exists)
- [Tools Reference](#-tools-reference)
- [Protocol Flow](#-protocol-flow)
- [Quick Start](#-quick-start)
- [Claude Desktop Setup](#-claude-desktop-setup)
- [Cursor Setup](#-cursor-setup)
- [Use in Your Own Agent](#-use-in-your-own-agent)
- [Design Decisions](#-design-decisions)
- [Eval Results](#-eval-results)
- [Roadmap](#-roadmap)
- [References](#-references)

---

## 💡 Why This Exists

Most MCP server examples are toy demos. This one is **production-ready**:

| Feature | This Repo | Typical MCP Tutorial |
|---------|-----------|---------------------|
| Runs without MCP SDK installed | ✅ built-in fallback | ❌ SDK required |
| stdout clean (no log corruption) | ✅ stderr-only logging | ❌ often breaks JSON-RPC |
| Self-test mode | ✅ `--self-test` flag | ❌ |
| Claude Desktop config helper | ✅ `--print-mac-config` | ❌ |
| Real external API (NWS) | ✅ | ❌ usually mocked |
| Eval tested | ✅ | ❌ |

---

## 🛠️ Tools Reference

| Tool | Parameters | Returns | Source |
|------|-----------|---------|--------|
| `get_alerts` | `state: str` (2-letter, e.g. `"CA"`) | Active NWS weather alerts | `api.weather.gov/alerts` |
| `get_forecast` | `latitude: float`, `longitude: float` | 5-period detailed forecast | `api.weather.gov/points` |
| `search_ai_playbooks` | `query: str` | AI engineering knowledge | Local TF-IDF RAG index |

---

## 📡 Protocol Flow

```
MCP Client (Claude Desktop / Cursor / Your Agent)
        │
        │  stdin:  {"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}
        ▼
┌─────────────────────────────────────────────────────┐
│               04_mcp_server.py                       │
│                                                      │
│  STDIO transport (stdin → parse → dispatch → stdout)│
│  stderr → logging ONLY (stdout stays clean for JSON)│
│                                                      │
│  JSON-RPC 2.0 Dispatcher:                           │
│    tools/list  → returns registered tool schemas     │
│    tools/call  → invokes the named tool function     │
│       ├─ get_alerts(state)                          │
│       ├─ get_forecast(latitude, longitude)           │
│       └─ search_ai_playbooks(query)                 │
└─────────────────────────────────────────────────────┘
        │
        │  stdout: {"jsonrpc":"2.0","id":1,"result":{"content":[...]}}
        ▼
MCP Client receives tool result
```

---

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/ansariazad/mcp-server.git
cd mcp-server

# Self-test all tools
python3 04_mcp_server.py --self-test

# Start STDIO server (for Claude Desktop / Cursor)
python3 04_mcp_server.py

# Print Claude Desktop config snippet
python3 04_mcp_server.py --print-mac-config
```

---

## 🖥️ Claude Desktop Setup

**Step 1:** Get your config path:
```bash
python3 04_mcp_server.py --print-mac-config
```

**Step 2:** Add output to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "ai-engineering": {
      "command": "python3",
      "args": ["/absolute/path/to/mcp-server/04_mcp_server.py"],
      "cwd": "/absolute/path/to/mcp-server"
    }
  }
}
```

**Step 3:** Restart Claude Desktop — tools appear in the tool picker automatically.

> [!TIP]
> Use `uv run 04_mcp_server.py` as the command if you have `uv` installed — it auto-manages the Python environment.

---

## 🖱️ Cursor Setup

Add to `.cursor/mcp.json` in your project root:
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

## 🤖 Use in Your Own Agent

```python
import subprocess, json

proc = subprocess.Popen(
    ["python3", "04_mcp_server.py"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    stderr=subprocess.PIPE, text=True,
)

def call_tool(name: str, arguments: dict) -> str:
    req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
           "params": {"name": name, "arguments": arguments}}
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    resp = json.loads(proc.stdout.readline())
    return resp["result"]["content"][0]["text"]

print(call_tool("get_alerts", {"state": "NY"}))
print(call_tool("get_forecast", {"latitude": 40.71, "longitude": -74.00}))
print(call_tool("search_ai_playbooks", {"query": "What is RAG?"}))
```

---

## 🔧 Design Decisions

**stdout is sacred:**
```python
# ALL logging goes to stderr — stdout is reserved for JSON-RPC only
logging.basicConfig(stream=sys.stderr)
# → L1_MCP_Server_Zero_Stdout_Print_Calls eval: 0 print() calls found
```

**SDK + built-in fallback:**
```python
try:
    from mcp.server import MCPServer    # official SDK
except ImportError:
    try:
        from mcp import FastMCP         # FastMCP alternative
    except ImportError:
        pass                            # use PortableMCPServer (built-in)
```

---

## 🧪 Eval Results

Verified by [`ai-evals-suite`](https://github.com/ansariazad/ai-evals-suite):

| Assertion | Method | Result |
|-----------|--------|--------|
| `L1_MCP_Server_Zero_Stdout_Print_Calls` | AST parse, count `print()` nodes | ✅ PASS — 0 found |
| `L1_MCP_STDIO_End_To_End_Tool_Invocation` | Spawn subprocess, call 3 tools | ✅ PASS — all 3 responded |

---

## 🗺️ Roadmap

- [ ] Google Maps geocoding tool
- [ ] Wikipedia search tool
- [ ] Local filesystem tool (with path guardrail)
- [ ] MCP resources & prompts support
- [ ] SSE transport option

---

## 📚 References

| Resource | |
|----------|-|
| [MCP Specification](https://spec.modelcontextprotocol.io/) | Anthropic |
| [MCP Quickstart: Build a Server](https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server) | Anthropic |
| [NWS Web API](https://www.weather.gov/documentation/services-web-api) | National Weather Service |
| [Claude Desktop Integration](https://modelcontextprotocol.io/quickstart/user) | Anthropic |
| [JSON-RPC 2.0 Spec](https://www.jsonrpc.org/specification) | — |

---

## 🤝 Contributing

PRs welcome! Adding a new tool is simple — register it in `PortableMCPServer.__init__` and implement the function.

---

## ⭐ Support

Building with MCP? **Star the repo** to help others find a clean reference!

[![GitHub stars](https://img.shields.io/github/stars/ansariazad/mcp-server?style=for-the-badge)](https://github.com/ansariazad/mcp-server/stargazers)

---

## 📄 License

MIT © 2026

---

## 👤 Author

**Azad Ansari** — Python Developer & AI Engineer, Mumbai

[![GitHub](https://img.shields.io/badge/GitHub-ansariazad-181717?logo=github)](https://github.com/ansariazad)
[![Portfolio](https://img.shields.io/badge/Portfolio-ansariazad.github.io-blue)](https://ansariazad.github.io)
