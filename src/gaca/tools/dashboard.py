"""Audit comparison and dashboard tools for tracking SEO progress over time."""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _compare_dicts(audit1: dict, audit2: dict, label1: str = "before", label2: str = "after") -> dict:
    """Compare two audit result dicts and return a structured diff.

    This helper can be used programmatically when you have two audit JSON objects.

    Args:
        audit1: First (older) audit result dict.
        audit2: Second (newer) audit result dict.
        label1: Label for the first audit (e.g. date string).
        label2: Label for the second audit (e.g. date string).

    Returns:
        Dict with score_change, improvements, regressions, new_issues, resolved_issues.
    """
    result: dict = {
        "label_before": label1,
        "label_after": label2,
        "score_change": None,
        "improvements": [],
        "regressions": [],
        "new_issues": [],
        "resolved_issues": [],
        "metric_changes": {},
    }

    # --- Score comparison ---
    score1 = audit1.get("score")
    score2 = audit2.get("score")
    if isinstance(score1, (int, float)) and isinstance(score2, (int, float)):
        result["score_change"] = {
            "before": score1,
            "after": score2,
            "delta": round(score2 - score1, 2),
            "direction": "improved" if score2 > score1 else "declined" if score2 < score1 else "unchanged",
        }

    # --- Issue comparison ---
    issues1 = set(audit1.get("issues", []))
    issues2 = set(audit2.get("issues", []))
    result["new_issues"] = sorted(issues2 - issues1)
    result["resolved_issues"] = sorted(issues1 - issues2)

    # --- Data / metric comparison ---
    data1 = audit1.get("data", {})
    data2 = audit2.get("data", {})

    if isinstance(data1, dict) and isinstance(data2, dict):
        all_keys = set(data1.keys()) | set(data2.keys())
        for key in sorted(all_keys):
            val1 = data1.get(key)
            val2 = data2.get(key)
            # Only compare scalar numeric values
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                delta = round(val2 - val1, 4)
                pct_change = round((delta / val1) * 100, 1) if val1 != 0 else None
                entry = {
                    "before": val1,
                    "after": val2,
                    "delta": delta,
                    "pct_change": pct_change,
                }
                result["metric_changes"][key] = entry

                # Classify as improvement or regression for known directional metrics
                positive_higher = {
                    "total_clicks", "total_impressions", "avg_ctr", "score",
                    "unique_ips", "total_requests",
                }
                negative_higher = {
                    "avg_position", "crawl_errors", "wasted_requests_4xx_5xx",
                    "waste_pct",
                }

                if key in positive_higher:
                    if delta > 0:
                        result["improvements"].append(f"{key}: {val1} → {val2} (+{delta})")
                    elif delta < 0:
                        result["regressions"].append(f"{key}: {val1} → {val2} ({delta})")
                elif key in negative_higher:
                    if delta < 0:
                        result["improvements"].append(f"{key}: {val1} → {val2} ({delta})")
                    elif delta > 0:
                        result["regressions"].append(f"{key}: {val1} → {val2} (+{delta})")

    return result


def compare_audits(domain: str, date1: str, date2: str) -> dict:
    """Compare two historical audit snapshots for a domain to track SEO changes over time.

    Since gaca does not include persistent storage, this tool returns:
    1. A structured comparison template showing the expected format.
    2. Instructions on how to store and compare audit results.
    3. The ``_compare_dicts`` helper is available for programmatic use when
       audit JSON data is loaded from external files.

    Args:
        domain: The domain being compared.
        date1: Date label for the first (older) audit snapshot.
        date2: Date label for the second (newer) audit snapshot.

    Returns:
        Dict with status, instructions, and a comparison format template.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Build an example showing the output format
    example_comparison = _compare_dicts(
        audit1={
            "score": 6,
            "issues": ["Missing meta descriptions", "Slow TTFB", "No HTTPS redirect"],
            "data": {
                "total_clicks": 1200,
                "total_impressions": 45000,
                "avg_ctr": 2.7,
                "avg_position": 14.3,
            },
        },
        audit2={
            "score": 8,
            "issues": ["Slow TTFB", "Images not optimized"],
            "data": {
                "total_clicks": 1850,
                "total_impressions": 52000,
                "avg_ctr": 3.6,
                "avg_position": 11.1,
            },
        },
        label1=date1,
        label2=date2,
    )

    instructions = [
        "1. Run an audit tool (e.g. seo_audit_technical, seo_analyze_gsc) and save the JSON result to a file.",
        f"   Example: save as ~/output/audits/{domain}/{date1}.json",
        "2. Run the same audit at a later date and save that result too.",
        f"   Example: save as ~/output/audits/{domain}/{date2}.json",
        "3. Load both JSON files and call _compare_dicts(audit1, audit2) programmatically,",
        "   or paste both results into a conversation for manual comparison.",
        "4. The comparison will show: score changes, new/resolved issues, and metric deltas.",
    ]

    logger.info("Comparison template generated for %s (%s vs %s)", domain, date1, date2)

    return {
        "status": "success",
        "domain": domain,
        "timestamp": timestamp,
        "date1": date1,
        "date2": date2,
        "message": (
            "Seoleo does not include persistent audit storage. "
            "Save audit results as JSON files and use the comparison format below. "
            "The _compare_dicts() helper in gaca.tools.dashboard can diff two audit dicts programmatically."
        ),
        "instructions": instructions,
        "comparison_format_example": example_comparison,
        "usage_code": (
            "from gaca.tools.dashboard import _compare_dicts\n"
            "import json\n\n"
            f'with open("audit_{date1}.json") as f:\n'
            f"    audit1 = json.load(f)\n"
            f'with open("audit_{date2}.json") as f:\n'
            f"    audit2 = json.load(f)\n\n"
            f'diff = _compare_dicts(audit1, audit2, "{date1}", "{date2}")\n'
        ),
    }
