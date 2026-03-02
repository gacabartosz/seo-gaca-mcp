"""Competitor analysis tools for benchmarking SEO performance."""

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from seoleo.core.collectors import fetch_headers, fetch_html
from seoleo.core.config import config
from seoleo.core.parsers import parse_headings, parse_images, parse_links, parse_meta_tags, parse_schema

logger = logging.getLogger(__name__)

SECURITY_HEADERS = [
    "strict-transport-security",
    "content-security-policy",
    "x-content-type-options",
    "x-frame-options",
    "x-xss-protection",
    "referrer-policy",
    "permissions-policy",
    "cross-origin-opener-policy",
    "cross-origin-resource-policy",
]


def _extract_body_word_count(html: str) -> int:
    """Count words in the visible body text."""
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body")
    if not body:
        return 0
    for tag in body.find_all(["script", "style", "noscript"]):
        tag.decompose()
    text = body.get_text(separator=" ", strip=True)
    return len(text.split())


def _count_security_headers(headers: dict) -> dict:
    """Count present security headers and list them."""
    lower_headers = {k.lower(): v for k, v in headers.items()}
    present = [h for h in SECURITY_HEADERS if h in lower_headers]
    return {
        "present_count": len(present),
        "total_checked": len(SECURITY_HEADERS),
        "present": present,
        "missing": [h for h in SECURITY_HEADERS if h not in lower_headers],
    }


def _analyze_site(url: str) -> dict | None:
    """Fetch and analyze a single site, returning structured metrics."""
    html, status_code, _ = fetch_html(url)
    if html is None:
        logger.warning("Could not fetch %s (status %d)", url, status_code)
        return None

    meta = parse_meta_tags(html)
    headings = parse_headings(html)
    images = parse_images(html, base_url=url)
    links = parse_links(html, base_url=url)
    schema = parse_schema(html)
    word_count = _extract_body_word_count(html)

    resp_headers, _ = fetch_headers(url)
    security = _count_security_headers(resp_headers)

    h1_count = len(headings.get("h1", []))
    h2_count = len(headings.get("h2", []))
    total_headings = sum(len(v) for v in headings.values())

    img_total = images.get("count", 0)
    img_without_alt = images.get("without_alt", 0)
    img_with_alt = img_total - img_without_alt

    jsonld_types = []
    for item in schema.get("json_ld", []):
        if isinstance(item, dict):
            t = item.get("@type")
            if t:
                if isinstance(t, list):
                    jsonld_types.extend(t)
                else:
                    jsonld_types.append(t)

    return {
        "url": url,
        "meta": {
            "title": meta.get("title"),
            "title_length": meta.get("title_length", 0),
            "description": meta.get("description"),
            "description_length": meta.get("description_length", 0),
            "canonical": meta.get("canonical"),
        },
        "headings": {
            "h1_count": h1_count,
            "h2_count": h2_count,
            "total_headings": total_headings,
        },
        "images": {
            "total": img_total,
            "with_alt": img_with_alt,
            "missing_alt": img_without_alt,
        },
        "links": {
            "total_internal": len(links.get("internal", [])),
            "total_external": len(links.get("external", [])),
        },
        "schema": {
            "json_ld_types": jsonld_types,
        },
        "content": {
            "word_count": word_count,
        },
        "security_headers": security,
    }


def _determine_winner(client_val, competitor_val, higher_is_better: bool = True) -> str:
    """Determine winner between two numeric values."""
    if client_val == competitor_val:
        return "tie"
    if higher_is_better:
        return "client" if client_val > competitor_val else "competitor"
    return "client" if client_val < competitor_val else "competitor"


