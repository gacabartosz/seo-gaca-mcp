"""GEO Analyzer — audit content for AI search citation readiness.

Based on Princeton research (arXiv:2311.09735, KDD 2024):
9 methods that measurably increase AI search citation probability.
"""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from seoleo.core.collectors import fetch_html, fetch_robots
from seoleo.core.parsers import parse_meta_tags, parse_schema, parse_headings

# Princeton 9 GEO methods with measured uplift percentages
PRINCETON_METHODS = {
    "cite_sources": {
        "name": "Cite Sources",
        "uplift": 40,
        "description": "Add authoritative references, inline citations, bibliography",
    },
    "statistics": {
        "name": "Statistics",
        "uplift": 37,
        "description": "Include specific numbers, percentages, research data",
    },
    "quotations": {
        "name": "Quotations",
        "uplift": 30,
        "description": "Expert quotes with attribution",
    },
    "authoritative_tone": {
        "name": "Authoritative Tone",
        "uplift": 25,
        "description": "Confident, expert language without hedging",
    },
    "easy_language": {
        "name": "Easy Language",
        "uplift": 20,
        "description": "Accessible explanations, clear structure",
    },
    "technical_terms": {
        "name": "Technical Terms",
        "uplift": 18,
        "description": "Domain-specific vocabulary demonstrating expertise",
    },
    "unique_words": {
        "name": "Unique Words",
        "uplift": 15,
        "description": "Vocabulary diversity, avoid repetition",
    },
    "fluency": {
        "name": "Fluency Optimization",
        "uplift": 15,
        "description": "Natural language quality, readability, flow",
    },
    "keyword_stuffing": {
        "name": "Keyword Stuffing (AVOID)",
        "uplift": -10,
        "description": "Actively avoid — degrades AI citation probability",
    },
}

# Patterns for detecting Princeton method signals
_CITATION_PATTERNS = [
    r"\baccording to\b", r"\bresearch (?:shows|indicates|suggests)\b",
    r"\bstudy (?:by|from|published)\b", r"\b(?:source|ref|reference)s?\b",
    r"\[\d+\]", r"\(\d{4}\)", r"\bcited?\b",
    r"\bwedług\b", r"\bbadania (?:pokazują|wskazują)\b",
]

_STATISTIC_PATTERNS = [
    r"\d+(?:\.\d+)?%", r"\d+(?:,\d+)?\s*(?:mln|mld|tys)",
    r"\$\d+", r"€\d+", r"\d+x\b", r"\d+\s*(?:razy|times|percent)",
]

_QUOTE_PATTERNS = [
    r'[\u201c\u201d\u0022].*?[\u201c\u201d\u0022]',
    r'\u201e.*?\u201d',
    r'\u2014\s*\w+',
]

_HEDGING_WORDS = [
    "maybe", "perhaps", "might", "possibly", "could be", "seems",
    "może", "być może", "prawdopodobnie", "wydaje się",
]


