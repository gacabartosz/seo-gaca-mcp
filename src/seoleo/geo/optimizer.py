"""GEO Optimizer — suggest improvements based on Princeton methods."""

import re
from datetime import datetime, timezone

from seoleo.geo.analyzer import PRINCETON_METHODS, _avg_sentence_length


def optimize_geo(
    content: str,
    methods: list[str] | None = None,
    target_platform: str = "all",
) -> dict:
    """Provide GEO optimization suggestions for given content."""
    methods = methods or ["all"]
    words = content.split()
    word_count = len(words)

    if word_count < 20:
        return {
            "status": "error",
            "message": "Content too short for GEO analysis (min 20 words).",
        }

    suggestions: list[dict] = []

    if "all" in methods or "cite_sources" in methods:
        if not re.search(r"according to|research shows|\[\d+\]|source", content, re.I):
            suggestions.append({
                "method": "cite_sources",
                "priority": "P0",
                "uplift": "+40%",
                "suggestion": "Add authoritative citations. Example: 'According to [Source] (2024), ...' or add a References section at the end.",
            })

    if "all" in methods or "statistics" in methods:
        stat_count = len(re.findall(r"\d+(?:\.\d+)?%|\d+x\b", content))
        if stat_count < 2:
            suggestions.append({
                "method": "statistics",
                "priority": "P0",
                "uplift": "+37%",
                "suggestion": "Add specific data: '73% of users...', 'reduces load time by 2.5x', '$1.2M in savings'.",
            })

    if "all" in methods or "quotations" in methods:
        if not re.search(r'[""„"]', content):
            suggestions.append({
                "method": "quotations",
                "priority": "P1",
                "uplift": "+30%",
                "suggestion": "Add expert quotes: '\"This approach increases conversion by 40%\" — John Smith, CEO of Example Corp'.",
            })

    if "all" in methods or "authoritative_tone" in methods:
        hedging = len(re.findall(
            r"\b(?:maybe|perhaps|might|possibly|could be|seems|I think)\b", content, re.I
        ))
        if hedging > 2:
            suggestions.append({
                "method": "authoritative_tone",
                "priority": "P1",
                "uplift": "+25%",
                "suggestion": f"Remove {hedging} hedging phrases (maybe, perhaps, might). Replace with confident statements.",
            })

    if "all" in methods or "easy_language" in methods:
        avg_sent = _avg_sentence_length(content)
        if avg_sent > 25:
            suggestions.append({
                "method": "easy_language",
                "priority": "P1",
                "uplift": "+20%",
                "suggestion": f"Average sentence length is {avg_sent:.0f} words (target: <20). Break long sentences.",
            })

    if "all" in methods or "fluency" in methods:
        if not re.search(r"\n\s*[-*•]\s", content) and not re.search(r"\n\s*\d+\.\s", content):
            suggestions.append({
                "method": "fluency",
                "priority": "P2",
                "uplift": "+15%",
                "suggestion": "Add bullet points or numbered lists to improve scannability.",
            })

    # Platform-specific tips
    platform_tips: dict = {}
    if target_platform in ("all", "chatgpt"):
        platform_tips["chatgpt"] = "ChatGPT favors: domain authority, recent content (<30 days = 3.2x citations), FAQ format"
    if target_platform in ("all", "perplexity"):
        platform_tips["perplexity"] = "Perplexity favors: citation-dense content, FAQ schema, PDF content gets citation boost"
    if target_platform in ("all", "google_sge"):
        platform_tips["google_sge"] = "Google SGE favors: E-E-A-T signals, structured data, authoritative citations (+132% visibility)"
    if target_platform in ("all", "claude"):
        platform_tips["claude"] = "Claude uses Brave Search: factual density, clear headings, allow ClaudeBot in robots.txt"
    if target_platform in ("all", "copilot"):
        platform_tips["copilot"] = "Copilot/Bing: must be Bing-indexed, Microsoft ecosystem signals, <2s load time"

    return {
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "word_count": word_count,
        "suggestions": suggestions,
        "platform_tips": platform_tips,
        "total_potential_uplift": sum(
            int(s["uplift"].replace("+", "").replace("%", ""))
            for s in suggestions if s["uplift"].startswith("+")
        ),
    }
