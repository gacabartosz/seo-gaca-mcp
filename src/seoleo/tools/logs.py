"""Server log analysis tools for crawl budget and bot behavior insights."""

import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Combined log format regex
_LOG_RE = re.compile(
    r'^(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+) \S+" (\d+) (\d+|-) "([^"]*)" "([^"]*)"$'
)

# Bot identification rules: (substring_in_ua, bot_label)
_BOT_RULES: list[tuple[str, str]] = [
    # Google family
    ("Googlebot-Mobile", "Googlebot"),
    ("Googlebot", "Googlebot"),
    ("Google-InspectionTool", "Googlebot"),
    # Bing family
    ("bingbot", "Bingbot"),
    ("msnbot", "Bingbot"),
    # AI bots
    ("GPTBot", "GPTBot"),
    ("ChatGPT-User", "ChatGPT-User"),
    ("ClaudeBot", "ClaudeBot"),
    ("anthropic-ai", "ClaudeBot"),
    ("PerplexityBot", "PerplexityBot"),
    ("Bytespider", "Bytespider"),
    ("CCBot", "CCBot"),
    # Other bots
    ("YandexBot", "YandexBot"),
    ("Baiduspider", "Baiduspider"),
    ("DuckDuckBot", "DuckDuckBot"),
    ("Applebot", "Applebot"),
    ("facebookexternalhit", "FacebookBot"),
]


def _identify_bot(user_agent: str) -> str:
    """Return bot label from user-agent string, or 'human'."""
    for substring, label in _BOT_RULES:
        if substring in user_agent:
            return label
    ua_lower = user_agent.lower()
    if "bot" in ua_lower or "spider" in ua_lower or "crawl" in ua_lower:
        return "other_bot"
    return "human"


def _parse_log_datetime(dt_str: str) -> datetime | None:
    """Parse log datetime like '10/Oct/2024:13:55:36 +0000'."""
    try:
        return datetime.strptime(dt_str, "%d/%b/%Y:%H:%M:%S %z")
    except (ValueError, TypeError):
        return None


