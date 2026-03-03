"""AI crawler robots.txt analysis and generation."""

from datetime import datetime, timezone
from urllib.parse import urlparse

from gaca.core.collectors import fetch_robots

AI_CRAWLERS = {
    "GPTBot": {"org": "OpenAI", "purpose": "ChatGPT training + browsing plugins"},
    "ChatGPT-User": {"org": "OpenAI", "purpose": "ChatGPT live browsing"},
    "ClaudeBot": {"org": "Anthropic", "purpose": "Claude training data"},
    "anthropic-ai": {"org": "Anthropic", "purpose": "Claude training (legacy UA)"},
    "PerplexityBot": {"org": "Perplexity", "purpose": "Perplexity search engine"},
    "Google-Extended": {"org": "Google", "purpose": "Gemini/Bard training"},
    "Bytespider": {"org": "ByteDance", "purpose": "TikTok/AI training"},
    "CCBot": {"org": "Common Crawl", "purpose": "Open dataset used by many LLMs"},
    "cohere-ai": {"org": "Cohere", "purpose": "Cohere LLM training"},
    "FacebookBot": {"org": "Meta", "purpose": "Meta AI / Llama training"},
    "Applebot-Extended": {"org": "Apple", "purpose": "Apple Intelligence training"},
    "Amazonbot": {"org": "Amazon", "purpose": "Alexa / Amazon AI"},
    "YouBot": {"org": "You.com", "purpose": "You.com AI search"},
}


def check_ai_robots(url: str) -> dict:
    """Analyze robots.txt for AI crawler rules."""
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    robots_txt = fetch_robots(base_url)

    if robots_txt is None:
        return {
            "status": "success", "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "has_robots_txt": False,
            "message": "No robots.txt found — all AI crawlers are allowed by default",
            "crawlers": {name: {"status": "allowed", "reason": "no robots.txt"}
                        for name in AI_CRAWLERS},
        }

    results: dict = {}
    lines = robots_txt.lower().splitlines()

    for crawler_name, info in AI_CRAWLERS.items():
        status = _check_crawler_status(lines, crawler_name.lower())
        results[crawler_name] = {
            "org": info["org"],
            "purpose": info["purpose"],
            "status": status,
        }

    # Also check wildcard rules
    wildcard_disallow = _check_crawler_status(lines, "*")

    allowed_count = sum(1 for v in results.values() if v["status"] == "allowed")
    blocked_count = sum(1 for v in results.values() if v["status"] == "blocked")

    return {
        "status": "success",
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "has_robots_txt": True,
        "crawlers": results,
        "summary": {
            "total_ai_crawlers": len(AI_CRAWLERS),
            "allowed": allowed_count,
            "blocked": blocked_count,
            "wildcard_status": wildcard_disallow,
        },
        "recommendations": _ai_robots_recommendations(results),
    }


def _check_crawler_status(lines: list[str], ua_name: str) -> str:
    """Check if a specific user-agent is blocked in robots.txt lines."""
    in_block = False
    for line in lines:
        line = line.strip()
        if line.startswith("user-agent:"):
            agent = line.split(":", 1)[1].strip()
            in_block = agent == ua_name or agent == "*"
        elif in_block and line.startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            if path == "/" or path == "/*":
                return "blocked"
        elif in_block and line.startswith("allow:"):
            path = line.split(":", 1)[1].strip()
            if path == "/" or path == "/*":
                return "allowed"
        elif line == "" and in_block:
            in_block = False
    return "allowed"


def generate_ai_robots(strategy: str = "recommended", current_robots: str = "") -> dict:
    """Generate robots.txt rules for AI crawlers."""
    templates = {
        "allow_all": _template_allow_all(),
        "block_all": _template_block_all(),
        "selective": _template_selective(),
        "recommended": _template_recommended(),
    }

    if strategy not in templates:
        return {
            "status": "error",
            "message": f"Unknown strategy: {strategy}. Use: allow_all, block_all, selective, recommended",
        }

    rules = templates[strategy]

    if current_robots:
        merged = current_robots.rstrip() + "\n\n# === AI Crawler Rules (gaca-mcp) ===\n" + rules
    else:
        merged = rules

    return {
        "status": "success",
        "strategy": strategy,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "robots_txt": merged,
        "description": {
            "allow_all": "All AI crawlers allowed — maximum AI search visibility",
            "block_all": "All AI crawlers blocked — content protected from AI training",
            "selective": "Allow search-facing bots (ChatGPT, Perplexity), block training-only bots",
            "recommended": "Balanced approach — allow search bots, block pure training crawlers",
        }.get(strategy, ""),
    }


def _template_allow_all() -> str:
    return "# AI Crawlers: Allow All\n# Maximum AI search visibility\n\n"


def _template_block_all() -> str:
    lines = ["# AI Crawlers: Block All", "# Content protected from AI training", ""]
    for name in AI_CRAWLERS:
        lines.append(f"User-agent: {name}")
        lines.append("Disallow: /")
        lines.append("")
    return "\n".join(lines)


def _template_selective() -> str:
    allow = ["GPTBot", "ChatGPT-User", "PerplexityBot", "ClaudeBot", "Google-Extended"]
    block = [n for n in AI_CRAWLERS if n not in allow]

    lines = ["# AI Crawlers: Selective", "# Allow search-facing, block training-only", ""]
    lines.append("# Allowed: search-facing AI bots")
    for name in allow:
        lines.append(f"# {name} ({AI_CRAWLERS[name]['org']}) — allowed")
    lines.append("")
    lines.append("# Blocked: training-only bots")
    for name in block:
        lines.append(f"User-agent: {name}")
        lines.append("Disallow: /")
        lines.append("")
    return "\n".join(lines)


def _template_recommended() -> str:
    allow = ["GPTBot", "ChatGPT-User", "PerplexityBot", "ClaudeBot",
             "Google-Extended", "Applebot-Extended"]
    block = ["Bytespider", "CCBot", "cohere-ai"]

    lines = [
        "# AI Crawlers: Recommended Configuration (gaca-mcp)",
        "# Balance: visible in AI search, protected from mass scraping",
        "",
        "# Allow AI search engines (ChatGPT, Perplexity, Claude, Gemini, Apple)",
    ]
    for name in allow:
        lines.append(f"# {name} ({AI_CRAWLERS[name]['org']}) — allowed by default")
    lines.append("")
    lines.append("# Block mass-scraping bots")
    for name in block:
        lines.append(f"User-agent: {name}")
        lines.append("Disallow: /")
        lines.append("")
    return "\n".join(lines)


def _ai_robots_recommendations(crawlers: dict) -> list[str]:
    recs: list[str] = []
    search_bots = ["GPTBot", "ChatGPT-User", "PerplexityBot", "ClaudeBot", "Google-Extended"]
    for bot in search_bots:
        if crawlers.get(bot, {}).get("status") == "blocked":
            org = AI_CRAWLERS[bot]["org"]
            recs.append(
                f"[P1] {bot} ({org}) is blocked — you won't appear in {org}'s AI search results"
            )
    return recs
