# seo-gaca-mcp — Ralph Autonomous Dev Loop

## You Are
Claude Code working autonomously on seo-gaca-mcp — a Python FastMCP server with 37 SEO/UX/GEO audit tools.

## Project Context
- MCP server is WORKING (37 tools registered)
- core/ modules are DONE (collectors, parsers, analyzers, lighthouse, config)
- tools/technical.py is DONE (full 13-step SEO+UX audit pipeline)
- tools/reporting.py is DONE (JSON report + PDF generation)
- geo/ modules are DONE (analyzer, optimizer, platforms, robots_ai, checklist)
- 14 tools/*.py files are STUBS returning "not_implemented"

## Current Objectives

### Phase 1: Implement remaining tool modules
For each stub in `src/gaca/tools/`, implement real logic. Use the existing `gaca.core.*` modules (collectors, parsers, analyzers) as building blocks. Look at `tools/technical.py` as the reference implementation pattern.

Priority order:

1. **`content.py`** — `analyze_content(url, keyword, language)` + `check_eeat(url)`
   - Readability: Flesch-Kincaid, Gunning Fog, Flesch Reading Ease
   - Keyword density analysis (if keyword provided)
   - Word count, sentence analysis, paragraph structure
   - E-E-A-T: author info, citations, expertise signals, dates, about page links
   - Use: `core.collectors.fetch_html()`, `core.parsers.parse_meta_tags()`, BeautifulSoup

2. **`schema.py`** — `validate_schema(url)` + `generate_schema(type, data)` + `check_rich_results(url)`
   - Parse JSON-LD and microdata from HTML
   - Validate required/recommended fields per Google's requirements for 12 types
   - Generate JSON-LD from templates (Article, Product, FAQ, HowTo, LocalBusiness, Organization, Event, Recipe, VideoObject, Person)
   - Rich Result eligibility check
   - Use: `core.parsers.parse_schema()`

3. **`security.py`** — `audit_ssl(url, check_mixed)` + `check_security_headers(url)`
   - SSL: cert chain, validity, issuer, expiry, SAN, protocol versions, HSTS
   - Security headers: HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, X-XSS-Protection
   - Use: `core.collectors.fetch_ssl_info()`, `core.collectors.fetch_headers()`

4. **`links.py`** — `audit_links(url, max_pages, max_depth)` + `check_broken_links(url)`
   - BFS crawler: follow internal links up to max_pages/max_depth
   - Build link graph: orphan pages, link depth distribution
   - Anchor text distribution analysis
   - Broken link scan: check internal + external for 4xx/5xx
   - Use: `core.collectors.fetch_html()`, `core.parsers.parse_links()`

5. **`accessibility.py`** — `audit_accessibility(url)`
   - WCAG 2.2 Level AA checks: alt text, form labels, heading hierarchy
   - Landmarks, skip navigation, ARIA attributes
   - Language declaration, keyboard navigability signals
   - Color contrast (basic check via inline styles)
   - Use: `core.collectors.fetch_html()`, BeautifulSoup

6. **`international.py`** — `check_hreflang(url, check_reciprocal, sitemap_url)`
   - Parse hreflang from HTML link tags, HTTP headers, sitemap
   - Validate ISO 639-1 language codes, ISO 3166-1 region codes
   - Check reciprocal links and x-default
   - Detect canonical conflicts with hreflang
   - Use: `core.collectors.fetch_html()`, `core.parsers.parse_meta_tags()`

7. **`local_seo.py`** — `audit_local(url)`
   - NAP extraction (Name, Address, Phone) from page content
   - LocalBusiness schema validation
   - Google Maps embed detection
   - Contact page analysis
   - Use: `core.parsers.parse_schema()`, BeautifulSoup, regex for phone/address

8. **`media.py`** — `audit_media(url)`
   - Image audit: formats (WebP/AVIF detection), file sizes, lazy-loading, srcset/sizes
   - Alt text quality check (empty, generic, keyword-stuffed)
   - Video: VideoObject schema, OG video tags
   - Use: `core.parsers.parse_images()`, `core.parsers.parse_schema()`

9. **`competitor.py`** — `compare_competitors(client_url, competitor_urls, include_lighthouse)`
   - Fetch and parse all URLs (client + up to 3 competitors)
   - Side-by-side comparison: meta, headings, schema, content metrics, headers
   - Win/loss analysis per category
   - Optional Lighthouse scores
   - Use: all core modules

10. **`topic_clusters.py`** — `audit_topic_clusters(url, sitemap_url)`
    - Parse sitemap for URL structure
    - Group URLs by path segments (detect clusters)
    - Identify pillar pages vs cluster pages
    - Internal linking gaps between clusters
    - Use: `core.collectors.fetch_sitemap()`, `core.parsers.parse_links()`

11. **`js_rendering.py`** — `check_js_rendering(url)`
    - Framework fingerprints: React, Vue, Angular, Next.js, Nuxt, Svelte
    - Compare raw HTML vs what JS would render (noscript fallback)
    - Client-side routing detection (pushState, hashbang)
    - Lazy-load patterns, hydration markers
    - Use: `core.collectors.fetch_html()`, BeautifulSoup

12. **`logs.py`** — `analyze_logs(log_content, domain)`
    - Parse Apache/Nginx combined log format
    - Bot identification: Googlebot, Bingbot, AI bots (GPTBot, ClaudeBot etc.)
    - Status code distribution, crawl frequency
    - Most crawled URLs, crawl budget estimation

13. **`gsc.py`** — `analyze_gsc(csv_content, domain)`
    - Parse GSC exported CSV (queries, pages, clicks, impressions, CTR, position)
    - Top queries analysis, CTR vs position benchmarks
    - Keyword cannibalization detection (same keyword, multiple pages)
    - Declining pages, opportunity keywords

14. **`dashboard.py`** — `compare_audits(domain, date1, date2)`
    - Load two audit JSON snapshots
    - Diff: improvements, regressions, new issues, resolved issues
    - Score trends per category

### Phase 2: Data files
Create reference data in `src/gaca/data/`:
- `google_schema_requirements.json` — required/recommended fields per schema type
- `bot_signatures.json` — User-Agent patterns for search engine bots
- `wcag_rules.json` — WCAG 2.2 AA rule definitions
- `stopwords_en.txt`, `stopwords_pl.txt` — for keyword analysis

### Phase 3: Tests
Write pytest tests in `tests/` for each implemented module.
Use `respx` for mocking HTTP requests.

## Implementation Rules
- ONE module per loop iteration
- Keep function signatures matching what server.py expects
- All imports from `gaca.core.*` (no sys.path hacks)
- Return dict: `{status, url, timestamp, data, issues, score, recommendations}`
- NEVER print to stdout (breaks MCP stdio)
- Commit after each successful module

## Build & Verify
After implementing each module:
```bash
uv run python -c "from gaca.tools.{module} import {function}; print('OK')"
# Verify all 37 tools still register:
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n' | uv run seo-gaca-mcp 2>/dev/null | python3 -c "import sys,json;[print(json.dumps(json.loads(l))) for l in sys.stdin if l.strip()]" | grep -c '"name"'
# Run tests:
uv run pytest tests/ -x
```

---RALPH_STATUS---
STATUS: active
EXIT_SIGNAL: none
WORK_TYPE: implementation
FILES_MODIFIED: none yet
PHASE: 1
NEXT_TASK: Implement tools/content.py
---END_RALPH_STATUS---
