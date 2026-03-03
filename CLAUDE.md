# SEO GACA MCP — Claude Code Conventions
# GEO · Audit · Crawl · Analyze

## Architecture
- Python FastMCP server: `src/gaca/server.py` (all @mcp.tool() definitions)
- `core/` — shared infrastructure (collectors, parsers, analyzers, lighthouse, config)
- `tools/` — 1 module per SEO domain (technical, content, schema, security, links, etc.)
- `geo/` — GEO (Generative Engine Optimization) — AI search citation optimization
- `data/` — bundled reference data (JSON/TXT)

## Key Patterns
- Every tool function: `def tool_name(params) -> dict` returning `{"status": "success/error", "data": {...}, ...}`
- NEVER print() to stdout — breaks MCP stdio transport. Use `logging.getLogger(__name__)`
- All HTTP fetching through `core/collectors.py`
- All HTML parsing through `core/parsers.py`
- Graceful degradation: missing Lighthouse → fallback timing, missing API key → helpful message
- Type hints on all public functions

## Build & Test
```bash
uv run pytest tests/ -x         # Run tests
uv run ruff check src/          # Lint
# Verify MCP tools registration:
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n' | uv run seo-gaca-mcp 2>/dev/null
```

## Current State (v0.3.0)
- 37 tools registered and fully implemented
- Performance: Lighthouse + CWV + INP + TTFB
- core/: collectors, parsers, analyzers, lighthouse, config
- tools/: technical, content, schema, security, links, accessibility, international, local_seo, media, competitor, topic_clusters, js_rendering, logs, gsc, dashboard, reporting
- geo/: analyzer, optimizer, platforms, robots_ai, checklist

## Implementation Pattern
Each tool follows:
```
# 1. Use gaca.core.collectors to fetch HTML/headers/robots
# 2. Use gaca.core.parsers to extract structured data
# 3. Implement domain-specific analysis logic
# 4. Return dict: {status, url, timestamp, data, issues, score, recommendations}
# 5. NEVER print to stdout
# 6. Type hints on all public functions
```
