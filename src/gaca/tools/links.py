"""Link audit tools for internal and external link analysis."""

import logging
import time
from collections import Counter, deque
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from gaca.core.collectors import fetch_html
from gaca.core.parsers import parse_links

logger = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
HEAD_TIMEOUT = 10


def _normalize_url(url: str) -> str:
    """Normalize URL by removing fragment and trailing slash for deduplication."""
    parsed = urlparse(url)
    # Remove fragment
    path = parsed.path.rstrip("/") or "/"
    normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    return normalized


def _head_request(url: str) -> tuple[int, float]:
    """Make a HEAD request, return (status_code, response_time_ms).

    Falls back to GET if HEAD is blocked (405).
    Returns (0, 0.0) on timeout/connection error.
    """
    try:
        start = time.time()
        r = requests.head(
            url,
            headers={"User-Agent": DEFAULT_UA},
            timeout=HEAD_TIMEOUT,
            allow_redirects=True,
        )
        elapsed = (time.time() - start) * 1000
        # Some servers block HEAD, fall back to GET
        if r.status_code == 405:
            start = time.time()
            r = requests.get(
                url,
                headers={"User-Agent": DEFAULT_UA},
                timeout=HEAD_TIMEOUT,
                allow_redirects=True,
                stream=True,
            )
            elapsed = (time.time() - start) * 1000
            r.close()
        return r.status_code, round(elapsed, 1)
    except requests.Timeout:
        return 0, 0.0
    except requests.RequestException:
        return 0, 0.0


