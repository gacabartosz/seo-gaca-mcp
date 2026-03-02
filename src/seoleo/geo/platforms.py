"""AI platform-specific ranking algorithms and signals."""

PLATFORMS = {
    "chatgpt": {
        "name": "ChatGPT (OpenAI)",
        "bot": "GPTBot",
        "ranking_factors": {
            "domain_authority": {"weight": 0.40, "description": "Established, trusted domains"},
            "content_answer_fit": {"weight": 0.55, "description": "Direct answer match to query"},
            "freshness": {"weight": 0.20, "description": "Content within 30 days = 3.2x citations"},
            "branded_domains": {"weight": 0.11, "description": "Branded domains cited 11% more"},
        },
        "preferred_formats": ["FAQ", "How-to", "Definitions", "Lists"],
        "tips": [
            "Allow GPTBot and ChatGPT-User in robots.txt",
            "Keep content fresh (< 30 days for max citation probability)",
            "Structure with clear H2/H3 for direct answers",
            "Add FAQ schema — dramatically increases citation",
        ],
    },
    "perplexity": {
        "name": "Perplexity AI",
        "bot": "PerplexityBot",
        "ranking_factors": {
            "citation_density": {"weight": 0.45, "description": "Inline references and sources"},
            "rag_reranking": {"weight": 0.30, "description": "3-layer RAG reranking pipeline"},
            "faq_schema": {"weight": 0.20, "description": "FAQ schema prioritized"},
            "pdf_content": {"weight": 0.15, "description": "PDFs get citation boost"},
        },
        "preferred_formats": ["Research papers", "FAQ", "Data-heavy articles"],
        "tips": [
            "Allow PerplexityBot in robots.txt",
            "Maximize inline citations and references",
            "Add FAQ schema for direct answer extraction",
            "Consider publishing PDF versions of key content",
        ],
    },
    "google_sge": {
        "name": "Google SGE / AI Overview",
        "bot": "Google-Extended",
        "ranking_factors": {
            "eeat": {"weight": 0.50, "description": "E-E-A-T (Experience, Expertise, Authority, Trust)"},
            "structured_data": {"weight": 0.35, "description": "Schema.org markup"},
            "topical_authority": {"weight": 0.30, "description": "Topic cluster coverage"},
            "authoritative_citations": {"weight": 0.25, "description": "+132% visibility with citations"},
        },
        "preferred_formats": ["Comprehensive guides", "Expert analysis", "Structured content"],
        "tips": [
            "Allow Google-Extended in robots.txt",
            "Maximize E-E-A-T signals (author info, credentials)",
            "Build topical authority with content clusters",
            "Add authoritative citations for +132% visibility",
        ],
    },
    "claude": {
        "name": "Claude (Anthropic)",
        "bot": "ClaudeBot",
        "ranking_factors": {
            "factual_density": {"weight": 0.45, "description": "High ratio of verifiable facts"},
            "clear_structure": {"weight": 0.35, "description": "Well-organized headings and sections"},
            "brave_search": {"weight": 0.30, "description": "Uses Brave Search (not Google/Bing)"},
            "content_depth": {"weight": 0.25, "description": "Comprehensive coverage of topic"},
        },
        "preferred_formats": ["In-depth analysis", "Technical documentation", "Structured guides"],
        "tips": [
            "Allow ClaudeBot and anthropic-ai in robots.txt",
            "Ensure indexing by Brave Search (submit URL)",
            "Focus on factual density and verifiable claims",
            "Use clear heading hierarchy (H1 > H2 > H3)",
        ],
    },
    "copilot": {
        "name": "Microsoft Copilot",
        "bot": "bingbot",
        "ranking_factors": {
            "bing_index": {"weight": 0.50, "description": "Must be indexed by Bing"},
            "microsoft_ecosystem": {"weight": 0.25, "description": "LinkedIn, GitHub signals"},
            "load_speed": {"weight": 0.20, "description": "< 2s load time required"},
            "structured_answers": {"weight": 0.30, "description": "Clear Q&A format, listicles"},
        },
        "preferred_formats": ["Listicles", "Q&A", "Step-by-step guides"],
        "tips": [
            "Submit site to Bing Webmaster Tools",
            "Leverage Microsoft ecosystem (LinkedIn, GitHub)",
            "Optimize for < 2s page load",
            "Structure content as clear Q&A or step-by-step",
        ],
    },
}


def get_platform_info(platform: str = "all") -> dict:
    """Get ranking algorithm info for AI platforms."""
    if platform == "all":
        return {"platforms": PLATFORMS}
    if platform in PLATFORMS:
        return {"platform": PLATFORMS[platform]}
    return {"error": f"Unknown platform: {platform}. Available: {', '.join(PLATFORMS.keys())}"}
