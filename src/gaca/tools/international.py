"""International SEO tools for hreflang and multi-language site auditing."""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from gaca.core.collectors import fetch_html, fetch_headers

logger = logging.getLogger(__name__)

_VALID_LANGS = {
    "af", "am", "ar", "az", "be", "bg", "bn", "bs", "ca", "cs", "cy", "da",
    "de", "el", "en", "es", "et", "eu", "fa", "fi", "fr", "ga", "gl", "gu",
    "ha", "he", "hi", "hr", "hu", "hy", "id", "is", "it", "ja", "ka", "kk",
    "km", "kn", "ko", "ky", "lb", "lo", "lt", "lv", "mk", "ml", "mn", "mr",
    "ms", "mt", "my", "nb", "ne", "nl", "nn", "no", "pa", "pl", "ps", "pt",
    "ro", "ru", "si", "sk", "sl", "sq", "sr", "sv", "sw", "ta", "te", "th",
    "tk", "tr", "uk", "ur", "uz", "vi", "zh", "zu",
}

_VALID_REGIONS = {
    "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AR", "AT", "AU", "AZ",
    "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BN", "BO", "BR",
    "BS", "BT", "BW", "BY", "BZ", "CA", "CD", "CF", "CG", "CH", "CI", "CL",
    "CM", "CN", "CO", "CR", "CU", "CV", "CY", "CZ", "DE", "DJ", "DK", "DM",
    "DO", "DZ", "EC", "EE", "EG", "ER", "ES", "ET", "FI", "FJ", "FK", "FR",
    "GA", "GB", "GD", "GE", "GH", "GM", "GN", "GQ", "GR", "GT", "GW", "GY",
    "HK", "HN", "HR", "HT", "HU", "ID", "IE", "IL", "IN", "IQ", "IR", "IS",
    "IT", "JM", "JO", "JP", "KE", "KG", "KH", "KI", "KM", "KN", "KP", "KR",
    "KW", "KZ", "LA", "LB", "LC", "LI", "LK", "LR", "LS", "LT", "LU", "LV",
    "LY", "MA", "MC", "MD", "ME", "MG", "MK", "ML", "MM", "MN", "MO", "MR",
    "MT", "MU", "MV", "MW", "MX", "MY", "MZ", "NA", "NE", "NG", "NI", "NL",
    "NO", "NP", "NR", "NZ", "OM", "PA", "PE", "PG", "PH", "PK", "PL", "PS",
    "PT", "PY", "QA", "RO", "RS", "RU", "RW", "SA", "SB", "SC", "SD", "SE",
    "SG", "SI", "SK", "SL", "SM", "SN", "SO", "SR", "SS", "ST", "SV", "SY",
    "SZ", "TD", "TG", "TH", "TJ", "TL", "TM", "TN", "TO", "TR", "TT", "TV",
    "TW", "TZ", "UA", "UG", "US", "UY", "UZ", "VA", "VC", "VE", "VN", "VU",
    "WS", "YE", "ZA", "ZM", "ZW",
}


