"""JavaScript rendering audit tools for Googlebot compatibility."""

import logging
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from gaca.core.collectors import fetch_html
from gaca.core.parsers import parse_meta_tags

logger = logging.getLogger(__name__)

# Framework detection signatures
FRAMEWORK_SIGNATURES: dict[str, list[dict]] = {
    "next.js": [
        {"type": "text", "pattern": "__NEXT_DATA__"},
        {"type": "text", "pattern": "/_next/"},
        {"type": "text", "pattern": "_next/static"},
    ],
    "react": [
        {"type": "text", "pattern": "data-reactroot"},
        {"type": "text", "pattern": "react-root"},
        {"type": "attr", "tag": "div", "attr": "id", "value": "root"},
        {"type": "text", "pattern": "__REACT_DEVTOOLS"},
    ],
    "nuxt": [
        {"type": "text", "pattern": "__NUXT__"},
        {"type": "text", "pattern": "_nuxt/"},
    ],
    "vue": [
        {"type": "text", "pattern": "__VUE__"},
        {"type": "regex", "pattern": r'data-v-[a-f0-9]+'},
        {"type": "text", "pattern": "vue-app"},
    ],
    "angular": [
        {"type": "regex", "pattern": r'ng-version="'},
        {"type": "text", "pattern": "ng-app"},
        {"type": "attr", "tag": "app-root", "attr": None, "value": None},
    ],
    "svelte": [
        {"type": "text", "pattern": "__svelte"},
        {"type": "regex", "pattern": r'class="[^"]*svelte-[a-z0-9]+'},
    ],
    "gatsby": [
        {"type": "text", "pattern": "___gatsby"},
        {"type": "text", "pattern": "/page-data/"},
    ],
}

# Ordered by specificity — more specific frameworks first
FRAMEWORK_DETECTION_ORDER = ["next.js", "nuxt", "gatsby", "angular", "svelte", "vue", "react"]


def _detect_frameworks(html: str, soup: BeautifulSoup) -> list[dict]:
    """Detect JS frameworks present in the HTML source."""
    detected: list[dict] = []

    for framework in FRAMEWORK_DETECTION_ORDER:
        signatures = FRAMEWORK_SIGNATURES[framework]
        matches: list[str] = []

        for sig in signatures:
            if sig["type"] == "text":
                if sig["pattern"] in html:
                    matches.append(sig["pattern"])
            elif sig["type"] == "regex":
                if re.search(sig["pattern"], html):
                    matches.append(sig["pattern"])
            elif sig["type"] == "attr":
                tag_name = sig.get("tag")
                attr_name = sig.get("attr")
                attr_val = sig.get("value")
                if tag_name and attr_name:
                    found = soup.find(tag_name, attrs={attr_name: attr_val}) if attr_val else soup.find(tag_name, attrs={attr_name: True})
                    if found:
                        matches.append(f'{tag_name}[{attr_name}]')
                elif tag_name:
                    # Just check if the tag exists (e.g., <app-root>)
                    if soup.find(tag_name):
                        matches.append(f'<{tag_name}>')

        if matches:
            detected.append({
                "framework": framework,
                "signals": matches,
                "confidence": min(len(matches) / len(signatures), 1.0),
            })

    return detected


def _extract_body_word_count(soup: BeautifulSoup) -> int:
    """Count words in the visible body text of raw HTML."""
    body = soup.find("body")
    if not body:
        return 0
    for tag in body.find_all(["script", "style", "noscript"]):
        tag.decompose()
    text = body.get_text(separator=" ", strip=True)
    return len(text.split())