def _build_comparison(client_data: dict, competitor_data: dict) -> dict:
    """Build a per-category comparison between client and a single competitor."""
    categories: dict = {}

    # Title length (closer to 50-60 ideal)
    client_tl = client_data["meta"]["title_length"]
    comp_tl = competitor_data["meta"]["title_length"]
    client_title_score = 10 - abs(55 - client_tl) / 5.5 if client_tl else 0
    comp_title_score = 10 - abs(55 - comp_tl) / 5.5 if comp_tl else 0
    categories["title_optimization"] = {
        "client_score": round(max(0, client_title_score), 1),
        "competitor_score": round(max(0, comp_title_score), 1),
        "winner": _determine_winner(client_title_score, comp_title_score),
    }

    # Description length (closer to 150-160 ideal)
    client_dl = client_data["meta"]["description_length"]
    comp_dl = competitor_data["meta"]["description_length"]
    client_desc_score = 10 - abs(155 - client_dl) / 15.5 if client_dl else 0
    comp_desc_score = 10 - abs(155 - comp_dl) / 15.5 if comp_dl else 0
    categories["description_optimization"] = {
        "client_score": round(max(0, client_desc_score), 1),
        "competitor_score": round(max(0, comp_desc_score), 1),
        "winner": _determine_winner(client_desc_score, comp_desc_score),
    }

    # Heading structure
    client_h_score = min(10, client_data["headings"]["h1_count"] * 3 + client_data["headings"]["h2_count"])
    comp_h_score = min(10, competitor_data["headings"]["h1_count"] * 3 + competitor_data["headings"]["h2_count"])
    categories["heading_structure"] = {
        "client_score": client_h_score,
        "competitor_score": comp_h_score,
        "winner": _determine_winner(client_h_score, comp_h_score),
    }

    # Image alt coverage
    c_img = client_data["images"]
    co_img = competitor_data["images"]
    client_alt_pct = (c_img["with_alt"] / c_img["total"] * 10) if c_img["total"] > 0 else 0
    comp_alt_pct = (co_img["with_alt"] / co_img["total"] * 10) if co_img["total"] > 0 else 0
    categories["image_alt_coverage"] = {
        "client_score": round(client_alt_pct, 1),
        "competitor_score": round(comp_alt_pct, 1),
        "winner": _determine_winner(client_alt_pct, comp_alt_pct),
    }

    # Internal linking
    categories["internal_linking"] = {
        "client_score": min(10, client_data["links"]["total_internal"] // 5),
        "competitor_score": min(10, competitor_data["links"]["total_internal"] // 5),
        "winner": _determine_winner(
            client_data["links"]["total_internal"],
            competitor_data["links"]["total_internal"],
        ),
    }

    # Schema markup
    client_schema_score = min(10, len(client_data["schema"]["json_ld_types"]) * 3)
    comp_schema_score = min(10, len(competitor_data["schema"]["json_ld_types"]) * 3)
    categories["schema_markup"] = {
        "client_score": client_schema_score,
        "competitor_score": comp_schema_score,
        "winner": _determine_winner(client_schema_score, comp_schema_score),
    }

    # Content depth (word count)
    categories["content_depth"] = {
        "client_score": min(10, client_data["content"]["word_count"] // 100),
        "competitor_score": min(10, competitor_data["content"]["word_count"] // 100),
        "winner": _determine_winner(
            client_data["content"]["word_count"],
            competitor_data["content"]["word_count"],
        ),
    }

    # Security headers
    categories["security_headers"] = {
        "client_score": round(client_data["security_headers"]["present_count"] / len(SECURITY_HEADERS) * 10, 1),
        "competitor_score": round(competitor_data["security_headers"]["present_count"] / len(SECURITY_HEADERS) * 10, 1),
        "winner": _determine_winner(
            client_data["security_headers"]["present_count"],
            competitor_data["security_headers"]["present_count"],
        ),
    }

    return categories


def _generate_recommendations(client_data: dict, comparisons: list[dict]) -> list[str]:
    """Generate actionable recommendations based on comparison results."""
    recs: list[str] = []

    # Aggregate losses across all competitors
    loss_counts: dict[str, int] = {}
    for comp in comparisons:
        for cat_name, cat_data in comp.get("categories", {}).items():
            if cat_data.get("winner") == "competitor":
                loss_counts[cat_name] = loss_counts.get(cat_name, 0) + 1

    if loss_counts.get("title_optimization", 0) > 0:
        recs.append(
            f"Optimize title tag length (currently {client_data['meta']['title_length']} chars). "
            "Aim for 50-60 characters for best SERP display."
        )

    if loss_counts.get("description_optimization", 0) > 0:
        recs.append(
            f"Improve meta description (currently {client_data['meta']['description_length']} chars). "
            "Target 150-160 characters with a compelling call-to-action."
        )

    if loss_counts.get("heading_structure", 0) > 0:
        recs.append(
            f"Strengthen heading structure (H1: {client_data['headings']['h1_count']}, "
            f"H2: {client_data['headings']['h2_count']}). "
            "Competitors use more structured headings."
        )

    if loss_counts.get("image_alt_coverage", 0) > 0:
        recs.append(
            f"Add alt text to {client_data['images']['missing_alt']} images. "
            "Competitors have better image accessibility."
        )

    if loss_counts.get("internal_linking", 0) > 0:
        recs.append(
            f"Increase internal links (currently {client_data['links']['total_internal']}). "
            "Competitors have stronger internal linking."
        )

    if loss_counts.get("schema_markup", 0) > 0:
        recs.append(
            "Add more structured data (JSON-LD). "
            "Competitors use richer schema markup for enhanced SERP features."
        )

    if loss_counts.get("content_depth", 0) > 0:
        recs.append(
            f"Expand content (currently {client_data['content']['word_count']} words). "
            "Competitors publish more in-depth content on their pages."
        )

    if loss_counts.get("security_headers", 0) > 0:
        missing = client_data["security_headers"].get("missing", [])
        if missing:
            recs.append(
                f"Add missing security headers: {', '.join(missing[:3])}. "
                "Security signals contribute to trust and ranking."
            )

    if not recs:
        recs.append("Your site performs well across all compared categories. Continue monitoring competitors.")

    return recs


def compare_competitors(
    client_url: str,
    competitor_urls: list,
    include_lighthouse: bool = False,
) -> dict:
    """Compare a client site against competitor URLs across key SEO metrics.

    Args:
        client_url: The client's URL to audit.
        competitor_urls: List of up to 3 competitor URLs to compare against.
        include_lighthouse: If True and Lighthouse is available, include performance scores.

    Returns:
        Dict with status, timestamp, data (client metrics, competitor metrics,
        comparison table, wins/losses), and recommendations.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Limit to 3 competitors
    competitor_urls = competitor_urls[:3]

    # Analyze client site
    client_data = _analyze_site(client_url)
    if client_data is None:
        return {
            "status": "error",
            "message": f"Could not fetch client URL: {client_url}",
            "timestamp": timestamp,
        }

    # Analyze competitors
    competitor_results: list[dict] = []
    for comp_url in competitor_urls:
        comp_data = _analyze_site(comp_url)
        if comp_data is not None:
            competitor_results.append(comp_data)
        else:
            logger.warning("Skipping unreachable competitor: %s", comp_url)

    if not competitor_results:
        return {
            "status": "error",
            "message": "Could not fetch any competitor URLs.",
            "timestamp": timestamp,
            "data": {"client": client_data},
        }

    # Build comparisons
    comparisons: list[dict] = []
    total_wins = 0
    total_losses = 0
    total_ties = 0

    for comp_data in competitor_results:
        categories = _build_comparison(client_data, comp_data)
        wins = sum(1 for c in categories.values() if c["winner"] == "client")
        losses = sum(1 for c in categories.values() if c["winner"] == "competitor")
        ties = sum(1 for c in categories.values() if c["winner"] == "tie")
        total_wins += wins
        total_losses += losses
        total_ties += ties

        comparisons.append({
            "competitor_url": comp_data["url"],
            "categories": categories,
            "wins": wins,
            "losses": losses,
            "ties": ties,
        })

    # Optional Lighthouse
    lighthouse_data: dict | None = None
    if include_lighthouse and config.has_lighthouse:
        try:
            from seoleo.core.lighthouse import run_lighthouse

            all_urls = [client_url] + [c["url"] for c in competitor_results]
            lighthouse_data = {}
            for lh_url in all_urls:
                try:
                    lh_result = run_lighthouse(lh_url)
                    lighthouse_data[lh_url] = lh_result
                except Exception as e:
                    logger.warning("Lighthouse failed for %s: %s", lh_url, e)
        except ImportError:
            logger.warning("Lighthouse module not available")

    # Generate recommendations
    recommendations = _generate_recommendations(client_data, comparisons)

    result: dict = {
        "status": "success",
        "timestamp": timestamp,
        "data": {
            "client": client_data,
            "competitors": competitor_results,
            "comparison": comparisons,
            "wins": total_wins,
            "losses": total_losses,
            "ties": total_ties,
        },
        "recommendations": recommendations,
    }

    if lighthouse_data:
        result["data"]["lighthouse"] = lighthouse_data

    return result
