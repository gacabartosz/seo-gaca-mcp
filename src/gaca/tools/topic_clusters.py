"""Topic cluster and content silo audit tools."""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from gaca.core.collectors import discover_sitemap_urls, fetch_html, fetch_robots, fetch_sitemap

logger = logging.getLogger(__name__)


def _discover_sitemap(url: str, sitemap_url: str) -> list[str]:
    """Discover and fetch sitemap URLs, returning a flat list of page URLs."""
    if sitemap_url:
        entries = fetch_sitemap(sitemap_url)
        if entries:
            return [e["loc"] for e in entries if e.get("loc")]

    # Try robots.txt discovery
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    robots_txt = fetch_robots(base_url)
    sitemap_urls = discover_sitemap_urls(base_url, robots_txt)

    all_page_urls: list[str] = []
    for sm_url in sitemap_urls:
        entries = fetch_sitemap(sm_url)
        for entry in entries:
            loc = entry.get("loc")
            if loc:
                all_page_urls.append(loc)

    return all_page_urls


def _extract_cluster_key(path: str) -> tuple[str, str]:
    """Extract cluster name and page slug from a URL path.

    /blog/seo/keyword-research -> cluster="blog/seo", page="keyword-research"
    /products/shoes -> cluster="products", page="shoes"
    /about -> cluster="(root)", page="about"
    """
    segments = [s for s in path.strip("/").split("/") if s]

    if not segments:
        return "(root)", ""

    if len(segments) == 1:
        return "(root)", segments[0]

    # Use first 1-2 segments as the cluster key
    if len(segments) == 2:
        return segments[0], segments[1]

    # 3+ segments: cluster is first two segments
    cluster = "/".join(segments[:2])
    page = "/".join(segments[2:])
    return cluster, page


def _identify_pillar_page(cluster_name: str, pages: list[dict]) -> str | None:
    """Identify the pillar page in a cluster (shortest URL or index page)."""
    if not pages:
        return None

    # Sort by URL length — shortest is most likely the pillar
    sorted_pages = sorted(pages, key=lambda p: len(p["url"]))
    return sorted_pages[0]["url"]


def _check_pillar_links(pillar_url: str, cluster_page_urls: list[str]) -> dict:
    """Check if a pillar page links to its cluster pages."""
    html, status_code, _ = fetch_html(pillar_url)
    if html is None:
        return {"checked": False, "linked_pages": [], "unlinked_pages": cluster_page_urls}

    soup = BeautifulSoup(html, "lxml")
    all_hrefs: set[str] = set()
    for a in soup.find_all("a", href=True):
        all_hrefs.add(a["href"].strip().rstrip("/"))

    linked: list[str] = []
    unlinked: list[str] = []
    for page_url in cluster_page_urls:
        normalized = page_url.rstrip("/")
        # Check both full URL and path-only matches
        parsed = urlparse(normalized)
        path = parsed.path.rstrip("/")

        if normalized in all_hrefs or path in all_hrefs:
            linked.append(page_url)
        else:
            unlinked.append(page_url)

    return {
        "checked": True,
        "linked_pages": linked,
        "unlinked_pages": unlinked,
    }


def _score_cluster_structure(
    clusters: list[dict],
    thin_clusters: list[str],
    large_clusters: list[str],
    linking_gaps: list[dict],
    total_urls: int,
) -> int:
    """Score cluster structure quality from 1-10."""
    if total_urls == 0:
        return 1

    score = 10.0

    # Penalize for too few clusters
    if len(clusters) < 2:
        score -= 2.0

    # Penalize thin clusters
    thin_ratio = len(thin_clusters) / max(len(clusters), 1)
    score -= thin_ratio * 3.0

    # Penalize large clusters (potentially unorganized)
    large_ratio = len(large_clusters) / max(len(clusters), 1)
    score -= large_ratio * 1.5

    # Penalize linking gaps
    if linking_gaps:
        gap_severity = sum(len(g.get("unlinked_pages", [])) for g in linking_gaps)
        score -= min(3.0, gap_severity * 0.3)

    # Bonus for having clear structure (multiple clusters with 3-20 pages)
    well_sized = sum(1 for c in clusters if 3 <= c["page_count"] <= 20)
    if clusters:
        score += (well_sized / len(clusters)) * 1.5

    return max(1, min(10, round(score)))