def audit_geo(url: str, target_platforms: list[str] | None = None) -> dict:
    """Full GEO audit using Princeton 9 methods."""
    target_platforms = target_platforms or ["all"]

    html, status, headers = fetch_html(url)
    if not html:
        return {
            "status": "error", "url": url,
            "message": f"Failed to fetch page (status: {status})",
        }

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body")
    text = body.get_text(separator=" ", strip=True) if body else ""
    words = text.split()
    word_count = len(words)

    meta = parse_meta_tags(html)
    schema = parse_schema(html)
    headings = parse_headings(html)

    # Analyze each Princeton method
    method_scores: dict = {}

    # 1. Cite Sources (+40%)
    citation_count = sum(
        len(re.findall(p, text, re.I)) for p in _CITATION_PATTERNS
    )
    cite_score = min(10, citation_count * 2) if word_count > 0 else 0
    method_scores["cite_sources"] = {
        "score": cite_score, "citations_found": citation_count,
        "recommendation": "Add inline citations, references, and bibliography"
        if cite_score < 7 else "Good citation density",
    }

    # 2. Statistics (+37%)
    stat_count = sum(
        len(re.findall(p, text, re.I)) for p in _STATISTIC_PATTERNS
    )
    stat_score = min(10, stat_count * 2) if word_count > 0 else 0
    method_scores["statistics"] = {
        "score": stat_score, "statistics_found": stat_count,
        "recommendation": "Add specific numbers, percentages, and data points"
        if stat_score < 7 else "Good statistical density",
    }

    # 3. Quotations (+30%)
    quote_count = sum(
        len(re.findall(p, text)) for p in _QUOTE_PATTERNS
    )
    quote_score = min(10, quote_count * 3) if word_count > 0 else 0
    method_scores["quotations"] = {
        "score": quote_score, "quotes_found": quote_count,
        "recommendation": "Add expert quotes with attribution"
        if quote_score < 7 else "Good use of quotations",
    }

    # 4. Authoritative Tone (+25%)
    hedging_count = sum(
        len(re.findall(r"\b" + w + r"\b", text, re.I)) for w in _HEDGING_WORDS
    )
    hedging_ratio = hedging_count / max(word_count, 1)
    auth_score = max(1, 10 - int(hedging_ratio * 500))
    method_scores["authoritative_tone"] = {
        "score": min(10, auth_score), "hedging_words": hedging_count,
        "recommendation": "Reduce hedging language (maybe, perhaps, might)"
        if auth_score < 7 else "Strong authoritative tone",
    }

    # 5. Easy Language (+20%)
    avg_sentence_len = _avg_sentence_length(text)
    easy_score = 10 if avg_sentence_len < 20 else max(1, 10 - int((avg_sentence_len - 20) / 3))
    method_scores["easy_language"] = {
        "score": min(10, easy_score), "avg_sentence_length": round(avg_sentence_len, 1),
        "recommendation": "Shorten sentences for better readability"
        if easy_score < 7 else "Good readability",
    }

    # 6. Technical Terms (+18%)
    unique_words_set = set(w.lower() for w in words if len(w) > 6)
    long_word_ratio = len(unique_words_set) / max(word_count, 1)
    tech_score = min(10, int(long_word_ratio * 50))
    method_scores["technical_terms"] = {
        "score": max(1, tech_score), "technical_terms_count": len(unique_words_set),
        "recommendation": "Include more domain-specific terminology"
        if tech_score < 7 else "Good use of technical terms",
    }

    # 7. Unique Words (+15%)
    all_lower = [w.lower() for w in words]
    unique_ratio = len(set(all_lower)) / max(len(all_lower), 1)
    uniq_score = min(10, int(unique_ratio * 15))
    method_scores["unique_words"] = {
        "score": max(1, uniq_score), "unique_ratio": round(unique_ratio, 3),
        "recommendation": "Diversify vocabulary, avoid word repetition"
        if uniq_score < 7 else "Good vocabulary diversity",
    }

    # 8. Fluency (+15%)
    h_count = sum(len(v) for v in headings.values())
    has_lists = bool(soup.find_all(["ul", "ol"]))
    fluency_score = 5
    if h_count >= 3:
        fluency_score += 2
    if has_lists:
        fluency_score += 1
    if word_count > 300:
        fluency_score += 1
    if avg_sentence_len < 25:
        fluency_score += 1
    method_scores["fluency"] = {
        "score": min(10, fluency_score),
        "headings_count": h_count, "has_lists": has_lists,
        "recommendation": "Improve content structure with headings and lists"
        if fluency_score < 7 else "Good content flow",
    }

    # 9. Keyword Stuffing (-10%)
    # Check for excessive repetition of any single word
    from collections import Counter
    word_freq = Counter(all_lower)
    most_common = word_freq.most_common(1)
    stuffing_detected = False
    if most_common and word_count > 50:
        top_word, top_count = most_common[0]
        if len(top_word) > 3 and top_count / word_count > 0.05:
            stuffing_detected = True
    method_scores["keyword_stuffing"] = {
        "detected": stuffing_detected,
        "recommendation": "Reduce keyword repetition — it hurts AI citation"
        if stuffing_detected else "No keyword stuffing detected",
    }

    # Schema analysis for GEO
    json_ld_types = [s.get("@type", "") for s in schema.get("json_ld", [])]
    has_faq = "FAQPage" in json_ld_types
    has_article = any(t in json_ld_types for t in ["Article", "NewsArticle", "BlogPosting"])

    # Overall GEO score
    scorable = [v["score"] for k, v in method_scores.items() if "score" in v]
    overall_geo = round(sum(scorable) / len(scorable), 1) if scorable else 0

    return {
        "status": "success",
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_geo_score": overall_geo,
        "word_count": word_count,
        "method_scores": method_scores,
        "schema": {
            "has_faq": has_faq,
            "has_article": has_article,
            "json_ld_types": json_ld_types,
            "faq_boost": "+40% AI visibility" if has_faq else "Missing FAQ schema",
        },
        "meta": {
            "has_title": bool(meta.get("title")),
            "has_description": bool(meta.get("description")),
            "has_canonical": bool(meta.get("canonical")),
        },
        "recommendations": _geo_recommendations(method_scores, schema, meta),
    }