def analyze_logs(log_content: str, domain: str = "") -> dict:
    """Parse server access logs to surface crawl frequency, bot activity, and crawl budget waste."""
    timestamp = datetime.now(timezone.utc).isoformat()

    if not log_content or not log_content.strip():
        return {
            "status": "error",
            "message": "No log content provided. Paste raw Apache/Nginx combined-format access logs.",
            "timestamp": timestamp,
        }

    # --- Parse lines ---
    parsed_lines: list[dict] = []
    unparsed_count = 0

    for line in log_content.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _LOG_RE.match(line)
        if not m:
            unparsed_count += 1
            continue
        ip, dt_str, method, path, status, size_str, referrer, user_agent = m.groups()
        size = int(size_str) if size_str != "-" else 0
        parsed_lines.append({
            "ip": ip,
            "datetime": _parse_log_datetime(dt_str),
            "method": method,
            "path": path,
            "status": int(status),
            "size": size,
            "referrer": referrer,
            "user_agent": user_agent,
            "bot": _identify_bot(user_agent),
        })

    total_requests = len(parsed_lines)
    if total_requests == 0:
        return {
            "status": "error",
            "message": f"Could not parse any log lines ({unparsed_count} lines failed). "
                       "Expected Apache/Nginx combined log format.",
            "timestamp": timestamp,
        }

    # --- Basic counts ---
    unique_ips = len({e["ip"] for e in parsed_lines})

    # --- Bot vs human ---
    bot_entries = [e for e in parsed_lines if e["bot"] != "human"]
    human_entries = [e for e in parsed_lines if e["bot"] == "human"]

    bot_count = len(bot_entries)
    human_count = len(human_entries)
    bot_pct = round(bot_count / total_requests * 100, 1) if total_requests else 0
    human_pct = round(human_count / total_requests * 100, 1) if total_requests else 0

    # --- Bot breakdown ---
    bot_breakdown: dict[str, int] = dict(Counter(e["bot"] for e in bot_entries).most_common())

    # --- Status code distribution ---
    status_codes: dict[str, int] = {
        str(k): v for k, v in sorted(Counter(e["status"] for e in parsed_lines).items())
    }

    # --- Top 20 most crawled URLs (bot requests only) ---
    top_crawled_urls = [
        {"url": url, "requests": count}
        for url, count in Counter(e["path"] for e in bot_entries).most_common(20)
    ]

    # --- Crawl errors: 4xx/5xx URLs seen by bots ---
    error_entries = [e for e in bot_entries if e["status"] >= 400]
    crawl_errors_counter: Counter = Counter()
    error_status_map: dict[str, int] = {}
    for e in error_entries:
        crawl_errors_counter[e["path"]] += 1
        error_status_map[e["path"]] = e["status"]  # keep last seen status

    crawl_errors = [
        {"url": url, "requests": count, "status": error_status_map.get(url, 0)}
        for url, count in crawl_errors_counter.most_common(30)
    ]

    # --- Crawl frequency: requests per hour-of-day and per date ---
    hourly: dict[int, int] = defaultdict(int)
    daily: dict[str, int] = defaultdict(int)
    for e in bot_entries:
        dt = e["datetime"]
        if dt:
            hourly[dt.hour] += 1
            daily[dt.strftime("%Y-%m-%d")] += 1

    crawl_frequency = {
        "by_hour": {str(h): hourly[h] for h in sorted(hourly)},
        "by_day": {d: daily[d] for d in sorted(daily)},
    }

    # --- Crawl budget estimate ---
    total_bot_bytes = sum(e["size"] for e in bot_entries)
    crawl_budget_estimate = {
        "total_bot_requests": bot_count,
        "total_bot_bytes": total_bot_bytes,
        "total_bot_mb": round(total_bot_bytes / (1024 * 1024), 2),
        "wasted_requests_4xx_5xx": len(error_entries),
        "waste_pct": round(len(error_entries) / bot_count * 100, 1) if bot_count else 0,
    }

    # --- Score (1-10) ---
    issues: list[str] = []
    recommendations: list[str] = []

    score = 8  # start optimistic

    # High error rate
    waste_pct = crawl_budget_estimate["waste_pct"]
    if waste_pct > 20:
        score -= 3
        issues.append(f"High crawl waste: {waste_pct}% of bot requests hit 4xx/5xx errors.")
        recommendations.append("Fix or redirect URLs returning 4xx/5xx to bots — they consume crawl budget.")
    elif waste_pct > 10:
        score -= 2
        issues.append(f"Moderate crawl waste: {waste_pct}% of bot requests hit errors.")
        recommendations.append("Review 4xx/5xx URLs and add proper redirects or remove internal links to them.")
    elif waste_pct > 5:
        score -= 1
        issues.append(f"Some crawl waste: {waste_pct}% error rate for bots.")

    # AI bot traffic
    ai_bots = {"GPTBot", "ChatGPT-User", "ClaudeBot", "PerplexityBot", "Bytespider", "CCBot"}
    ai_bot_requests = sum(bot_breakdown.get(b, 0) for b in ai_bots)
    if ai_bot_requests > 0:
        ai_pct = round(ai_bot_requests / bot_count * 100, 1) if bot_count else 0
        issues.append(f"AI bots account for {ai_pct}% of bot traffic ({ai_bot_requests} requests).")
        recommendations.append(
            "Review robots.txt rules for AI crawlers. Consider allowing/blocking based on your GEO strategy."
        )

    # No Googlebot
    if "Googlebot" not in bot_breakdown:
        score -= 2
        issues.append("No Googlebot requests found in the log sample.")
        recommendations.append("Ensure Googlebot is not blocked in robots.txt and the site is indexable.")

    # Very high bot ratio
    if bot_pct > 80:
        score -= 1
        issues.append(f"Bots represent {bot_pct}% of traffic — unusually high ratio.")
        recommendations.append("Investigate if aggressive scrapers or unwanted bots should be blocked.")

    score = max(1, min(10, score))

    if not issues:
        issues.append("No significant crawl budget issues detected in this log sample.")
    if not recommendations:
        recommendations.append("Crawl budget looks healthy. Continue monitoring periodically.")

    data = {
        "domain": domain or "(not specified)",
        "total_requests": total_requests,
        "unparsed_lines": unparsed_count,
        "unique_ips": unique_ips,
        "bot_human_split": {
            "bot_requests": bot_count,
            "human_requests": human_count,
            "bot_pct": bot_pct,
            "human_pct": human_pct,
        },
        "bot_breakdown": bot_breakdown,
        "status_codes": status_codes,
        "top_crawled_urls": top_crawled_urls,
        "crawl_errors": crawl_errors,
        "crawl_frequency": crawl_frequency,
        "crawl_budget_estimate": crawl_budget_estimate,
    }

    logger.info(
        "Log analysis complete: %d requests, %d bot, %d human, score=%d",
        total_requests, bot_count, human_count, score,
    )

    return {
        "status": "success",
        "timestamp": timestamp,
        "data": data,
        "score": score,
        "issues": issues,
        "recommendations": recommendations,
    }
