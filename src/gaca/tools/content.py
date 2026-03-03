"""Content analysis tools for SEO audits — readability, keyword density, E-E-A-T."""

import logging
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from gaca.core.collectors import fetch_html
from gaca.core.parsers import parse_meta_tags, parse_schema

logger = logging.getLogger(__name__)


# --------------- Helpers ---------------


def _count_syllables(word: str) -> int:
    """Count syllables in a word by counting vowel groups. Minimum 1."""
    word = word.lower().strip()
    if not word:
        return 1
    count = 0
    prev_vowel = False
    vowels = set("aeiouy")
    for ch in word:
        if ch in vowels:
            if not prev_vowel:
                count += 1
            prev_vowel = True
        else:
            prev_vowel = False
    return max(count, 1)


def _extract_body_text(soup: BeautifulSoup) -> str:
    """Extract visible text from the <body>, stripping scripts/styles."""
    body = soup.find("body")
    if not body:
        return ""
    # Remove non-visible elements
    for tag in body.find_all(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    return body.get_text(separator=" ", strip=True)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using punctuation boundaries."""
    # Split on sentence-ending punctuation followed by whitespace or end of string
    raw = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in raw if s.strip()]
    return sentences


def _split_words(text: str) -> list[str]:
    """Extract words (alphabetic sequences) from text."""
    return re.findall(r"[a-zA-Z\u00C0-\u024F\u0100-\u017F]+", text)


def _count_paragraphs(soup: BeautifulSoup) -> int:
    """Count <p> tags with actual text content."""
    body = soup.find("body")
    if not body:
        return 0
    count = 0
    for p in body.find_all("p"):
        if p.get_text(strip=True):
            count += 1
    return count


def _readability_label(fre: float) -> str:
    """Return a human-readable label for the Flesch Reading Ease score."""
    if fre >= 90:
        return "Very Easy"
    elif fre >= 80:
        return "Easy"
    elif fre >= 70:
        return "Fairly Easy"
    elif fre >= 60:
        return "Standard"
    elif fre >= 50:
        return "Fairly Difficult"
    elif fre >= 30:
        return "Difficult"
    else:
        return "Very Difficult"


def _content_score(
    word_count: int,
    sentence_count: int,
    fre: float,
    keyword_density: float,
    keyword: str,
) -> int:
    """Calculate an overall content quality score (1-10)."""
    score = 5.0

    # Word count factor
    if word_count >= 1500:
        score += 1.5
    elif word_count >= 800:
        score += 1.0
    elif word_count >= 300:
        score += 0.5
    elif word_count < 100:
        score -= 2.0
    else:
        score -= 1.0

    # Readability factor (FRE)
    if 50 <= fre <= 80:
        score += 1.5
    elif 30 <= fre < 50 or 80 < fre <= 90:
        score += 0.5
    elif fre < 30 or fre > 90:
        score -= 0.5

    # Keyword density factor (only if keyword was provided)
    if keyword:
        if 1.0 <= keyword_density <= 3.0:
            score += 1.0
        elif 0.5 <= keyword_density < 1.0 or 3.0 < keyword_density <= 5.0:
            score += 0.5
        elif keyword_density > 5.0:
            score -= 1.0
        elif keyword_density == 0:
            score -= 1.5

    # Sentence count factor
    if sentence_count >= 10:
        score += 0.5
    elif sentence_count < 3:
        score -= 1.0

    return max(1, min(10, round(score)))


def _content_recommendations(
    word_count: int,
    sentence_count: int,
    avg_sentence_length: float,
    fre: float,
    fk: float,
    keyword_density: float,
    keyword: str,
    paragraph_count: int,
) -> list[str]:
    """Generate actionable content recommendations."""
    recs: list[str] = []

    if word_count < 300:
        recs.append(
            f"Content is thin ({word_count} words). "
            "Aim for at least 800-1500 words for competitive SEO content."
        )
    elif word_count < 800:
        recs.append(
            f"Content length ({word_count} words) is below average. "
            "Consider expanding to 1000+ words for better topical coverage."
        )

    if avg_sentence_length > 25:
        recs.append(
            f"Average sentence length is high ({avg_sentence_length:.1f} words). "
            "Break long sentences into shorter ones for better readability."
        )

    if fre < 30:
        recs.append(
            f"Flesch Reading Ease is very low ({fre:.1f}). "
            "Simplify vocabulary and shorten sentences for wider audience reach."
        )
    elif fre < 50:
        recs.append(
            f"Flesch Reading Ease is below average ({fre:.1f}). "
            "Consider simplifying language for better engagement."
        )

    if fk > 14:
        recs.append(
            f"Flesch-Kincaid Grade Level is high ({fk:.1f}). "
            "Content requires college-level reading. Target grade 8-10 for general audiences."
        )

    if keyword:
        if keyword_density == 0:
            recs.append(
                f"Keyword '{keyword}' was not found in the content. "
                "Include it naturally in headings, first paragraph, and body text."
            )
        elif keyword_density < 0.5:
            recs.append(
                f"Keyword density for '{keyword}' is very low ({keyword_density:.2f}%). "
                "Increase usage to 1-2% for optimal SEO."
            )
        elif keyword_density > 5.0:
            recs.append(
                f"Keyword density for '{keyword}' is too high ({keyword_density:.2f}%). "
                "Reduce to 1-3% to avoid keyword stuffing penalties."
            )

    if paragraph_count < 3 and word_count > 200:
        recs.append(
            "Content has very few paragraphs. "
            "Break text into shorter paragraphs (3-4 sentences each) for better scannability."
        )

    if sentence_count < 3 and word_count > 50:
        recs.append(
            "Very few sentences detected. Check if the page relies heavily on "
            "non-text elements (images, videos) without supporting text."
        )

    if not recs:
        recs.append("Content quality metrics look good. Continue maintaining readability standards.")

    return recs


# --------------- Main Functions ---------------


def analyze_content(url: str, keyword: str = "", language: str = "auto") -> dict:
    """Analyze on-page content quality, keyword usage, and readability.

    Args:
        url: The page URL to analyze.
        keyword: Optional target keyword for density analysis.
        language: Language hint (currently informational; readability formulas are English-based).

    Returns:
        Dict with status, url, timestamp, data (readability metrics, keyword density,
        word/sentence/paragraph counts), score (1-10), and recommendations.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    html, status_code, headers = fetch_html(url)
    if not html:
        return {
            "status": "error",
            "url": url,
            "message": f"Failed to fetch page (HTTP {status_code})",
            "timestamp": timestamp,
        }

    soup = BeautifulSoup(html, "lxml")

    # Extract text content
    text = _extract_body_text(soup)
    words = _split_words(text)
    word_count = len(words)

    if word_count == 0:
        return {
            "status": "error",
            "url": url,
            "message": "No text content found on the page",
            "timestamp": timestamp,
        }

    sentences = _split_sentences(text)
    sentence_count = max(len(sentences), 1)
    paragraph_count = _count_paragraphs(BeautifulSoup(html, "lxml"))

    # Calculate syllables
    total_syllables = sum(_count_syllables(w) for w in words)
    complex_words = sum(1 for w in words if _count_syllables(w) >= 3)

    # Averages
    avg_sentence_length = word_count / sentence_count
    avg_word_length = (
        sum(len(w) for w in words) / word_count if word_count else 0
    )

    # Readability scores
    fk_grade = (
        0.39 * (word_count / sentence_count)
        + 11.8 * (total_syllables / word_count)
        - 15.59
    )
    gunning_fog = 0.4 * (
        (word_count / sentence_count) + 100 * (complex_words / word_count)
    )
    fre = (
        206.835
        - 1.015 * (word_count / sentence_count)
        - 84.6 * (total_syllables / word_count)
    )

    # Keyword density
    keyword_density = 0.0
    keyword_count = 0
    if keyword:
        keyword_lower = keyword.lower()
        text_lower = text.lower()
        # Count non-overlapping occurrences of the keyword phrase
        keyword_count = text_lower.count(keyword_lower)
        keyword_density = (keyword_count / word_count) * 100 if word_count else 0.0

    # Score and recommendations
    score = _content_score(word_count, sentence_count, fre, keyword_density, keyword)
    recommendations = _content_recommendations(
        word_count, sentence_count, avg_sentence_length,
        fre, fk_grade, keyword_density, keyword, paragraph_count,
    )

    data: dict = {
        "readability": {
            "flesch_kincaid_grade": round(fk_grade, 2),
            "gunning_fog_index": round(gunning_fog, 2),
            "flesch_reading_ease": round(fre, 2),
            "reading_ease_label": _readability_label(fre),
        },
        "word_count": word_count,
        "sentence_count": sentence_count,
        "paragraph_count": paragraph_count,
        "avg_sentence_length": round(avg_sentence_length, 2),
        "avg_word_length": round(avg_word_length, 2),
        "syllable_count": total_syllables,
        "complex_word_count": complex_words,
        "complex_word_ratio": round(complex_words / word_count * 100, 2),
    }

    if keyword:
        data["keyword_density"] = {
            "keyword": keyword,
            "count": keyword_count,
            "density_percent": round(keyword_density, 2),
        }

    return {
        "status": "success",
        "url": url,
        "timestamp": timestamp,
        "data": data,
        "score": score,
        "recommendations": recommendations,
    }


def check_eeat(url: str) -> dict:
    """Check E-E-A-T signals (Experience, Expertise, Authoritativeness, Trustworthiness).

    Analyzes the page for trust signals that search engines use to evaluate
    content quality and credibility.

    Args:
        url: The page URL to analyze.

    Returns:
        Dict with status, url, timestamp, data (detected signals per category),
        score (1-10), and recommendations.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    html, status_code, headers = fetch_html(url)
    if not html:
        return {
            "status": "error",
            "url": url,
            "message": f"Failed to fetch page (HTTP {status_code})",
            "timestamp": timestamp,
        }

    soup = BeautifulSoup(html, "lxml")
    signals: dict = {
        "author": [],
        "dates": [],
        "about_contact": [],
        "citations": [],
        "expertise": [],
        "trust": [],
    }
    signal_count = 0

    # --- Author signals ---
    # rel="author"
    author_links = soup.find_all("a", rel="author")
    for link in author_links:
        signals["author"].append({
            "type": "rel_author",
            "text": link.get_text(strip=True),
            "href": link.get("href", ""),
        })

    # itemprop="author"
    author_itemprop = soup.find_all(attrs={"itemprop": "author"})
    for elem in author_itemprop:
        signals["author"].append({
            "type": "itemprop_author",
            "text": elem.get_text(strip=True),
        })

    # .author class
    author_class = soup.find_all(class_=re.compile(r"\bauthor\b", re.I))
    for elem in author_class:
        text = elem.get_text(strip=True)
        if text and len(text) < 200:
            signals["author"].append({
                "type": "class_author",
                "text": text[:100],
            })

    # "by " pattern in specific contexts (byline)
    byline_patterns = soup.find_all(
        class_=re.compile(r"byline|by-line|post-author|entry-author|article-author", re.I)
    )
    for elem in byline_patterns:
        text = elem.get_text(strip=True)
        if text:
            signals["author"].append({
                "type": "byline_class",
                "text": text[:100],
            })

    # Schema.org author in JSON-LD
    schema_data = parse_schema(html)
    for schema in schema_data.get("json_ld", []):
        if isinstance(schema, dict):
            author = schema.get("author")
            if author:
                if isinstance(author, dict):
                    signals["author"].append({
                        "type": "schema_author",
                        "name": author.get("name", ""),
                        "url": author.get("url", ""),
                    })
                elif isinstance(author, list):
                    for a in author:
                        if isinstance(a, dict):
                            signals["author"].append({
                                "type": "schema_author",
                                "name": a.get("name", ""),
                                "url": a.get("url", ""),
                            })
                elif isinstance(author, str):
                    signals["author"].append({
                        "type": "schema_author",
                        "name": author,
                    })

    signal_count += min(len(signals["author"]), 3)  # Cap contribution

    # --- Date signals ---
    # <time> elements
    time_tags = soup.find_all("time")
    for tag in time_tags:
        signals["dates"].append({
            "type": "time_element",
            "datetime": tag.get("datetime", ""),
            "text": tag.get_text(strip=True),
        })

    # datePublished / dateModified in schema
    for schema in schema_data.get("json_ld", []):
        if isinstance(schema, dict):
            for date_key in ("datePublished", "dateModified", "dateCreated"):
                val = schema.get(date_key)
                if val:
                    signals["dates"].append({
                        "type": f"schema_{date_key}",
                        "value": str(val),
                    })

    # itemprop datePublished/dateModified
    for prop in ("datePublished", "dateModified"):
        elems = soup.find_all(attrs={"itemprop": prop})
        for elem in elems:
            signals["dates"].append({
                "type": f"itemprop_{prop}",
                "value": elem.get("content", elem.get("datetime", elem.get_text(strip=True))),
            })

    signal_count += min(len(signals["dates"]), 2)

    # --- About/Contact links ---
    all_links = soup.find_all("a", href=True)
    about_contact_keywords = ["about", "contact", "team", "o-nas", "kontakt", "our-team"]
    seen_hrefs: set = set()
    for link in all_links:
        href = link.get("href", "").lower()
        text = link.get_text(strip=True).lower()
        for kw in about_contact_keywords:
            if kw in href or kw in text:
                if href not in seen_hrefs:
                    seen_hrefs.add(href)
                    signals["about_contact"].append({
                        "type": "link",
                        "text": link.get_text(strip=True),
                        "href": link.get("href", ""),
                    })
                break

    signal_count += min(len(signals["about_contact"]), 2)

    # --- Citation signals ---
    # <cite> elements
    cite_tags = soup.find_all("cite")
    for tag in cite_tags:
        text = tag.get_text(strip=True)
        if text:
            signals["citations"].append({
                "type": "cite_element",
                "text": text[:150],
            })

    # <blockquote> elements
    blockquotes = soup.find_all("blockquote")
    for bq in blockquotes:
        cite_attr = bq.get("cite", "")
        text = bq.get_text(strip=True)[:150]
        signals["citations"].append({
            "type": "blockquote",
            "cite": cite_attr,
            "text": text,
        })

    # Reference patterns (links with ref/source/citation classes or text)
    ref_links = soup.find_all(
        "a",
        class_=re.compile(r"ref|cite|source|footnote|bibliography", re.I),
    )
    for link in ref_links:
        signals["citations"].append({
            "type": "reference_link",
            "text": link.get_text(strip=True)[:100],
            "href": link.get("href", ""),
        })

    # Numbered reference patterns like [1], [2] etc.
    sup_refs = soup.find_all("sup")
    ref_count = 0
    for sup in sup_refs:
        inner = sup.find("a")
        if inner and re.match(r"^\[?\d+\]?$", inner.get_text(strip=True)):
            ref_count += 1
    if ref_count > 0:
        signals["citations"].append({
            "type": "numbered_references",
            "count": ref_count,
        })

    signal_count += min(len(signals["citations"]), 2)

    # --- Expertise signals ---
    body = soup.find("body")
    body_text = body.get_text(separator=" ", strip=True).lower() if body else ""

    expertise_keywords = [
        "certified", "certification", "credential", "licensed",
        "accredited", "degree", "phd", "ph.d", "md", "m.d",
        "years of experience", "years experience",
        "expert", "specialist", "professional",
        "published in", "peer-reviewed", "research",
        "award", "recognized", "qualified",
        # Polish equivalents
        "certyfikat", "certyfikowany", "licencja", "licencjonowany",
        "akredytacja", "dyplom", "doktorat", "magister",
        "lat doswiadczenia", "ekspert", "specjalista",
    ]
    found_expertise: set = set()
    for kw in expertise_keywords:
        if kw in body_text:
            found_expertise.add(kw)

    for kw in found_expertise:
        signals["expertise"].append({
            "type": "keyword_mention",
            "keyword": kw,
        })

    # Author bio sections
    bio_sections = soup.find_all(
        class_=re.compile(r"bio|about.?author|author.?info|author.?bio|author.?desc", re.I)
    )
    for section in bio_sections:
        signals["expertise"].append({
            "type": "author_bio_section",
            "text": section.get_text(strip=True)[:200],
        })

    signal_count += min(len(signals["expertise"]), 2)

    # --- Trust signals ---
    # HTTPS
    if url.startswith("https://"):
        signals["trust"].append({"type": "https", "value": True})
        signal_count += 1

    # Privacy policy / Terms links
    trust_keywords = [
        "privacy", "policy", "terms", "conditions", "disclaimer",
        "polityka-prywatnosci", "regulamin", "warunki",
    ]
    seen_trust_hrefs: set = set()
    for link in all_links:
        href = link.get("href", "").lower()
        text = link.get_text(strip=True).lower()
        for kw in trust_keywords:
            if kw in href or kw in text:
                if href not in seen_trust_hrefs:
                    seen_trust_hrefs.add(href)
                    signals["trust"].append({
                        "type": "trust_link",
                        "text": link.get_text(strip=True),
                        "href": link.get("href", ""),
                    })
                break

    signal_count += min(len(signals["trust"]), 2)

    # --- Score calculation ---
    # Max practical signal_count is around 14 (3+2+2+2+2+1+2)
    # Map to 1-10 scale
    if signal_count >= 12:
        score = 10
    elif signal_count >= 10:
        score = 9
    elif signal_count >= 8:
        score = 8
    elif signal_count >= 6:
        score = 7
    elif signal_count >= 5:
        score = 6
    elif signal_count >= 4:
        score = 5
    elif signal_count >= 3:
        score = 4
    elif signal_count >= 2:
        score = 3
    elif signal_count >= 1:
        score = 2
    else:
        score = 1

    # --- Recommendations ---
    recommendations = _eeat_recommendations(signals)

    # Build summary counts for readability
    summary = {
        category: len(items) for category, items in signals.items()
    }
    summary["total_signals"] = signal_count

    return {
        "status": "success",
        "url": url,
        "timestamp": timestamp,
        "data": {
            "signals": signals,
            "summary": summary,
        },
        "score": score,
        "recommendations": recommendations,
    }


def _eeat_recommendations(signals: dict) -> list[str]:
    """Generate E-E-A-T improvement recommendations based on detected signals."""
    recs: list[str] = []

    if not signals["author"]:
        recs.append(
            "No author attribution found. Add visible author name with "
            'rel="author" link, structured data (schema.org Person), or a byline.'
        )

    if not signals["dates"]:
        recs.append(
            "No publish or update dates found. Add <time> elements or "
            "datePublished/dateModified in JSON-LD schema for freshness signals."
        )

    if not signals["about_contact"]:
        recs.append(
            "No About or Contact page links detected. Add visible links to "
            "About Us, Team, and Contact pages to establish transparency."
        )

    if not signals["citations"]:
        recs.append(
            "No citations or references found. Add <cite>, <blockquote>, or "
            "inline references to authoritative sources to boost credibility."
        )

    if not signals["expertise"]:
        recs.append(
            "No expertise signals (credentials, certifications, experience mentions) found. "
            "Add author bio with qualifications, years of experience, or relevant credentials."
        )

    trust_types = {s.get("type") for s in signals["trust"]}
    if "https" not in trust_types:
        recs.append(
            "Page is not served over HTTPS. Migrate to HTTPS for security and trust signals."
        )

    if "trust_link" not in trust_types:
        recs.append(
            "No Privacy Policy or Terms of Service links found. "
            "Add footer links to legal pages for user trust."
        )

    if not recs:
        recs.append(
            "Good E-E-A-T signals detected. Continue maintaining author attribution, "
            "date freshness, citations, and trust indicators."
        )

    return recs
