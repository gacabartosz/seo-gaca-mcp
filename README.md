# seoleo-mcp

The most comprehensive SEO/UX/GEO MCP server.

**37 tools** covering technical SEO, content analysis, accessibility, security, and AI search optimization (GEO).

```
   _____ ______ ____  _      ______ ____
  / ____|  ____/ __ \| |    |  ____/ __ \
 | (___ | |__ | |  | | |    | |__ | |  | |  __  __ ___ ____
  \___ \|  __|| |  | | |    |  __|| |  | | |  \/  / __|| __ \
  ____) | |___| |__| | |____| |___| |__| | | |\/| \__ \| ___/
 |_____/|______\____/|______|______\____/  |_|  |_|___/|_|
```

## Status

> **Alpha** — 18 tools fully implemented, 15 planned (stubs returning helpful messages), 4 optional (DataForSEO API).
> Contributions welcome!

## Features

### Working now
- **Full 13-step SEO+UX audit** with 11-category scoring (1-10)
- **GEO**: Generative Engine Optimization for AI search (ChatGPT, Perplexity, SGE, Claude, Copilot)
- Princeton 9 methods for AI citation optimization (+40% visibility boost)
- AI crawler robots.txt analysis and generation (13 AI bots tracked)
- Lighthouse + Core Web Vitals (optional, graceful fallback)
- UX audit (navigation, search, semantics, responsive, overlays)
- **PDF report generation** (JSON structure + branded PDF via pdf-generator)

### Planned (in development)
- WCAG 2.2 accessibility audit
- Schema.org validation with JSON-LD templates
- Internal link graph analysis with BFS crawler
- SSL/TLS audit, security headers
- Content readability + E-E-A-T signals
- Side-by-side competitor comparison
- Server log analysis for crawl budget
- And more — see Tools Reference below

## Quick Start

```bash
# Install via pip
pip install seoleo-mcp

# Or via uv
uv pip install seoleo-mcp
```

## Usage with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "seoleo": {
      "command": "seoleo-mcp"
    }
  }
}
```

## Usage with Claude Code

```json
{
  "mcpServers": {
    "seoleo": {
      "command": "uvx",
      "args": ["seoleo-mcp"]
    }
  }
}
```

## Docker

```bash
docker build -t seoleo-mcp .
# Test via MCP stdio:
echo '...' | docker run -i seoleo-mcp
```

## Tools Reference

Legend: **Working** | *Planned*

### Technical SEO (5) — Working
| Tool | Description |
|------|-------------|
| `seo_audit_technical` | Full 13-step SEO+UX audit with scoring |
| `seo_check_meta` | Quick meta tags analysis |
| `seo_check_crawlability` | Robots.txt + sitemap validation |
| `seo_check_headers` | HTTP security headers check |
| `seo_check_performance` | Lighthouse CWV (mobile+desktop) |

### GEO — AI Search Optimization (7) — Working
| Tool | Description |
|------|-------------|
| `seo_audit_geo` | Princeton 9 methods GEO audit |
| `seo_optimize_geo` | GEO optimization suggestions |
| `seo_check_ai_robots` | AI crawler robots.txt analysis |
| `seo_generate_ai_robots` | Generate AI-optimized robots.txt |
| `seo_check_ai_visibility` | AI citation readiness check |
| `seo_get_geo_checklist` | GEO optimization checklist (P0/P1/P2) |
| `seo_get_seo_checklist` | Traditional SEO checklist (P0/P1/P2) |

### Reporting (1) — Working
| Tool | Description |
|------|-------------|
| `seo_generate_report` | JSON report + branded PDF generation (EN/PL) |

### Utility (1) — Working
| Tool | Description |
|------|-------------|
| `seo_get_config` | Server status and feature availability |

### Content Analysis (3) — *Planned*
| Tool | Description |
|------|-------------|
| `seo_analyze_content` | *Readability (FK, Fog, FRE) + keyword density* |
| `seo_check_eeat` | *E-E-A-T signal detection* |
| `seo_audit_topic_clusters` | *Topic cluster structure analysis* |

### Schema / Structured Data (3) — *Planned*
| Tool | Description |
|------|-------------|
| `seo_validate_schema` | *JSON-LD validation vs Google requirements* |
| `seo_generate_schema` | *Generate JSON-LD from 10 templates* |
| `seo_check_rich_results` | *Rich Result eligibility check* |

### Security (2) — *Planned*
| Tool | Description |
|------|-------------|
| `seo_audit_ssl` | *Full SSL/TLS audit* |
| `seo_check_security_headers` | *Security headers analysis* |

### Links (2) — *Planned*
| Tool | Description |
|------|-------------|
| `seo_audit_links` | *BFS crawl + link graph analysis* |
| `seo_check_broken_links` | *Quick broken link scan* |

### Other (5) — *Planned*
| Tool | Description |
|------|-------------|
| `seo_audit_accessibility` | *WCAG 2.2 Level AA audit* |
| `seo_check_hreflang` | *International SEO validation* |
| `seo_audit_local` | *Local SEO + NAP extraction* |
| `seo_audit_media` | *Image/video SEO audit* |
| `seo_compare_competitors` | *Side-by-side comparison (up to 3)* |

### Advanced (4) — *Planned*
| Tool | Description |
|------|-------------|
| `seo_check_js_rendering` | *SPA/JS rendering detection* |
| `seo_analyze_logs` | *Server log analysis* |
| `seo_analyze_gsc` | *Google Search Console data analysis* |
| `seo_compare_audits` | *Audit diff and trends* |

### DataForSEO (4, optional) — *Requires API key*
| Tool | Description |
|------|-------------|
| `seo_research_keywords` | *Keyword volume, CPC, competition* |
| `seo_analyze_serp` | *SERP analysis + features* |
| `seo_check_backlinks` | *Backlink profile* |
| `seo_analyze_domain` | *Domain overview* |

## GEO: AI Search Optimization

GEO (Generative Engine Optimization) helps your content get cited by AI search engines.

Based on Princeton research (arXiv:2311.09735, KDD 2024), these methods increase AI citation probability:

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

## Configuration

```bash
# Optional: DataForSEO API
export DATAFORSEO_LOGIN=your_login
export DATAFORSEO_PASSWORD=your_password

# Optional: Lighthouse timeout
export SEOLEO_LIGHTHOUSE_TIMEOUT=120
```

## License

MIT License - Bartosz Gaca

---

Built with MCP (Model Context Protocol) by Anthropic.