def _check_rendering_signals(html: str, soup: BeautifulSoup, word_count: int) -> dict:
    """Analyze rendering signals to determine SSR/CSR/SSG."""
    signals: list[dict] = []

    # Check for empty/minimal body
    body = soup.find("body")
    body_children_count = len(list(body.children)) if body else 0

    if word_count < 50:
        signals.append({
            "signal": "low_word_count",
            "detail": f"Only {word_count} words in raw HTML body",
            "indicates": "csr",
        })

    # Check for common CSR mount points with no content
    for mount_id in ["root", "app", "__next", "___gatsby"]:
        mount_div = soup.find(id=mount_id)
        if mount_div:
            children = list(mount_div.children)
            # Filter whitespace-only text nodes
            real_children = [c for c in children if not (isinstance(c, str) and not c.strip())]
            if len(real_children) == 0:
                signals.append({
                    "signal": f"empty_mount_point_{mount_id}",
                    "detail": f'<div id="{mount_id}"> has no child elements',
                    "indicates": "csr",
                })
            elif len(real_children) > 0:
                signals.append({
                    "signal": f"populated_mount_point_{mount_id}",
                    "detail": f'<div id="{mount_id}"> has {len(real_children)} child element(s)',
                    "indicates": "ssr",
                })

    # Check for __NEXT_DATA__ (Next.js SSR/SSG indicator)
    next_data_script = soup.find("script", id="__NEXT_DATA__")
    if next_data_script:
        signals.append({
            "signal": "next_data_present",
            "detail": "__NEXT_DATA__ script found (Next.js SSR/SSG)",
            "indicates": "ssr",
        })

    # Check for __NUXT__ (Nuxt SSR indicator)
    if "__NUXT__" in html and word_count > 50:
        signals.append({
            "signal": "nuxt_ssr_data",
            "detail": "__NUXT__ state found with substantial content",
            "indicates": "ssr",
        })

    # Check for noscript fallback
    noscript_tags = soup.find_all("noscript")
    noscript_has_content = False
    for ns in noscript_tags:
        ns_text = ns.get_text(strip=True)
        if len(ns_text) > 20:
            noscript_has_content = True
            break

    if noscript_has_content:
        signals.append({
            "signal": "noscript_fallback",
            "detail": "Meaningful <noscript> content found",
            "indicates": "csr_with_fallback",
        })

    # Check for prerendered content indicators
    if word_count > 200:
        signals.append({
            "signal": "substantial_content",
            "detail": f"{word_count} words in raw HTML suggests server-rendered content",
            "indicates": "ssr",
        })

    return {
        "signals": signals,
        "noscript_fallback": noscript_has_content,
        "body_children_count": body_children_count,
    }


def _determine_rendering_type(signals: list[dict], frameworks: list[dict]) -> str:
    """Determine the rendering type based on collected signals."""
    ssr_signals = sum(1 for s in signals if s["indicates"] == "ssr")
    csr_signals = sum(1 for s in signals if s["indicates"] == "csr")
    csr_fallback = sum(1 for s in signals if s["indicates"] == "csr_with_fallback")

    # No framework detected at all
    if not frameworks:
        if ssr_signals > 0 or csr_signals == 0:
            return "traditional"
        return "unknown"

    # Strong SSR signals
    if ssr_signals > csr_signals:
        return "ssr"

    # CSR with some fallback
    if csr_signals > 0 and csr_fallback > 0:
        return "csr"

    # Pure CSR
    if csr_signals > ssr_signals:
        return "csr"

    # Ambiguous but has framework
    if ssr_signals == csr_signals and ssr_signals > 0:
        return "ssr"

    return "unknown"


def _check_seo_elements_in_html(html: str, soup: BeautifulSoup) -> dict:
    """Check if SEO-critical elements are present in raw HTML."""
    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else None

    meta_desc = soup.find("meta", attrs={"name": "description"})
    desc_content = meta_desc.get("content", "").strip() if meta_desc else None

    h1_tags = soup.find_all("h1")
    h1_texts = [h.get_text(strip=True) for h in h1_tags if h.get_text(strip=True)]

    canonical = soup.find("link", rel="canonical")
    canonical_href = canonical.get("href", "").strip() if canonical else None

    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")

    return {
        "title_present": bool(title_text),
        "title_text": title_text,
        "meta_description_present": bool(desc_content),
        "meta_description": desc_content,
        "h1_present": len(h1_texts) > 0,
        "h1_count": len(h1_texts),
        "h1_texts": h1_texts[:3],
        "canonical_present": bool(canonical_href),
        "canonical_href": canonical_href,
        "og_title_present": og_title is not None,
        "og_description_present": og_desc is not None,
    }


def _calculate_score(
    rendering_type: str,
    seo_elements: dict,
    word_count: int,
    noscript_fallback: bool,
) -> int:
    """Calculate JS rendering SEO score from 1-10.

    SSR/SSG = good (8-10), CSR with meta = ok (5-7), CSR no meta = bad (1-4).
    """
    score = 5.0

    # Base score by rendering type
    if rendering_type in ("ssr", "traditional"):
        score = 8.0
    elif rendering_type == "csr":
        score = 3.0
    elif rendering_type == "unknown":
        score = 5.0

    # Bonus for SEO elements present in raw HTML
    if seo_elements["title_present"]:
        score += 0.5
    if seo_elements["meta_description_present"]:
        score += 0.5
    if seo_elements["h1_present"]:
        score += 0.5
    if seo_elements["canonical_present"]:
        score += 0.3
    if seo_elements["og_title_present"]:
        score += 0.2

    # Penalty for missing critical elements
    if not seo_elements["title_present"]:
        score -= 1.0
    if not seo_elements["h1_present"]:
        score -= 1.0

    # Content depth bonus/penalty
    if word_count > 200:
        score += 0.5
    elif word_count < 50 and rendering_type != "traditional":
        score -= 1.5

    # Noscript fallback partial credit for CSR
    if rendering_type == "csr" and noscript_fallback:
        score += 1.0

    return max(1, min(10, round(score)))