def check_ai_visibility(url: str) -> dict:
    """Check how well a URL is prepared for AI search citation."""
    html, status, headers = fetch_html(url)
    if not html:
        return {"status": "error", "url": url, "message": f"Fetch failed ({status})"}

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator=" ", strip=True)

    meta = parse_meta_tags(html)
    schema = parse_schema(html)
    headings = parse_headings(html)

    json_ld_types = [s.get("@type", "") for s in schema.get("json_ld", [])]

    signals: dict = {
        "structured_data": len(schema.get("json_ld", [])) > 0,
        "faq_schema": "FAQPage" in json_ld_types,
        "article_schema": any(t in json_ld_types for t in ["Article", "NewsArticle", "BlogPosting"]),
        "speakable": any("speakable" in str(s).lower() for s in schema.get("json_ld", [])),
        "clear_title": bool(meta.get("title")) and 30 <= len(meta.get("title", "")) <= 60,
        "clear_description": bool(meta.get("description")) and len(meta.get("description", "")) >= 70,
        "heading_structure": len(headings.get("h1", [])) == 1 and len(headings.get("h2", [])) >= 2,
        "canonical": bool(meta.get("canonical")),
        "word_count": len(text.split()),
        "sufficient_content": len(text.split()) >= 300,
    }

    score = sum(1 for v in signals.values() if v is True)
    total = sum(1 for v in signals.values() if isinstance(v, bool))

    return {
        "status": "success",
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ai_visibility_score": round(score / max(total, 1) * 10, 1),
        "signals": signals,
        "recommendations": [
            f"Add FAQ schema (+40% AI visibility)" if not signals["faq_schema"] else None,
            f"Add Article schema" if not signals["article_schema"] else None,
            f"Add Speakable markup" if not signals["speakable"] else None,
            f"Fix title length" if not signals["clear_title"] else None,
            f"Improve meta description" if not signals["clear_description"] else None,
            f"Add more content (currently {signals['word_count']} words, need 300+)"
            if not signals["sufficient_content"] else None,
        ],
    }


def _avg_sentence_length(text: str) -> float:
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    if not sentences:
        return 0
    return sum(len(s.split()) for s in sentences) / len(sentences)


def _geo_recommendations(method_scores: dict, schema: dict, meta: dict) -> list[str]:
    recs: list[str] = []
    for method_key, method_data in method_scores.items():
        if method_key == "keyword_stuffing":
            if method_data.get("detected"):
                recs.append(f"[P0] {method_data['recommendation']}")
            continue
        score = method_data.get("score", 10)
        uplift = PRINCETON_METHODS.get(method_key, {}).get("uplift", 0)
        if score < 5:
            recs.append(f"[P0] {method_data['recommendation']} (potential +{uplift}% visibility)")
        elif score < 7:
            recs.append(f"[P1] {method_data['recommendation']} (potential +{uplift}% visibility)")

    json_ld_types = [s.get("@type", "") for s in schema.get("json_ld", [])]
    if "FAQPage" not in json_ld_types:
        recs.append("[P0] Add FAQPage schema — single biggest AI visibility boost (+40%)")
    if not any(t in json_ld_types for t in ["Article", "NewsArticle", "BlogPosting"]):
        recs.append("[P1] Add Article schema for content pages")

    return [r for r in recs if r]
