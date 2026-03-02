# seoleo-mcp — Claude Code Conventions

## Architecture
- Python FastMCP server: `src/seoleo/server.py` (all @mcp.tool() definitions)
- `core/` — shared infrastructure (collectors, parsers, analyzers, lighthouse, config)
- `tools/` — 1 module per SEO domain (technical, content, schema, security, links, etc.)
- `geo/` — GEO (Generative Engine Optimization) — AI search citation optimization
- `api/` — optional external API clients (DataForSEO)
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
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n' | uv run seoleo-mcp 2>/dev/null
```

## Current State (v0.2.0)
- server.py: 37 tools registered
- core/: fully implemented (collectors, parsers, analyzers, lighthouse, config)
- tools/technical.py: fully implemented (13-step audit pipeline)
- tools/reporting.py: implemented (JSON report + PDF via pdf-generator)
- geo/: analyzer, optimizer, platforms, robots_ai, checklist — all implemented
- tools/*.py (14 remaining): stub implementations — see Priority below
- api/dataforseo.py: stub with graceful degradation

## Priority for Implementation
1. tools/content.py — readability scores (FK, Fog, FRE) + keyword density
2. tools/schema.py — JSON-LD validation against Google requirements
3. tools/security.py — SSL/TLS audit (cert chain, protocols, ciphers)
4. tools/links.py — BFS internal link crawler + broken link scan
5. tools/accessibility.py — WCAG 2.2 Level AA checks
6. tools/international.py — hreflang validation (HTML, HTTP, sitemap)
7. tools/local_seo.py — NAP extraction, LocalBusiness schema
8. tools/media.py — image/video SEO (formats, sizes, alt, srcset)
9. tools/competitor.py — side-by-side multi-site comparison
10. tools/topic_clusters.py — pillar/cluster detection from sitemap
11. tools/js_rendering.py — SPA detection, framework fingerprints
12. tools/logs.py — server log analysis, bot identification
13. tools/gsc.py — GSC CSV import, keyword cannibalization
14. tools/dashboard.py — audit diff and trend tracking

## Implementation Pattern
Each tool follows:
```
# 1. Use seoleo.core.collectors to fetch HTML/headers/robots
# 2. Use seoleo.core.parsers to extract structured data
# 3. Implement domain-specific analysis logic
# 4. Return dict: {status, url, timestamp, data, issues, score, recommendations}
# 5. NEVER print to stdout
# 6. Type hints on all public functions
```
