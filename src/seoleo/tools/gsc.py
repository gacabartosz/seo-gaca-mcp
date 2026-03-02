"""Google Search Console data analysis tools."""

import csv
import io
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Possible header name variants (lowered) → canonical name
_HEADER_MAP: dict[str, str] = {
    "query": "query",
    "queries": "query",
    "top queries": "query",
    "search query": "query",
    "page": "page",
    "pages": "page",
    "url": "page",
    "landing page": "page",
    "clicks": "clicks",
    "total clicks": "clicks",
    "impressions": "impressions",
    "total impressions": "impressions",
    "ctr": "ctr",
    "average ctr": "ctr",
    "position": "position",
    "average position": "position",
    "date": "date",
}


def _normalize_header(raw: str) -> str:
    """Map a raw CSV header to a canonical field name."""
    cleaned = raw.strip().strip("\ufeff").lower()
    return _HEADER_MAP.get(cleaned, cleaned)


def _parse_number(val: str) -> float:
    """Parse numeric strings like '1,234', '3.5%', '< 1'."""
    val = val.strip()
    if not val or val == "--" or val == "n/a":
        return 0.0
    # Remove percentage sign
    val = val.replace("%", "")
    # Remove thousand separators (comma when used as grouping, not decimal)
    # Heuristic: if there's both comma and dot, comma is grouping
    if "," in val and "." in val:
        val = val.replace(",", "")
    elif "," in val:
        # Could be grouping or decimal — check pattern
        # "1,234" → grouping; "3,5" → decimal (EU)
        parts = val.split(",")
        if len(parts) == 2 and len(parts[1]) == 3:
            val = val.replace(",", "")  # grouping
        else:
            val = val.replace(",", ".")  # decimal
    val = val.replace("<", "").replace(">", "").strip()
    try:
        return float(val)
    except ValueError:
        return 0.0


def _detect_delimiter(content: str) -> str:
    """Detect whether content is tab-separated or comma-separated."""
    first_line = content.split("\n", 1)[0]
    if "\t" in first_line:
        return "\t"
    return ","


