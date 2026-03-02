"""Technical SEO audit — full 13-step pipeline with UX analysis."""

import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from seoleo.core.collectors import (
    check_resource, discover_sitemap_urls, fetch_headers, fetch_html,
    fetch_page_without_ua, fetch_robots, fetch_sitemap, fetch_ssl_info,
    get_hosting_info,
)
from seoleo.core.parsers import (
    fetch_and_parse_css_media_queries, parse_headings, parse_html_tag,
    parse_images, parse_links, parse_meta_tags, parse_schema, parse_scripts,
    parse_ux_elements,
)
from seoleo.core.analyzers import (
    calculate_scores, detect_issues, detect_ux_issues,
    generate_recommendations, generate_top5_problems, generate_top5_quickwins,
)
from seoleo.core.lighthouse import run_full_lighthouse

logger = logging.getLogger(__name__)


def run_full_audit(
    url: str,
    include_subpages: bool = True,
    max_subpages: int = 15,
    include_ux: bool = True,
) -> dict:
    """Full 13-step SEO+UX audit pipeline."""
    start = time.time()
    parsed = urlparse(url)
    domain = parsed.netloc
    base_url = f"{parsed.scheme}://{domain}"

    data: dict = {"url": url, "domain": domain, "base_url": base_url}

    # Step 1: Fetch homepage
    html, status, headers = fetch_html(url)
    data["headers"] = headers
    data["status_code"] = status

    if not html:
        return {
            "status": "error",
            "url": url,
            "message": f"Nie udało się pobrać strony (status: {status})",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Step 2: Test without UA
    status_no_ua = fetch_page_without_ua(url)
    data["status_no_ua"] = status_no_ua

    # Step 3: Robots.txt
    robots_txt = fetch_robots(base_url)
    data["robots_txt"] = robots_txt

    # Step 4: Sitemap
    sitemap_urls = discover_sitemap_urls(base_url, robots_txt)
    sitemap_entries: list = []
    for sm_url in sitemap_urls:
        sitemap_entries.extend(fetch_sitemap(sm_url))
    data["sitemap_urls"] = sitemap_urls
    data["sitemap_entries"] = sitemap_entries

    # Step 5: Lighthouse
    lh_results = run_full_lighthouse(url)
    data["lighthouse_mobile"] = lh_results.get("mobile", {})
    data["lighthouse_desktop"] = lh_results.get("desktop", {})

    # Step 6: Parse homepage
    meta = parse_meta_tags(html)
    headings = parse_headings(html)
    images = parse_images(html, base_url)
    links = parse_links(html, base_url)
    schema = parse_schema(html)
    html_tag = parse_html_tag(html)
    scripts = parse_scripts(html)

    data["homepage"] = {
        "meta": meta, "headings": headings, "images": images,
        "links": links, "schema": schema, "html_tag": html_tag,
        "scripts": scripts,
    }

    # Step 7: Subpages
    subpages: dict = {}
    if include_subpages and sitemap_entries:
        sp_urls = [e["loc"] for e in sitemap_entries if e.get("loc") != url][:max_subpages]
        for sp_url in sp_urls:
            sp_html, sp_status, _ = fetch_html(sp_url)
            if sp_html:
                sp_path = urlparse(sp_url).path
                subpages[sp_path] = {
                    "url": sp_url,
                    "status": sp_status,
                    "meta": parse_meta_tags(sp_html),
                    "headings": parse_headings(sp_html),
                }
    data["subpages"] = subpages

    # Step 8: Additional resources
    data["resources"] = {
        "favicon": check_resource(f"{base_url}/favicon.ico"),
        "security_txt": check_resource(f"{base_url}/.well-known/security.txt"),
    }

    # Step 9: Hosting info
    data["hosting"] = get_hosting_info(domain)
    data["ssl"] = fetch_ssl_info(domain)

    # Step 10: UX analysis
    ux_data: dict = {}
    if include_ux:
        ux_data = parse_ux_elements(html, base_url)
        css_breakpoints = fetch_and_parse_css_media_queries(ux_data.get("css_links", []))
        ux_data["css_breakpoints"] = css_breakpoints
    data["ux"] = ux_data

    # Step 11: Detect issues
    seo_issues = detect_issues(data)
    ux_issues: list = []
    if include_ux:
        lighthouse_ux = {
            "tap_targets": data["lighthouse_mobile"].get("tap_targets", {}),
            "font_size": data["lighthouse_mobile"].get("font_size", {}),
            "color_contrast": data["lighthouse_mobile"].get("color_contrast", {}),
        }
        ux_issues = detect_ux_issues(ux_data, lighthouse_ux)

    all_issues = seo_issues + ux_issues

    # Step 12: Scores
    scores = calculate_scores(all_issues)

    # Step 13: Build result
    overall_score = round(
        sum(c["score"] for c in scores.values()) / len(scores), 1
    ) if scores else 0

    elapsed = round(time.time() - start, 1)

    return {
        "status": "success",
        "url": url,
        "domain": domain,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "scores": {k: {"name": v["name"], "score": v["score"]} for k, v in scores.items()},
        "overall_score": overall_score,
        "issues": all_issues,
        "top5_problems": generate_top5_problems(all_issues),
        "top5_quickwins": generate_top5_quickwins(all_issues),
        "recommendations": generate_recommendations(all_issues),
        "data": {
            "meta": meta,
            "headings": headings,
            "images": {"count": images["count"], "without_alt": images["without_alt"], "formats": images["formats"]},
            "links": {"internal_count": len(links["internal"]), "external_count": len(links["external"])},
            "schema": {"json_ld_count": len(schema["json_ld"]), "types": [s.get("@type", "") for s in schema["json_ld"]]},
            "html_tag": html_tag,
            "robots_txt": robots_txt is not None,
            "sitemap_urls": sitemap_urls,
            "sitemap_entries_count": len(sitemap_entries),
            "subpages_analyzed": len(subpages),
            "hosting": data["hosting"],
            "ssl": data["ssl"],
            "lighthouse": {
                "mobile": data["lighthouse_mobile"].get("scores", {}),
                "desktop": data["lighthouse_desktop"].get("scores", {}),
            },
            "ux": {
                "has_search": ux_data.get("search", {}).get("has_search", False),
                "nav_count": ux_data.get("navigation", {}).get("nav_count", 0),
                "has_mobile_menu": ux_data.get("navigation", {}).get("has_mobile_menu_trigger", False),
                "has_main": ux_data.get("semantic_structure", {}).get("has_main", False),
                "has_skip_link": ux_data.get("semantic_structure", {}).get("has_skip_link", False),
            } if ux_data else {},
        },
    }


def check_meta(url: str) -> dict:
    """Quick meta tag analysis for a single URL."""
    html, status, headers = fetch_html(url)
    if not html:
        return {"status": "error", "url": url, "message": f"Fetch failed (status: {status})"}

    meta = parse_meta_tags(html)
    html_tag = parse_html_tag(html)

    return {
        "status": "success",
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {**meta, "html_lang": html_tag.get("lang")},
    }


def check_crawlability(url: str) -> dict:
    """Robots.txt + sitemap analysis."""
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    robots_txt = fetch_robots(base_url)
    sitemap_urls = discover_sitemap_urls(base_url, robots_txt)
    sitemap_entries: list = []
    for sm_url in sitemap_urls:
        sitemap_entries.extend(fetch_sitemap(sm_url))

    return {
        "status": "success",
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "robots_txt": robots_txt,
            "has_robots": robots_txt is not None,
            "sitemap_urls": sitemap_urls,
            "sitemap_entries_count": len(sitemap_entries),
        },
    }


def check_headers(url: str) -> dict:
    """HTTP response headers analysis."""
    headers, status = fetch_headers(url)
    security_headers = [
        "strict-transport-security", "content-security-policy",
        "x-content-type-options", "x-frame-options",
        "referrer-policy", "permissions-policy", "x-xss-protection",
    ]
    h_lower = {k.lower(): v for k, v in headers.items()}
    security_status = {h: h in h_lower for h in security_headers}

    return {
        "status": "success",
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "status_code": status,
            "headers": headers,
            "security_headers": security_status,
            "server": h_lower.get("server", ""),
            "x_powered_by": h_lower.get("x-powered-by", ""),
        },
    }


def check_performance(url: str, form_factor: str = "both") -> dict:
    """Lighthouse scores and Core Web Vitals."""
    results = run_full_lighthouse(url, form_factor)
    return {
        "status": "success",
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": results,
    }