def check_hreflang(
    url: str,
    check_reciprocal: bool = True,
    sitemap_url: str = "",
) -> dict:
    """Check hreflang implementation for correctness and reciprocal tag pairing."""
    html, status, headers = fetch_html(url)
    if not html:
        return {
            "status": "error", "url": url,
            "message": f"Failed to fetch page (status: {status})",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    tags: list[dict] = []
    issues: list[dict] = []
    sources: dict = {"html": 0, "http_header": 0, "sitemap": 0}

    # 1. HTML link tags
    for link in soup.find_all("link", rel="alternate"):
        hl = link.get("hreflang", "")
        href = link.get("href", "")
        if hl and href:
            tags.append({"hreflang": hl, "href": href, "source": "html"})
            sources["html"] += 1

    # 2. HTTP headers
    resp_headers, _ = fetch_headers(url)
    link_header = resp_headers.get("link", "") or resp_headers.get("Link", "")
    if link_header:
        for part in link_header.split(","):
            m_href = re.search(r'<([^>]+)>', part)
            m_hl = re.search(r'hreflang="?([^";,\s]+)', part)
            if m_href and m_hl:
                tags.append({"hreflang": m_hl.group(1), "href": m_href.group(1), "source": "http_header"})
                sources["http_header"] += 1

    # 3. Sitemap
    if sitemap_url:
        try:
            shtml, _, _ = fetch_html(sitemap_url)
            if shtml:
                ssoup = BeautifulSoup(shtml, "lxml-xml")
                for xlink in ssoup.find_all("xhtml:link") or ssoup.find_all("link"):
                    hl = xlink.get("hreflang", "")
                    href = xlink.get("href", "")
                    if hl and href:
                        tags.append({"hreflang": hl, "href": href, "source": "sitemap"})
                        sources["sitemap"] += 1
        except Exception as e:
            logger.warning("Sitemap hreflang parse error: %s", e)

    if not tags:
        return {
            "status": "success", "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {"hreflang_tags": [], "sources": sources, "validation_results": []},
            "score": 1,
            "issues": [{"severity": "high", "message": "No hreflang tags found"}],
            "recommendations": [
                "Add hreflang link tags for multi-language pages",
                "Include x-default for language/region selector page",
            ],
        }

    # Validate tags
    has_x_default = False
    validation: list[dict] = []

    for tag in tags:
        hl = tag["hreflang"]
        result: dict = {"hreflang": hl, "href": tag["href"], "valid": True, "issues": []}

        if hl == "x-default":
            has_x_default = True
        else:
            parts = hl.lower().split("-")
            lang = parts[0]
            region = parts[1].upper() if len(parts) > 1 else None

            if lang not in _VALID_LANGS:
                result["valid"] = False
                result["issues"].append(f"Invalid language code: {lang}")
                issues.append({"severity": "high", "message": f"Invalid language code '{lang}' in hreflang='{hl}'"})

            if region and region not in _VALID_REGIONS:
                result["valid"] = False
                result["issues"].append(f"Invalid region code: {region}")
                issues.append({"severity": "medium", "message": f"Invalid region code '{region}' in hreflang='{hl}'"})

        validation.append(result)

    if not has_x_default:
        issues.append({"severity": "medium", "message": "Missing x-default hreflang tag"})

    # Reciprocal check
    reciprocal_results: list[dict] = []
    if check_reciprocal:
        checked_urls: set = set()
        for tag in tags[:10]:  # limit to avoid too many requests
            href = tag["href"]
            if href in checked_urls or href == url:
                continue
            checked_urls.add(href)
            try:
                rhtml, rstatus, _ = fetch_html(href)
                if rhtml:
                    rsoup = BeautifulSoup(rhtml, "lxml")
                    back_links = [
                        l.get("href", "") for l in rsoup.find_all("link", rel="alternate")
                        if l.get("href")
                    ]
                    parsed_url = urlparse(url)
                    has_backlink = any(
                        urlparse(bl).netloc == parsed_url.netloc
                        and urlparse(bl).path.rstrip("/") == parsed_url.path.rstrip("/")
                        for bl in back_links
                    )
                    reciprocal_results.append({
                        "url": href, "links_back": has_backlink,
                    })
                    if not has_backlink:
                        issues.append({
                            "severity": "high",
                            "message": f"No reciprocal hreflang from {href} back to {url}",
                        })
            except Exception:
                reciprocal_results.append({"url": href, "links_back": False, "error": "fetch failed"})

    # Score
    score = 10
    valid_count = sum(1 for v in validation if v["valid"])
    if valid_count < len(validation):
        score -= min(3, (len(validation) - valid_count))
    if not has_x_default:
        score -= 1
    failed_reciprocal = sum(1 for r in reciprocal_results if not r.get("links_back"))
    score -= min(3, failed_reciprocal)
    score = max(1, min(10, score))

    recs: list[str] = []
    if not has_x_default:
        recs.append("Add x-default hreflang pointing to your language selector or main page")
    if failed_reciprocal:
        recs.append("Fix reciprocal hreflang tags — each alternate page must link back")
    if any(not v["valid"] for v in validation):
        recs.append("Fix invalid language/region codes in hreflang attributes")

    return {
        "status": "success",
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "hreflang_tags": tags,
            "total_tags": len(tags),
            "sources": sources,
            "has_x_default": has_x_default,
            "validation_results": validation,
            "reciprocal_check": reciprocal_results,
        },
        "score": score,
        "issues": issues,
        "recommendations": recs,
    }