def check_js_rendering(url: str) -> dict:
    """Compare raw HTML vs rendered DOM to detect JS-dependent content invisible to crawlers.

    Args:
        url: The URL to audit for JavaScript rendering issues.

    Returns:
        Dict with status, url, timestamp, data (framework, rendering_type, signals,
        seo_elements_in_html, noscript_fallback, word_count_raw), score, issues,
        and recommendations.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    html, status_code, headers = fetch_html(url)
    if html is None:
        return {
            "status": "error",
            "url": url,
            "timestamp": timestamp,
            "message": f"Could not fetch URL (status {status_code})",
        }

    soup = BeautifulSoup(html, "lxml")

    # Detect frameworks
    frameworks = _detect_frameworks(html, soup)
    primary_framework = frameworks[0]["framework"] if frameworks else None

    # Count words in raw HTML
    # Make a fresh soup since _extract_body_word_count modifies it
    soup_for_words = BeautifulSoup(html, "lxml")
    word_count = _extract_body_word_count(soup_for_words)

    # Check rendering signals
    rendering_info = _check_rendering_signals(html, soup, word_count)
    signals = rendering_info["signals"]
    noscript_fallback = rendering_info["noscript_fallback"]

    # Determine rendering type
    rendering_type = _determine_rendering_type(signals, frameworks)

    # Check SEO elements in raw HTML
    seo_elements = _check_seo_elements_in_html(html, soup)

    # Calculate score
    score = _calculate_score(rendering_type, seo_elements, word_count, noscript_fallback)

    # Identify issues
    issues: list[str] = []

    if rendering_type == "csr":
        issues.append(
            "Client-side rendering detected. Search engines may not fully render JavaScript content."
        )
    if rendering_type == "csr" and not noscript_fallback:
        issues.append(
            "No <noscript> fallback content found. Users/bots with JS disabled see nothing."
        )
    if not seo_elements["title_present"]:
        issues.append(
            "<title> tag not found in raw HTML. May be injected by JavaScript."
        )
    if not seo_elements["meta_description_present"]:
        issues.append(
            "Meta description not found in raw HTML. May be injected by JavaScript."
        )
    if not seo_elements["h1_present"]:
        issues.append(
            "<h1> heading not found in raw HTML. May be rendered client-side."
        )
    if word_count < 50 and frameworks:
        issues.append(
            f"Very low content in raw HTML ({word_count} words). "
            "Content appears to be loaded via JavaScript."
        )
    if not seo_elements["canonical_present"] and rendering_type != "traditional":
        issues.append(
            "No canonical tag in raw HTML. Risk of duplicate content issues."
        )

    # Generate recommendations
    recommendations: list[str] = []

    if rendering_type == "csr":
        recommendations.append(
            "Consider migrating to Server-Side Rendering (SSR) or Static Site Generation (SSG). "
            "Frameworks like Next.js (React) or Nuxt (Vue) support hybrid rendering."
        )
        recommendations.append(
            "Implement dynamic rendering (e.g., Rendertron, Puppeteer) as an interim solution "
            "to serve pre-rendered HTML to search engine bots."
        )
    if not seo_elements["title_present"] or not seo_elements["meta_description_present"]:
        recommendations.append(
            "Ensure <title> and <meta description> are present in the initial HTML response, "
            "not injected via JavaScript. This is critical for search engine indexing."
        )
    if not seo_elements["h1_present"] and rendering_type != "traditional":
        recommendations.append(
            "Include the main <h1> heading in the server-rendered HTML. "
            "JS-dependent headings may not be indexed correctly."
        )
    if not noscript_fallback and frameworks:
        recommendations.append(
            "Add meaningful <noscript> fallback content for users and crawlers "
            "that cannot execute JavaScript."
        )
    if rendering_type == "ssr" and not seo_elements["canonical_present"]:
        recommendations.append(
            "Add a canonical tag to the server-rendered HTML to prevent duplicate content issues."
        )
    if not recommendations:
        recommendations.append(
            "Your site appears well-optimized for search engine rendering. "
            "SEO-critical elements are present in the initial HTML."
        )

    return {
        "status": "success",
        "url": url,
        "timestamp": timestamp,
        "data": {
            "framework": primary_framework,
            "frameworks_detected": frameworks,
            "rendering_type": rendering_type,
            "signals": signals,
            "seo_elements_in_html": seo_elements,
            "noscript_fallback": noscript_fallback,
            "word_count_raw": word_count,
        },
        "score": score,
        "issues": issues,
        "recommendations": recommendations,
    }
