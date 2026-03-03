"""SEO and GEO checklists with P0/P1/P2 priorities."""

from datetime import datetime, timezone

from gaca.core.collectors import fetch_html, fetch_robots
from gaca.core.parsers import parse_meta_tags, parse_schema, parse_headings

GEO_CHECKLIST = [
    {"id": "geo-01", "priority": "P0", "category": "Schema", "check": "Add FAQPage JSON-LD schema (+40% AI visibility)", "how": "Add FAQ schema to key landing pages"},
    {"id": "geo-02", "priority": "P0", "category": "Citations", "check": "Include inline citations and references", "how": "Add 'According to [Source]...' patterns, link to authoritative sources"},
    {"id": "geo-03", "priority": "P0", "category": "Statistics", "check": "Add specific data points and statistics", "how": "Include percentages, dollar amounts, research data"},
    {"id": "geo-04", "priority": "P0", "category": "Robots", "check": "Allow key AI crawlers in robots.txt", "how": "Allow GPTBot, ClaudeBot, PerplexityBot, Google-Extended"},
    {"id": "geo-05", "priority": "P1", "category": "Content", "check": "Add expert quotations with attribution", "how": "Include named expert quotes relevant to your content"},
    {"id": "geo-06", "priority": "P1", "category": "Content", "check": "Use authoritative, confident tone", "how": "Remove hedging words (maybe, perhaps, might)"},
    {"id": "geo-07", "priority": "P1", "category": "Schema", "check": "Add Article/BlogPosting schema", "how": "Add JSON-LD Article schema with author, datePublished"},
    {"id": "geo-08", "priority": "P1", "category": "Schema", "check": "Add SpeakableSpecification schema", "how": "Mark key paragraphs as speakable for voice assistants"},
    {"id": "geo-09", "priority": "P1", "category": "Content", "check": "Maintain content freshness (<30 days)", "how": "Update key pages regularly, show dateModified"},
    {"id": "geo-10", "priority": "P1", "category": "Structure", "check": "Clear heading hierarchy (H1>H2>H3)", "how": "Single H1, descriptive H2s for each section"},
    {"id": "geo-11", "priority": "P2", "category": "Content", "check": "Use domain-specific technical terms", "how": "Include industry jargon and technical vocabulary"},
    {"id": "geo-12", "priority": "P2", "category": "Content", "check": "Diversify vocabulary (unique words)", "how": "Avoid word repetition, use synonyms"},
    {"id": "geo-13", "priority": "P2", "category": "Content", "check": "Optimize readability and fluency", "how": "Short sentences (<20 words avg), bullet lists, clear paragraphs"},
    {"id": "geo-14", "priority": "P2", "category": "Platform", "check": "Submit to Brave Search (for Claude)", "how": "Submit URL at search.brave.com/webmaster"},
    {"id": "geo-15", "priority": "P2", "category": "Platform", "check": "Submit to Bing Webmaster (for Copilot)", "how": "Register at bing.com/webmaster"},
]

