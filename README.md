# 🔌 MCP Server — Model Context Protocol STDIO Server

A portable MCP STDIO server exposing weather alerts, forecasts, and AI playbook search — works with Claude Desktop, any MCP client, or directly via subprocess.

## ✨ Features

- **MCP STDIO protocol** — JSON-RPC 2.0 over stdin/stdout
- **3 tools exposed** — `get_alerts`, `get_forecast`, `search_ai_playbooks`
- **Live NWS API** — real weather data from `api.weather.gov` (no API key needed)
- **Claude Desktop compatible** — drop-in config provided
- **Portable fallback** — works with or without the official MCP SDK

## 🛠️ Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_alerts` | Weather alerts for a US state | `state: str` (e.g. `"CA"`) |
| `get_forecast` | 7-day weather forecast | `latitude: float`, `longitude: float` |
| `search_ai_playbooks` | Search RAG knowledge base | `query: str` |

## 🚀 Quick Start

```bash
pip install httpx mcp

# Run as standalone MCP server (STDIO mode)
python 04_mcp_server.py

# Or spawn from an agent/client via subprocess
```

## 🔧 Claude Desktop Config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ai-engineering": {
      "command": "uv",
      "args": ["run", "--with", "mcp[cli]", "mcp", "run", "04_mcp_server.py"],
      "cwd": "/path/to/this/repo"
    }
  }
}
```

## 📡 JSON-RPC 2.0 Protocol

```json
// Request
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_alerts","arguments":{"state":"CA"}}}

// Response
{"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"...alerts..."}]}}
```

## 🔗 References

- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [NWS API](https://www.weather.gov/documentation/services-web-api)
- [Claude Desktop MCP Docs](https://modelcontextprotocol.io/quickstart/user)

## 📄 License

MIT
