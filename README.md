# seo-gaca-mcp

**SEO GACA MCP** — **G**EO · **A**udit · **C**rawl · **A**nalyze

```
   ___   ___    ___         ___    ___    ___    ___
  / __| | __|  / _ \       / __|  /   \  / __|  /   \
  \__ \ | _|  | (_) |  _  | (_ | | - | | (__  | - |
  |___/ |___|  \___/  (_)  \___| |_|_|  \___|  |_|_|
         GEO · Audit · Crawl · Analyze
```

The most comprehensive SEO / Performance / GEO / UX MCP server.

**37 tools** in one MCP — technical SEO, Lighthouse performance (CWV + INP + TTFB), GEO (AI search optimization), content analysis, accessibility, security, UX audit, and more.

## What It Does

| Area | What GACA Measures |
|------|-------------------|
| **Performance** | Lighthouse scores (mobile + desktop), Core Web Vitals: LCP, FCP, CLS, TBT, SI, TTI, **INP**, **TTFB**. Fallback basic timing when Lighthouse unavailable |
| **Technical SEO** | Meta tags, robots.txt, sitemap, crawlability, HTTP headers, canonical, hreflang |
| **GEO** | AI search optimization — Princeton 9 methods, AI crawler robots.txt, AI citation readiness, optimization checklist |
| **Content** | Readability (Flesch-Kincaid, Gunning Fog, FRE), keyword density, E-E-A-T signals, topic clusters |
| **Schema** | JSON-LD validation vs Google requirements, 10 templates, Rich Results eligibility |
| **Security** | SSL/TLS audit, 7+ security headers, mixed content detection |
| **Links** | BFS crawl + internal link graph, broken link scan |
| **Accessibility** | WCAG 2.2 Level AA, color contrast, tap targets, font size |
| **UX** | Navigation, search, semantic structure, responsive design, mobile menu, skip links |
| **Competitors** | Side-by-side comparison (up to 3 URLs) with optional Lighthouse benchmarking |
| **International** | Hreflang validation, local SEO, NAP extraction |
| **Media** | Image/video SEO audit, format detection |
| **Reports** | Structured JSON + branded PDF (EN/PL) |

## Status

> **Alpha** — 37 tools fully implemented.
> Contributions welcome!

## Quick Start

```bash
# Install via pip
pip install seo-gaca-mcp

# Or via uv
uv pip install seo-gaca-mcp
```