SEO_CHECKLIST = [
    {"id": "seo-01", "priority": "P0", "category": "Meta", "check": "Unique <title> tag (50-60 chars)", "how": "Add descriptive title with primary keyword"},
    {"id": "seo-02", "priority": "P0", "category": "Meta", "check": "Meta description (120-155 chars)", "how": "Write compelling description with CTA"},
    {"id": "seo-03", "priority": "P0", "category": "Meta", "check": "Canonical tag on every page", "how": "Add <link rel='canonical' href='...'>"},
    {"id": "seo-04", "priority": "P0", "category": "Meta", "check": "Viewport meta tag", "how": "Add <meta name='viewport' content='width=device-width, initial-scale=1'>"},
    {"id": "seo-05", "priority": "P0", "category": "Content", "check": "Single H1 with primary keyword", "how": "One H1 per page containing the main keyword"},
    {"id": "seo-06", "priority": "P0", "category": "Crawl", "check": "robots.txt exists and is valid", "how": "Create robots.txt with sitemap reference"},
    {"id": "seo-07", "priority": "P0", "category": "Crawl", "check": "XML sitemap exists", "how": "Generate and submit sitemap.xml to GSC"},
    {"id": "seo-08", "priority": "P0", "category": "Security", "check": "HTTPS with valid SSL", "how": "Install SSL certificate, redirect HTTP to HTTPS"},
    {"id": "seo-09", "priority": "P1", "category": "Meta", "check": "Open Graph tags (og:title, og:description, og:image)", "how": "Add OG tags for social sharing"},
    {"id": "seo-10", "priority": "P1", "category": "Content", "check": "H2 subheadings structuring content", "how": "Add H2s for each major section"},
    {"id": "seo-11", "priority": "P1", "category": "Images", "check": "All images have descriptive alt text", "how": "Add alt attributes describing image content"},
    {"id": "seo-12", "priority": "P1", "category": "Images", "check": "Modern image formats (WebP/AVIF)", "how": "Convert images to WebP/AVIF"},
    {"id": "seo-13", "priority": "P1", "category": "Schema", "check": "JSON-LD structured data present", "how": "Add Organization, WebSite, breadcrumbs schema"},
    {"id": "seo-14", "priority": "P1", "category": "Performance", "check": "Lighthouse Performance ≥ 90", "how": "Optimize images, JS, CSS, server response"},
    {"id": "seo-15", "priority": "P1", "category": "Performance", "check": "LCP < 2.5s", "how": "Optimize largest visible element loading"},
    {"id": "seo-16", "priority": "P1", "category": "Security", "check": "HSTS header present", "how": "Add Strict-Transport-Security header"},
    {"id": "seo-17", "priority": "P1", "category": "Meta", "check": "HTML lang attribute set", "how": "Add <html lang='pl'> or appropriate language"},
    {"id": "seo-18", "priority": "P2", "category": "Links", "check": "External links have rel='noopener'", "how": "Add rel='noopener noreferrer' to target='_blank' links"},
    {"id": "seo-19", "priority": "P2", "category": "Images", "check": "Lazy loading for below-fold images", "how": "Add loading='lazy' to images"},
    {"id": "seo-20", "priority": "P2", "category": "Meta", "check": "Twitter Cards configured", "how": "Add twitter:card, twitter:title, twitter:description"},
]


def get_geo_checklist(url: str = "") -> dict:
    """Return GEO checklist, optionally with compliance check for URL."""
    result: dict = {
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checklist": GEO_CHECKLIST,
        "total_items": len(GEO_CHECKLIST),
    }

    if url:
        compliance = _check_geo_compliance(url)
        result["compliance"] = compliance
        passed = sum(1 for v in compliance.values() if v)
        result["compliance_score"] = f"{passed}/{len(compliance)}"

    return result


def get_seo_checklist(url: str = "") -> dict:
    """Return SEO checklist, optionally with compliance check for URL."""
    result: dict = {
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checklist": SEO_CHECKLIST,
        "total_items": len(SEO_CHECKLIST),
    }

    if url:
        compliance = _check_seo_compliance(url)
        result["compliance"] = compliance
        passed = sum(1 for v in compliance.values() if v)
        result["compliance_score"] = f"{passed}/{len(compliance)}"

    return result


def _check_geo_compliance(url: str) -> dict:
    html, status, _ = fetch_html(url)
    if not html:
        return {}

    from urllib.parse import urlparse
    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

    schema = parse_schema(html)
    meta = parse_meta_tags(html)
    headings = parse_headings(html)
    robots = fetch_robots(base_url) or ""

    json_ld_types = [s.get("@type", "") for s in schema.get("json_ld", [])]

    return {
        "geo-01": "FAQPage" in json_ld_types,
        "geo-04": not any(
            bot.lower() in robots.lower()
            for bot in ["GPTBot", "ClaudeBot", "PerplexityBot"]
            if f"user-agent: {bot.lower()}" in robots.lower()
            and "disallow: /" in robots.lower()
        ),
        "geo-07": any(t in json_ld_types for t in ["Article", "NewsArticle", "BlogPosting"]),
        "geo-10": len(headings.get("h1", [])) == 1 and len(headings.get("h2", [])) >= 2,
    }


def _check_seo_compliance(url: str) -> dict:
    html, status, headers = fetch_html(url)
    if not html:
        return {}

    from urllib.parse import urlparse
    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

    meta = parse_meta_tags(html)
    headings = parse_headings(html)
    robots = fetch_robots(base_url)

    return {
        "seo-01": bool(meta.get("title")) and 30 <= len(meta.get("title", "")) <= 60,
        "seo-02": bool(meta.get("description")) and 70 <= len(meta.get("description", "")) <= 160,
        "seo-03": bool(meta.get("canonical")),
        "seo-04": bool(meta.get("viewport")),
        "seo-05": len(headings.get("h1", [])) == 1,
        "seo-06": robots is not None,
        "seo-09": len(meta.get("og", {})) >= 3,
        "seo-17": True,  # Would need html_tag for this
    }