def audit_links(url: str, max_pages: int = 50, max_depth: int = 3) -> dict:
    """Audit internal and external link structure via BFS crawl.

    Args:
        url: Starting URL for the crawl.
        max_pages: Maximum number of pages to crawl.
        max_depth: Maximum BFS depth from the start URL.

    Returns:
        Dict with status, data (pages_crawled, total_internal, total_external,
        orphan_pages, depth_distribution, top_anchor_texts, link_graph_summary),
        score, issues, and recommendations.
    """
    start_time = time.time()
    timestamp = datetime.now(timezone.utc).isoformat()

    parsed_start = urlparse(url)
    base_domain = parsed_start.netloc
    start_url = _normalize_url(url)

    # BFS state
    queue: deque[tuple[str, int]] = deque()  # (url, depth)
    queue.append((start_url, 0))
    visited: set[str] = set()
    visited.add(start_url)

    # Link graph: source -> [target_urls]
    link_graph: dict[str, list[str]] = {}
    # Incoming link counter
    incoming_count: Counter = Counter()
    # Depth map: url -> depth
    depth_map: dict[str, int] = {start_url: 0}
    # Anchor text collection
    anchor_texts: Counter = Counter()
    # Outgoing counts
    outgoing_count: dict[str, int] = {}

    total_internal_links = 0
    total_external_links = 0
    pages_crawled = 0
    crawl_errors: list[dict] = []

    while queue and pages_crawled < max_pages:
        current_url, depth = queue.popleft()

        html, status, _headers = fetch_html(current_url)
        if not html:
            crawl_errors.append({"url": current_url, "status": status, "depth": depth})
            continue

        pages_crawled += 1
        logger.debug("Crawled [%d/%d] depth=%d: %s", pages_crawled, max_pages, depth, current_url)

        # Parse links on current page
        link_data = parse_links(html, current_url)
        internal_links = link_data.get("internal", [])
        external_links = link_data.get("external", [])

        total_internal_links += len(internal_links)
        total_external_links += len(external_links)

        # Build graph for this page
        targets: list[str] = []
        for link in internal_links:
            href = link.get("href", "")
            if not href:
                continue
            normalized = _normalize_url(href)
            targets.append(normalized)
            incoming_count[normalized] += 1

            # Collect anchor text
            text = (link.get("text") or "").strip()
            if text:
                anchor_texts[text] += 1

            # Add to BFS queue if not visited and within depth
            if normalized not in visited and depth + 1 <= max_depth:
                # Only crawl pages on same domain
                link_parsed = urlparse(normalized)
                if link_parsed.netloc == base_domain:
                    visited.add(normalized)
                    queue.append((normalized, depth + 1))
                    depth_map[normalized] = depth + 1

        link_graph[current_url] = targets
        outgoing_count[current_url] = len(targets)

        # Collect anchor texts for external links too
        for link in external_links:
            text = (link.get("text") or "").strip()
            if text:
                anchor_texts[text] += 1

    # --- Analysis ---

    # Depth distribution
    depth_distribution: dict[int, int] = {}
    for d in depth_map.values():
        depth_distribution[d] = depth_distribution.get(d, 0) + 1

    # Orphan pages: pages discovered (in visited set) that have 0 incoming internal links,
    # excluding the start URL
    all_crawled_urls = set(link_graph.keys())
    orphan_pages: list[str] = []
    for page_url in all_crawled_urls:
        if page_url == start_url:
            continue
        if incoming_count.get(page_url, 0) == 0:
            orphan_pages.append(page_url)

    # Top anchor texts (top 20)
    top_anchor_texts = [
        {"text": text, "count": count}
        for text, count in anchor_texts.most_common(20)
    ]

    # Pages with most outgoing links (top 10)
    top_outgoing = sorted(outgoing_count.items(), key=lambda x: x[1], reverse=True)[:10]
    pages_most_outgoing = [{"url": u, "count": c} for u, c in top_outgoing]

    # Pages with most incoming links (top 10)
    top_incoming = incoming_count.most_common(10)
    pages_most_incoming = [{"url": u, "count": c} for u, c in top_incoming]

    # Average depth
    depths = list(depth_map.values())
    avg_depth = round(sum(depths) / len(depths), 2) if depths else 0.0

    # Max depth reached
    max_depth_reached = max(depths) if depths else 0

    # --- Scoring (1-10) ---
    issues: list[str] = []
    recommendations: list[str] = []

    score = 10.0

    # Orphan pages penalty
    if pages_crawled > 1:
        orphan_ratio = len(orphan_pages) / (pages_crawled - 1) if pages_crawled > 1 else 0
    else:
        orphan_ratio = 0

    if orphan_ratio > 0.3:
        score -= 3
        issues.append(f"{len(orphan_pages)} orphan pages ({orphan_ratio:.0%} of crawled pages)")
        recommendations.append(
            "Add internal links to orphan pages to improve crawlability and PageRank flow."
        )
    elif orphan_ratio > 0.1:
        score -= 1.5
        issues.append(f"{len(orphan_pages)} orphan pages ({orphan_ratio:.0%} of crawled pages)")
        recommendations.append(
            "Review orphan pages and add contextual internal links from related content."
        )

    # Average depth penalty
    if avg_depth > 4:
        score -= 2
        issues.append(f"Average page depth is {avg_depth} — too deep for efficient crawling")
        recommendations.append(
            "Flatten site architecture so important pages are reachable within 3 clicks."
        )
    elif avg_depth > 3:
        score -= 1
        issues.append(f"Average page depth is {avg_depth} — slightly deep")
        recommendations.append(
            "Consider adding hub/category pages to reduce average depth."
        )

    # Crawl errors penalty
    if crawl_errors:
        error_ratio = len(crawl_errors) / (pages_crawled + len(crawl_errors))
        if error_ratio > 0.2:
            score -= 2
            issues.append(f"{len(crawl_errors)} pages returned errors during crawl")
        elif error_ratio > 0.05:
            score -= 1
            issues.append(f"{len(crawl_errors)} pages returned errors during crawl")
        recommendations.append(
            "Fix or redirect pages that returned errors during crawl."
        )

    # Low internal linking penalty
    if pages_crawled > 1:
        avg_internal = total_internal_links / pages_crawled
        if avg_internal < 3:
            score -= 1.5
            issues.append(
                f"Low average internal links per page ({avg_internal:.1f})"
            )
            recommendations.append(
                "Increase internal linking — aim for at least 3-5 contextual internal links per page."
            )

    # Pages with 0 outgoing internal links
    dead_end_pages = [u for u, c in outgoing_count.items() if c == 0]
    if dead_end_pages:
        score -= 0.5 * min(len(dead_end_pages), 3)
        issues.append(f"{len(dead_end_pages)} dead-end pages with no outgoing internal links")
        recommendations.append(
            "Add related content links or navigation to dead-end pages."
        )

    # Clamp score
    score = max(1, min(10, round(score)))

    # General recommendations if none generated
    if not recommendations:
        recommendations.append("Internal link structure looks healthy. Keep maintaining contextual links.")

    elapsed = round(time.time() - start_time, 2)

    return {
        "status": "success",
        "url": url,
        "timestamp": timestamp,
        "data": {
            "pages_crawled": pages_crawled,
            "total_internal_links": total_internal_links,
            "total_external_links": total_external_links,
            "orphan_pages": orphan_pages,
            "orphan_pages_count": len(orphan_pages),
            "depth_distribution": depth_distribution,
            "avg_depth": avg_depth,
            "max_depth_reached": max_depth_reached,
            "top_anchor_texts": top_anchor_texts,
            "pages_most_outgoing_links": pages_most_outgoing,
            "pages_most_incoming_links": pages_most_incoming,
            "dead_end_pages": dead_end_pages,
            "crawl_errors": crawl_errors,
            "link_graph_summary": {
                "nodes": len(link_graph),
                "edges": sum(len(v) for v in link_graph.values()),
            },
            "crawl_time_seconds": elapsed,
        },
        "score": score,
        "issues": issues,
        "recommendations": recommendations,
    }


