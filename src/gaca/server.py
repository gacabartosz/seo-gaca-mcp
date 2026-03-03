"""SEO GACA MCP — GEO · Audit · Crawl · Analyze.

37 tools: technical SEO, performance (Lighthouse + CWV + INP + TTFB),
GEO (AI search optimization), accessibility, security, UX, and more.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("seo-gaca-mcp")


# ============================================================
# Technical SEO (5 tools)
# ============================================================


@mcp.tool()
def seo_audit_technical(
    url: str,
    include_subpages: bool = True,
    max_subpages: int = 15,
    include_ux: bool = True,
) -> dict:
    """Full 13-step SEO+UX audit: meta tags, headings, images, links, schema,
    robots.txt, sitemap, Lighthouse (mobile+desktop), security headers, hosting,
    UX analysis. Returns scored results (11 categories, 1-10) with prioritized
    recommendations, TOP 5 problems, and quick wins."""
    from gaca.tools.technical import run_full_audit
    return run_full_audit(url, include_subpages, max_subpages, include_ux)


@mcp.tool()
def seo_check_meta(url: str) -> dict:
    """Quick meta tag analysis: title, description, canonical, viewport,
    Open Graph, Twitter Cards, hreflang, favicon, robots directive."""
    from gaca.tools.technical import check_meta
    return check_meta(url)


@mcp.tool()
def seo_check_crawlability(url: str) -> dict:
    """Robots.txt parsing and sitemap discovery/validation.
    Checks for sitemap index support and common sitemap paths."""
    from gaca.tools.technical import check_crawlability
    return check_crawlability(url)


@mcp.tool()
def seo_check_headers(url: str) -> dict:
    """HTTP response headers analysis: security headers (HSTS, CSP,
    X-Content-Type-Options, X-Frame-Options, Referrer-Policy,
    Permissions-Policy), server info, caching."""
    from gaca.tools.technical import check_headers
    return check_headers(url)


@mcp.tool()
def seo_check_performance(url: str, form_factor: str = "both") -> dict:
    """Lighthouse scores and Core Web Vitals (LCP, CLS, TBT, FCP, SI, TTI).
    Runs mobile+desktop by default. Falls back to basic load-time if
    Lighthouse is unavailable. form_factor: 'mobile', 'desktop', or 'both'."""
    from gaca.tools.technical import check_performance
    return check_performance(url, form_factor)


# ============================================================
# Content Analysis (3 tools)
# ============================================================


@mcp.tool()
def seo_analyze_content(
    url: str, keyword: str = "", language: str = "auto"
) -> dict:
    """Content quality analysis: readability scores (Flesch-Kincaid, Gunning Fog,
    Flesch Reading Ease), keyword density, word count, sentence analysis.
    Optionally targets a specific keyword for density calculation."""
    from gaca.tools.content import analyze_content
    return analyze_content(url, keyword, language)


@mcp.tool()
def seo_check_eeat(url: str) -> dict:
    """E-E-A-T signal detection: author information, citations/references,
    expertise signals, trust indicators, publication dates, about pages."""
    from gaca.tools.content import check_eeat
    return check_eeat(url)


@mcp.tool()
def seo_audit_topic_clusters(url: str, sitemap_url: str = "") -> dict:
    """Topic cluster structure analysis from sitemap: pillar pages detection,
    cluster pages grouping, internal linking gaps between clusters."""
    from gaca.tools.topic_clusters import audit_topic_clusters
    return audit_topic_clusters(url, sitemap_url)


# ============================================================
# Schema / Structured Data (3 tools)
# ============================================================


@mcp.tool()
def seo_validate_schema(url: str) -> dict:
    """JSON-LD and microdata validation against Google requirements.
    Checks required/recommended fields for 12 schema types.
    Reports Rich Result eligibility."""
    from gaca.tools.schema import validate_schema
    return validate_schema(url)


@mcp.tool()
def seo_generate_schema(schema_type: str, data: dict) -> dict:
    """Generate JSON-LD schema markup from templates.
    Supported types: Article, Product, FAQ, HowTo, LocalBusiness,
    Organization, Event, Recipe, VideoObject, Person.
    Provide data dict with required fields for the chosen type."""
    from gaca.tools.schema import generate_schema
    return generate_schema(schema_type, data)


@mcp.tool()
def seo_check_rich_results(url: str) -> dict:
    """Quick Rich Result eligibility check: identifies which schema types
    are present and whether they qualify for rich snippets in Google."""
    from gaca.tools.schema import check_rich_results
    return check_rich_results(url)


# ============================================================
# Security (2 tools)
# ============================================================


@mcp.tool()
def seo_audit_ssl(url: str, check_mixed_content: bool = False) -> dict:
    """Full SSL/TLS audit: certificate chain, validity, issuer, expiry,
    protocol versions (TLS 1.0-1.3), cipher suites, HSTS, OCSP stapling.
    Optionally checks for mixed content."""
    from gaca.tools.security import audit_ssl
    return audit_ssl(url, check_mixed_content)


@mcp.tool()
def seo_check_security_headers(url: str) -> dict:
    """Security header analysis: HSTS, CSP, X-Frame-Options,
    X-Content-Type-Options, Referrer-Policy, Permissions-Policy,
    X-XSS-Protection. Returns pass/fail per header with recommendations."""
    from gaca.tools.security import check_security_headers
    return check_security_headers(url)


# ============================================================
# Links (2 tools)
# ============================================================


@mcp.tool()
def seo_audit_links(url: str, max_pages: int = 50, max_depth: int = 3) -> dict:
    """Internal link graph analysis via BFS crawl: orphan pages, broken links,
    anchor text distribution, approximate PageRank, link depth distribution."""
    from gaca.tools.links import audit_links
    return audit_links(url, max_pages, max_depth)


@mcp.tool()
def seo_check_broken_links(url: str) -> dict:
    """Quick broken link scan for a single page — checks both internal
    and external links for 4xx/5xx responses."""
    from gaca.tools.links import check_broken_links
    return check_broken_links(url)


# ============================================================
# Accessibility (1 tool)
# ============================================================


@mcp.tool()
def seo_audit_accessibility(url: str) -> dict:
    """WCAG 2.2 Level AA audit: alt text, form labels, heading hierarchy,
    landmarks, skip navigation, color contrast, keyboard navigability,
    ARIA attributes, language declaration."""
    from gaca.tools.accessibility import audit_accessibility
    return audit_accessibility(url)


# ============================================================
# International SEO (1 tool)
# ============================================================


@mcp.tool()
def seo_check_hreflang(
    url: str, check_reciprocal: bool = True, sitemap_url: str = ""
) -> dict:
    """Hreflang validation: HTML link tags, HTTP headers, sitemap xhtml:link.
    Validates reciprocal links, x-default, ISO 639-1 language codes,
    ISO 3166-1 region codes, canonical conflicts."""
    from gaca.tools.international import check_hreflang
    return check_hreflang(url, check_reciprocal, sitemap_url)


# ============================================================
# Local SEO (1 tool)
# ============================================================


@mcp.tool()
def seo_audit_local(url: str) -> dict:
    """Local SEO audit: NAP (Name, Address, Phone) extraction and consistency,
    LocalBusiness schema validation, Google Maps embed detection,
    contact page analysis."""
    from gaca.tools.local_seo import audit_local
    return audit_local(url)


# ============================================================
# Media (1 tool)
# ============================================================


@mcp.tool()
def seo_audit_media(url: str) -> dict:
    """Image and video SEO audit: modern formats (WebP/AVIF), file sizes,
    lazy-loading, srcset/sizes, alt text quality, VideoObject schema,
    Open Graph video tags."""
    from gaca.tools.media import audit_media
    return audit_media(url)


# ============================================================
# Competitor Intelligence (1 tool)
# ============================================================


@mcp.tool()
def seo_compare_competitors(
    client_url: str, competitor_urls: list[str], include_lighthouse: bool = False
) -> dict:
    """Side-by-side SEO comparison: meta tags, headings, schema, content metrics,
    security headers. Up to 3 competitors. Optionally includes Lighthouse scores."""
    from gaca.tools.competitor import compare_competitors
    return compare_competitors(client_url, competitor_urls, include_lighthouse)


# ============================================================
# Advanced (4 tools)
# ============================================================


@mcp.tool()
def seo_check_js_rendering(url: str) -> dict:
    """SPA/JS rendering detection: framework fingerprints (React, Vue, Angular,
    Next.js, Nuxt), static vs rendered HTML analysis, noscript fallback,
    lazy-load patterns, client-side routing signals."""
    from gaca.tools.js_rendering import check_js_rendering
    return check_js_rendering(url)


@mcp.tool()
def seo_analyze_logs(log_content: str, domain: str = "") -> dict:
    """Server access log analysis: bot identification (Googlebot, Bingbot, AI bots),
    crawl budget estimation, status code distribution, most crawled URLs,
    crawl frequency patterns. Paste log content directly."""
    from gaca.tools.logs import analyze_logs
    return analyze_logs(log_content, domain)


@mcp.tool()
def seo_analyze_gsc(csv_content: str, domain: str = "") -> dict:
    """Google Search Console CSV import and analysis: top queries, CTR per position,
    keyword cannibalization detection, declining pages, opportunity keywords."""
    from gaca.tools.gsc import analyze_gsc
    return analyze_gsc(csv_content, domain)


@mcp.tool()
def seo_compare_audits(domain: str, date1: str, date2: str) -> dict:
    """Compare two audit snapshots for a domain: improvements, regressions,
    new issues, resolved issues, score trends."""
    from gaca.tools.dashboard import compare_audits
    return compare_audits(domain, date1, date2)


# ============================================================
# GEO — Generative Engine Optimization (7 tools)
# ============================================================


@mcp.tool()
def seo_audit_geo(url: str, target_platforms: list[str] | None = None) -> dict:
    """Full GEO audit: analyze content for AI search citation readiness using
    Princeton 9 methods (cite sources +40%, statistics +37%, quotations +30%,
    authoritative tone +25%, easy language +20%, technical terms +18%,
    unique words +15%, fluency +15-30%). Checks all 5 AI platforms:
    ChatGPT, Perplexity, Google SGE, Copilot, Claude."""
    from gaca.geo.analyzer import audit_geo
    return audit_geo(url, target_platforms or ["all"])


@mcp.tool()
def seo_optimize_geo(
    content: str, methods: list[str] | None = None, target_platform: str = "all"
) -> dict:
    """GEO optimization suggestions: given content text, return specific
    suggestions for improving AI search citation probability using
    Princeton methods. Does NOT rewrite — provides actionable recommendations."""
    from gaca.geo.optimizer import optimize_geo
    return optimize_geo(content, methods or ["all"], target_platform)


@mcp.tool()
def seo_check_ai_robots(url: str) -> dict:
    """Analyze robots.txt for AI crawler rules: GPTBot, ChatGPT-User,
    ClaudeBot, anthropic-ai, PerplexityBot, Google-Extended, Bytespider,
    CCBot, cohere-ai, FacebookBot, Applebot-Extended. Shows which
    AI crawlers are allowed vs blocked."""
    from gaca.geo.robots_ai import check_ai_robots
    return check_ai_robots(url)


@mcp.tool()
def seo_generate_ai_robots(
    strategy: str = "recommended", current_robots: str = ""
) -> dict:
    """Generate optimal robots.txt rules for AI crawlers.
    Strategies: 'allow_all', 'block_all', 'selective', 'recommended'.
    Optionally merges with existing robots.txt content."""
    from gaca.geo.robots_ai import generate_ai_robots
    return generate_ai_robots(strategy, current_robots)


@mcp.tool()
def seo_check_ai_visibility(url: str) -> dict:
    """Check AI search citation readiness: structured data completeness,
    FAQ coverage, entity clarity, factual density, source attribution,
    speakable content detection."""
    from gaca.geo.analyzer import check_ai_visibility
    return check_ai_visibility(url)


@mcp.tool()
def seo_get_geo_checklist(url: str = "") -> dict:
    """GEO optimization checklist with P0/P1/P2 priorities.
    If URL provided, checks current compliance status.
    Without URL, returns the full checklist template."""
    from gaca.geo.checklist import get_geo_checklist
    return get_geo_checklist(url)


@mcp.tool()
def seo_get_seo_checklist(url: str = "") -> dict:
    """Traditional SEO checklist with P0/P1/P2 priorities.
    Covers technical SEO, on-page, content, links, schema, performance.
    If URL provided, checks current compliance status."""
    from gaca.geo.checklist import get_seo_checklist
    return get_seo_checklist(url)


# ============================================================
# Reporting (1 tool)
# ============================================================


@mcp.tool()
def seo_generate_report(
    audit_data: dict,
    format: str = "json",
    language: str = "en",
    title: str = "",
    output_path: str = "",
    brand: str = "",
) -> dict:
    """Generate a structured SEO report from any gaca tool output.
    format: 'json' returns content blocks, 'pdf' generates a branded PDF file.
    language: 'en' or 'pl'. brand: 'bartoszgaca', 'beecommerce', 'neutral'.
    Pass the full output dict from any gaca tool as audit_data."""
    from gaca.tools.reporting import generate_report
    return generate_report(audit_data, format, language, title, output_path, brand)


# ============================================================
# Utility (1 tool)
# ============================================================


@mcp.tool()
def seo_get_config() -> dict:
    """Show seo-gaca-mcp configuration: available features (Lighthouse, DataForSEO,
    SMTP), data file versions, Python version, installed package versions."""
    import sys
    from gaca import __version__
    from gaca.core.config import config
    return {
        "status": "success",
        "name": "seo-gaca-mcp",
        "full_name": "SEO GACA MCP — GEO · Audit · Crawl · Analyze",
        "version": __version__,
        "python": sys.version,
        "features": config.status(),
        "tools_count": 37,
    }