def audit_topic_clusters(url: str, sitemap_url: str = "") -> dict:
    """Audit topic cluster structure, pillar pages, and internal linking silos.

    Args:
        url: The site URL to audit.
        sitemap_url: Optional sitemap URL. If empty, attempts discovery via robots.txt.

    Returns:
        Dict with status, url, timestamp, data (clusters, thin/large cluster lists),
        score, issues, and recommendations.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Discover sitemap URLs
    page_urls = _discover_sitemap(url, sitemap_url)

    if not page_urls:
        return {
            "status": "error",
            "url": url,
            "timestamp": timestamp,
            "message": "Could not discover sitemap or no URLs found. "
                       "Provide sitemap_url parameter explicitly.",
        }

    # Parse base domain for filtering
    parsed_base = urlparse(url)
    base_domain = parsed_base.netloc

    # Filter to same domain only
    page_urls = [u for u in page_urls if urlparse(u).netloc == base_domain]

    # Group URLs by cluster
    cluster_map: dict[str, list[dict]] = defaultdict(list)
    for page_url in page_urls:
        parsed = urlparse(page_url)
        cluster_name, page_slug = _extract_cluster_key(parsed.path)
        cluster_map[cluster_name].append({
            "url": page_url,
            "slug": page_slug,
            "path": parsed.path,
        })

    # Analyze each cluster
    clusters: list[dict] = []
    thin_clusters: list[str] = []
    large_clusters: list[str] = []
    linking_gaps: list[dict] = []

    # Limit pillar link checks to avoid excessive fetching
    pillar_checks_remaining = 5

    for cluster_name, pages in sorted(cluster_map.items(), key=lambda x: -len(x[1])):
        pillar_url = _identify_pillar_page(cluster_name, pages)
        cluster_page_urls = [p["url"] for p in pages if p["url"] != pillar_url]
        page_count = len(pages)

        cluster_info: dict = {
            "name": cluster_name,
            "pillar_url": pillar_url,
            "pages": [p["url"] for p in pages],
            "page_count": page_count,
        }

        # Check pillar linking (limited to avoid too many HTTP requests)
        if pillar_url and cluster_page_urls and pillar_checks_remaining > 0:
            pillar_checks_remaining -= 1
            link_check = _check_pillar_links(pillar_url, cluster_page_urls)
            cluster_info["pillar_links"] = link_check

            if link_check["checked"] and link_check["unlinked_pages"]:
                linking_gaps.append({
                    "cluster": cluster_name,
                    "pillar_url": pillar_url,
                    "unlinked_pages": link_check["unlinked_pages"],
                })

        # Detect thin and large clusters
        if page_count < 3:
            thin_clusters.append(cluster_name)
        if page_count > 20:
            large_clusters.append(cluster_name)

        clusters.append(cluster_info)

    # Score the structure
    score = _score_cluster_structure(
        clusters, thin_clusters, large_clusters, linking_gaps, len(page_urls)
    )

    # Identify issues
    issues: list[str] = []
    if thin_clusters:
        issues.append(
            f"{len(thin_clusters)} thin cluster(s) with fewer than 3 pages: "
            f"{', '.join(thin_clusters[:5])}"
        )
    if large_clusters:
        issues.append(
            f"{len(large_clusters)} oversized cluster(s) with 20+ pages: "
            f"{', '.join(large_clusters[:5])}"
        )
    if linking_gaps:
        total_unlinked = sum(len(g["unlinked_pages"]) for g in linking_gaps)
        issues.append(
            f"{total_unlinked} cluster page(s) not linked from their pillar page "
            f"across {len(linking_gaps)} cluster(s)."
        )
    if len(clusters) == 1:
        issues.append("Only 1 content cluster detected. Consider organizing content into topical silos.")
    if not page_urls:
        issues.append("No indexable URLs found in the sitemap.")

    # Generate recommendations
    recommendations: list[str] = []
    if thin_clusters:
        recommendations.append(
            "Expand thin clusters by creating additional supporting content. "
            "Aim for at least 3-5 pages per topic cluster."
        )
    if large_clusters:
        recommendations.append(
            "Consider splitting large clusters into sub-clusters. "
            "Over 20 pages in a single cluster may dilute topical focus."
        )
    if linking_gaps:
        recommendations.append(
            "Add internal links from pillar pages to all cluster pages. "
            "This strengthens topical authority and helps search engines understand content relationships."
        )
    if len(clusters) < 3 and len(page_urls) > 10:
        recommendations.append(
            "Create more distinct topic clusters. Your content volume suggests "
            "opportunities for additional topical silos."
        )
    if not recommendations:
        recommendations.append(
            "Your topic cluster structure is well-organized. "
            "Continue expanding clusters with supporting content."
        )

    return {
        "status": "success",
        "url": url,
        "timestamp": timestamp,
        "data": {
            "total_urls": len(page_urls),
            "clusters": clusters,
            "thin_clusters": thin_clusters,
            "large_clusters": large_clusters,
            "linking_gaps": linking_gaps,
        },
        "score": score,
        "issues": issues,
        "recommendations": recommendations,
    }