## Usage with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gaca": {
      "command": "seo-gaca-mcp"
    }
  }
}
```

## Usage with Claude Code

```json
{
  "mcpServers": {
    "gaca": {
      "command": "uvx",
      "args": ["seo-gaca-mcp"]
    }
  }
}
```

## Docker

```bash
docker build -t seo-gaca-mcp .
# Test via MCP stdio:
echo '...' | docker run -i seo-gaca-mcp
```

## Tools Reference

### Performance (1)

| Tool | Description |
|------|-------------|
| `seo_check_performance` | Lighthouse scores + Core Web Vitals: LCP, FCP, CLS, TBT, SI, TTI, INP, TTFB (mobile + desktop) |

### Technical SEO (4)

| Tool | Description |
|------|-------------|
| `seo_audit_technical` | Full 13-step SEO + UX audit with 11-category scoring (1-10) |
| `seo_check_meta` | Quick meta tags analysis |
| `seo_check_crawlability` | Robots.txt + sitemap validation |
| `seo_check_headers` | HTTP response headers check |

### GEO — AI Search Optimization (7)

| Tool | Description |
|------|-------------|
| `seo_audit_geo` | Princeton 9 methods GEO audit |
| `seo_optimize_geo` | GEO optimization suggestions |
| `seo_check_ai_robots` | AI crawler robots.txt analysis (13 bots tracked) |
| `seo_generate_ai_robots` | Generate AI-optimized robots.txt |
| `seo_check_ai_visibility` | AI citation readiness check |
| `seo_get_geo_checklist` | GEO optimization checklist (P0/P1/P2) |
| `seo_get_seo_checklist` | Traditional SEO checklist (P0/P1/P2) |

### Content Analysis (3)

| Tool | Description |
|------|-------------|
| `seo_analyze_content` | Readability (FK, Fog, FRE) + keyword density |
| `seo_check_eeat` | E-E-A-T signal detection |
| `seo_audit_topic_clusters` | Topic cluster structure analysis |

### Schema / Structured Data (3)

| Tool | Description |
|------|-------------|
| `seo_validate_schema` | JSON-LD validation vs Google requirements |
| `seo_generate_schema` | Generate JSON-LD from 10 templates |
| `seo_check_rich_results` | Rich Result eligibility check |

### Security (2)

| Tool | Description |
|------|-------------|
| `seo_audit_ssl` | Full SSL/TLS audit (cert chain, TLS versions, ciphers) |
| `seo_check_security_headers` | 7+ security headers analysis |

### Links (2)

| Tool | Description |
|------|-------------|
| `seo_audit_links` | BFS crawl + internal link graph analysis |
| `seo_check_broken_links` | Quick broken link scan |

### Accessibility (1)

| Tool | Description |
|------|-------------|
| `seo_audit_accessibility` | WCAG 2.2 Level AA audit |

### International & Local (3)

| Tool | Description |
|------|-------------|
| `seo_check_hreflang` | Hreflang validation + reciprocal link check |
| `seo_audit_local` | Local SEO + NAP extraction |
| `seo_audit_media` | Image/video SEO audit |

### Competitors (1)

| Tool | Description |
|------|-------------|
| `seo_compare_competitors` | Side-by-side comparison (up to 3) with optional Lighthouse |

### Advanced (4)

| Tool | Description |
|------|-------------|
| `seo_check_js_rendering` | SPA/JS rendering detection (React, Next.js, Vue, Angular, Nuxt) |
| `seo_analyze_logs` | Server access log analysis |
| `seo_analyze_gsc` | Google Search Console CSV data analysis |
| `seo_compare_audits` | Audit diff and historical trends |

### Reporting (1)

| Tool | Description |
|------|-------------|
| `seo_generate_report` | Structured JSON report + branded PDF generation (EN/PL) |

### Utility (1)

| Tool | Description |
|------|-------------|
| `seo_get_config` | Server status, feature availability, version info |

## GEO: AI Search Optimization

GEO (Generative Engine Optimization) helps your content get cited by AI search engines (ChatGPT, Perplexity, SGE, Claude, Copilot).

Based on Princeton research (arXiv:2311.09735, KDD 2024):

| Method | Uplift | Description |
|--------|--------|-------------|
| Cite Sources | +40% | Authoritative references and citations |
| Statistics | +37% | Specific numbers, percentages, data |
| Quotations | +30% | Expert quotes with attribution |
| Authoritative Tone | +25% | Confident, expert language |
| Easy Language | +20% | Clear, accessible explanations |
| Technical Terms | +18% | Domain-specific vocabulary |
| Unique Words | +15% | Vocabulary diversity |
| Fluency | +15% | Natural flow, good structure |
| Keyword Stuffing | **-10%** | Actively avoid! |

## Performance Metrics

GACA measures all Core Web Vitals including the newest metrics:

| Metric | Full Name | Good | Needs Improvement | Poor |
|--------|-----------|------|-------------------|------|
| **LCP** | Largest Contentful Paint | <2.5s | 2.5–4.0s | >4.0s |
| **INP** | Interaction to Next Paint | <200ms | 200–500ms | >500ms |
| **CLS** | Cumulative Layout Shift | <0.1 | 0.1–0.25 | >0.25 |
| **FCP** | First Contentful Paint | <1.8s | 1.8–3.0s | >3.0s |
| **TTFB** | Time to First Byte | <800ms | 800–1800ms | >1800ms |
| **TBT** | Total Blocking Time | <200ms | 200–600ms | >600ms |
| **SI** | Speed Index | <3.4s | 3.4–5.8s | >5.8s |
| **TTI** | Time to Interactive | <3.8s | 3.8–7.3s | >7.3s |

## Configuration

```bash
# Optional: Lighthouse timeout (default: 120s)
export GACA_LIGHTHOUSE_TIMEOUT=120
```

## License

MIT License — Bartosz Gaca

---

Built with [MCP](https://modelcontextprotocol.io/) (Model Context Protocol) by Anthropic.