def analyze_gsc(csv_content: str, domain: str = "") -> dict:
    """Analyze exported Google Search Console CSV data for clicks, impressions, CTR, and position trends."""
    timestamp = datetime.now(timezone.utc).isoformat()

    if not csv_content or not csv_content.strip():
        return {
            "status": "error",
            "message": "No CSV content provided. Export data from Google Search Console "
                       "(Performance > Queries or Pages) and paste the CSV content.",
            "timestamp": timestamp,
        }

    # --- Parse CSV ---
    delimiter = _detect_delimiter(csv_content)
    reader = csv.DictReader(io.StringIO(csv_content), delimiter=delimiter)

    if not reader.fieldnames:
        return {
            "status": "error",
            "message": "Could not detect CSV headers. Ensure the first row contains column names.",
            "timestamp": timestamp,
        }

    # Map raw headers to canonical names
    header_mapping: dict[str, str] = {}
    for raw_header in reader.fieldnames:
        canonical = _normalize_header(raw_header)
        header_mapping[raw_header] = canonical

    canonical_fields = set(header_mapping.values())
    has_query = "query" in canonical_fields
    has_page = "page" in canonical_fields
    has_date = "date" in canonical_fields
    has_clicks = "clicks" in canonical_fields
    has_impressions = "impressions" in canonical_fields
    has_ctr = "ctr" in canonical_fields
    has_position = "position" in canonical_fields

    if not has_clicks and not has_impressions:
        return {
            "status": "error",
            "message": "CSV must contain at least Clicks or Impressions columns. "
                       f"Found columns: {list(reader.fieldnames)}",
            "timestamp": timestamp,
        }

    # Build a reverse map: canonical → raw header name
    canon_to_raw: dict[str, str] = {}
    for raw, canon in header_mapping.items():
        canon_to_raw.setdefault(canon, raw)

    rows: list[dict] = []
    for row in reader:
        parsed: dict = {}
        for raw_header, value in row.items():
            canon = header_mapping.get(raw_header, raw_header)
            if canon in ("clicks", "impressions", "ctr", "position"):
                parsed[canon] = _parse_number(value)
            else:
                parsed[canon] = value.strip() if value else ""
        rows.append(parsed)

    if not rows:
        return {
            "status": "error",
            "message": "CSV parsed but contains no data rows.",
            "timestamp": timestamp,
        }

    # --- Aggregates ---
    total_clicks = sum(r.get("clicks", 0) for r in rows)
    total_impressions = sum(r.get("impressions", 0) for r in rows)
    avg_ctr = round(total_clicks / total_impressions * 100, 2) if total_impressions else 0.0
    positions = [r["position"] for r in rows if r.get("position", 0) > 0]
    avg_position = round(sum(positions) / len(positions), 1) if positions else 0.0

    # --- Top queries/pages by clicks and impressions ---
    sort_key_clicks = lambda r: r.get("clicks", 0)
    sort_key_impressions = lambda r: r.get("impressions", 0)

    label = "query" if has_query else "page" if has_page else "item"

    top_by_clicks = sorted(rows, key=sort_key_clicks, reverse=True)[:20]
    top_queries_clicks = [
        {
            label: r.get(label, ""),
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": r.get("ctr", 0),
            "position": r.get("position", 0),
        }
        for r in top_by_clicks
    ]

    top_by_impressions = sorted(rows, key=sort_key_impressions, reverse=True)[:20]
    top_queries_impressions = [
        {
            label: r.get(label, ""),
            "impressions": r.get("impressions", 0),
            "clicks": r.get("clicks", 0),
            "ctr": r.get("ctr", 0),
            "position": r.get("position", 0),
        }
        for r in top_by_impressions
    ]

    # --- CTR by position range ---
    position_groups: dict[str, list[float]] = {
        "1-3": [],
        "4-10": [],
        "11-20": [],
        "21+": [],
    }
    for r in rows:
        pos = r.get("position", 0)
        ctr_val = r.get("ctr", 0)
        if pos <= 0:
            continue
        if pos <= 3:
            position_groups["1-3"].append(ctr_val)
        elif pos <= 10:
            position_groups["4-10"].append(ctr_val)
        elif pos <= 20:
            position_groups["11-20"].append(ctr_val)
        else:
            position_groups["21+"].append(ctr_val)

    ctr_by_position = {}
    for group, values in position_groups.items():
        ctr_by_position[group] = {
            "avg_ctr": round(sum(values) / len(values), 2) if values else 0,
            "count": len(values),
        }

    # --- Below-benchmark CTR ---
    below_benchmark: list[dict] = []
    for r in rows:
        pos = r.get("position", 0)
        ctr_val = r.get("ctr", 0)
        item_label = r.get(label, "")
        if 0 < pos <= 3 and ctr_val < 5:
            below_benchmark.append({
                label: item_label,
                "position": pos,
                "ctr": ctr_val,
                "benchmark": 5.0,
                "gap": round(5.0 - ctr_val, 2),
            })
        elif 3 < pos <= 10 and ctr_val < 2:
            below_benchmark.append({
                label: item_label,
                "position": pos,
                "ctr": ctr_val,
                "benchmark": 2.0,
                "gap": round(2.0 - ctr_val, 2),
            })
    below_benchmark.sort(key=lambda x: x["gap"], reverse=True)
    below_benchmark = below_benchmark[:20]

    # --- Opportunity keywords: high impressions, low CTR, mid position ---
    opportunities: list[dict] = []
    for r in rows:
        imp = r.get("impressions", 0)
        ctr_val = r.get("ctr", 0)
        pos = r.get("position", 0)
        if imp > 100 and ctr_val < 2 and 5 <= pos <= 20:
            opportunities.append({
                label: r.get(label, ""),
                "impressions": imp,
                "clicks": r.get("clicks", 0),
                "ctr": ctr_val,
                "position": pos,
            })
    opportunities.sort(key=lambda x: x["impressions"], reverse=True)
    opportunities = opportunities[:20]

    # --- Keyword cannibalization (only if both query and page columns exist) ---
    cannibalization: list[dict] = []
    if has_query and has_page:
        query_pages: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            q = r.get("query", "")
            p = r.get("page", "")
            if q and p:
                query_pages[q].append({
                    "page": p,
                    "clicks": r.get("clicks", 0),
                    "impressions": r.get("impressions", 0),
                    "position": r.get("position", 0),
                })
        for query, pages in query_pages.items():
            unique_pages = {p["page"] for p in pages}
            if len(unique_pages) > 1:
                cannibalization.append({
                    "query": query,
                    "pages": sorted(pages, key=lambda x: x["clicks"], reverse=True),
                    "page_count": len(unique_pages),
                })
        cannibalization.sort(key=lambda x: x["page_count"], reverse=True)
        cannibalization = cannibalization[:20]

    # --- Declining queries (only if date dimension exists) ---
    declining: list[dict] = []
    if has_date and has_query:
        # Group clicks by query per date, compare first half vs second half
        query_date_clicks: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for r in rows:
            q = r.get("query", "")
            d = r.get("date", "")
            if q and d:
                query_date_clicks[q][d] += r.get("clicks", 0)

        for query, date_clicks in query_date_clicks.items():
            sorted_dates = sorted(date_clicks.keys())
            if len(sorted_dates) < 4:
                continue
            mid = len(sorted_dates) // 2
            first_half = sum(date_clicks[d] for d in sorted_dates[:mid])
            second_half = sum(date_clicks[d] for d in sorted_dates[mid:])
            if first_half > 0 and second_half < first_half * 0.7:
                decline_pct = round((1 - second_half / first_half) * 100, 1)
                declining.append({
                    "query": query,
                    "first_half_clicks": first_half,
                    "second_half_clicks": second_half,
                    "decline_pct": decline_pct,
                })
        declining.sort(key=lambda x: x["decline_pct"], reverse=True)
        declining = declining[:20]

    # --- Score (1-10) ---
    score = 7
    issues: list[str] = []
    recommendations: list[str] = []

    if avg_ctr < 2:
        score -= 2
        issues.append(f"Average CTR is very low ({avg_ctr}%). Titles and meta descriptions may need improvement.")
        recommendations.append("Rewrite title tags and meta descriptions for top-impression queries to boost CTR.")
    elif avg_ctr < 4:
        score -= 1
        issues.append(f"Average CTR ({avg_ctr}%) is below typical benchmarks.")

    if avg_position > 20:
        score -= 2
        issues.append(f"Average position ({avg_position}) is beyond page 2 — limited visibility.")
        recommendations.append("Focus on content quality and link building for high-impression queries.")
    elif avg_position > 10:
        score -= 1
        issues.append(f"Average position ({avg_position}) is on page 2.")

    if len(opportunities) > 5:
        score -= 1
        issues.append(f"{len(opportunities)} opportunity keywords found (high impressions, low CTR, position 5-20).")
        recommendations.append(
            "Optimize content and on-page SEO for opportunity keywords — they have volume but low CTR."
        )

    if len(cannibalization) > 3:
        score -= 1
        issues.append(f"{len(cannibalization)} keyword cannibalization cases detected.")
        recommendations.append(
            "Consolidate or differentiate pages competing for the same queries to avoid cannibalization."
        )

    if len(declining) > 5:
        score -= 1
        issues.append(f"{len(declining)} queries show declining traffic.")
        recommendations.append("Refresh content for declining queries — update dates, add new info, improve depth.")

    if len(below_benchmark) > 5:
        issues.append(f"{len(below_benchmark)} queries have CTR below position benchmarks.")
        recommendations.append("Improve SERP snippets (titles, descriptions, structured data) for below-benchmark CTR queries.")

    score = max(1, min(10, score))

    if not issues:
        issues.append("GSC data looks healthy. No major issues detected in this export.")
    if not recommendations:
        recommendations.append("Continue monitoring GSC data weekly for trends and new opportunities.")

    data = {
        "domain": domain or "(not specified)",
        "total_rows": len(rows),
        "total_queries": len({r.get("query", "") for r in rows if r.get("query")}) if has_query else None,
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "avg_ctr": avg_ctr,
        "avg_position": avg_position,
        "top_queries_clicks": top_queries_clicks,
        "top_queries_impressions": top_queries_impressions,
        "ctr_by_position": ctr_by_position,
        "below_benchmark_ctr": below_benchmark,
        "opportunities": opportunities,
        "cannibalization": cannibalization if cannibalization else None,
        "declining": declining if declining else None,
    }

    logger.info(
        "GSC analysis complete: %d rows, %d clicks, %d impressions, avg_ctr=%.2f%%, score=%d",
        len(rows), total_clicks, total_impressions, avg_ctr, score,
    )

    return {
        "status": "success",
        "timestamp": timestamp,
        "data": data,
        "score": score,
        "recommendations": recommendations,
    }