def check_broken_links(url: str) -> dict:
    """Check all links on a single page for broken responses (4xx, 5xx, timeout).

    Args:
        url: Page URL to check.

    Returns:
        Dict with status, data (total_links, ok, redirects, broken, errors),
        score, and recommendations.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    html, status, _headers = fetch_html(url)
    if not html:
        return {
            "status": "error",
            "url": url,
            "message": f"Failed to fetch page (status: {status})",
            "timestamp": timestamp,
        }

    link_data = parse_links(html, url)
    all_links = link_data.get("internal", []) + link_data.get("external", [])

    # Deduplicate by href
    seen_hrefs: set[str] = set()
    unique_links: list[dict] = []
    for link in all_links:
        href = link.get("href", "")
        if href and href not in seen_hrefs:
            seen_hrefs.add(href)
            unique_links.append(link)

    # Limit to 100 links
    links_to_check = unique_links[:100]
    total_links = len(unique_links)
    checked_count = len(links_to_check)

    ok_links: list[dict] = []
    redirect_links: list[dict] = []
    broken_links: list[dict] = []
    error_links: list[dict] = []
    unreachable_links: list[dict] = []

    for link in links_to_check:
        href = link.get("href", "")
        text = (link.get("text") or "").strip()

        status_code, response_time = _head_request(href)

        entry = {
            "url": href,
            "anchor_text": text[:100],
            "status": status_code,
            "response_time_ms": response_time,
        }

        if status_code == 0:
            entry["category"] = "unreachable"
            unreachable_links.append(entry)
        elif 200 <= status_code < 300:
            entry["category"] = "ok"
            ok_links.append(entry)
        elif 300 <= status_code < 400:
            entry["category"] = "redirect"
            redirect_links.append(entry)
        elif 400 <= status_code < 500:
            entry["category"] = "broken"
            broken_links.append(entry)
        elif status_code >= 500:
            entry["category"] = "server_error"
            error_links.append(entry)

    # --- Scoring ---
    issues: list[str] = []
    recommendations: list[str] = []
    score = 10.0

    # Broken links penalty
    if broken_links:
        broken_ratio = len(broken_links) / checked_count if checked_count else 0
        if broken_ratio > 0.1:
            score -= 4
        elif broken_ratio > 0.05:
            score -= 2.5
        elif broken_links:
            score -= 1
        issues.append(
            f"{len(broken_links)} broken link(s) (4xx) found"
        )
        recommendations.append(
            "Fix or remove broken links. Update href to valid URLs or remove the link elements."
        )

    # Server errors
    if error_links:
        score -= min(len(error_links) * 0.5, 2)
        issues.append(
            f"{len(error_links)} link(s) returning server errors (5xx)"
        )
        recommendations.append(
            "Investigate server errors — the linked resources may be experiencing issues."
        )

    # Unreachable
    if unreachable_links:
        score -= min(len(unreachable_links) * 0.3, 2)
        issues.append(
            f"{len(unreachable_links)} link(s) are unreachable (timeout or connection error)"
        )
        recommendations.append(
            "Verify unreachable links — they may be temporarily down or have incorrect URLs."
        )

    # Excessive redirects
    if redirect_links:
        redirect_ratio = len(redirect_links) / checked_count if checked_count else 0
        if redirect_ratio > 0.2:
            score -= 1
            issues.append(
                f"{len(redirect_links)} link(s) are redirects — update to final destination URLs"
            )
            recommendations.append(
                "Update redirect links to point directly to the final URL to save crawl budget."
            )

    score = max(1, min(10, round(score)))

    if not issues:
        recommendations.append("All checked links are healthy. No action needed.")

    return {
        "status": "success",
        "url": url,
        "timestamp": timestamp,
        "data": {
            "total_links": total_links,
            "checked": checked_count,
            "ok": len(ok_links),
            "redirects": len(redirect_links),
            "broken": broken_links,
            "server_errors": error_links,
            "unreachable": unreachable_links,
            "redirect_details": redirect_links,
        },
        "score": score,
        "issues": issues,
        "recommendations": recommendations,
    }
