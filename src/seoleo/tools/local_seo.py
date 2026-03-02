"""Local SEO audit tools for geo-targeted and local business signals."""

import logging
import re
from datetime import datetime, timezone

from seoleo.core.collectors import fetch_html
from seoleo.core.parsers import parse_schema, parse_meta_tags

logger = logging.getLogger(__name__)

_PHONE_PATTERNS = [
    r'\+?\d{1,3}[\s.-]?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{2,4}',
    r'\(\d{2,3}\)\s?\d{3}[\s-]?\d{2}[\s-]?\d{2}',
]

_SOCIAL_DOMAINS = {
    "facebook.com": "Facebook",
    "linkedin.com": "LinkedIn",
    "instagram.com": "Instagram",
    "twitter.com": "Twitter/X",
    "x.com": "Twitter/X",
    "youtube.com": "YouTube",
    "tiktok.com": "TikTok",
    "pinterest.com": "Pinterest",
}


def audit_local(url: str) -> dict:
    """Audit local SEO signals including NAP, local schema, maps, and contact info."""
    html, status, headers = fetch_html(url)
    if not html:
        return {
            "status": "error", "url": url,
            "message": f"Failed to fetch page (status: {status})",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body")
    text = body.get_text(separator=" ", strip=True) if body else ""

    schema = parse_schema(html)
    meta = parse_meta_tags(html)

    nap: dict = {"name": None, "address": None, "phone": None}
    schema_info: dict = {"has_local_business": False, "types": [], "fields": {}}
    issues: list[dict] = []
    recs: list[str] = []

    # 1. Schema.org LocalBusiness / Organization
    local_types = {"LocalBusiness", "Organization", "Restaurant", "Store", "Hotel",
                   "MedicalBusiness", "FinancialService", "RealEstateAgent",
                   "LegalService", "Dentist", "Physician", "AutoDealer"}

    for item in schema.get("json_ld", []):
        stype = item.get("@type", "")
        if isinstance(stype, list):
            stype = stype[0] if stype else ""

        if stype in local_types:
            schema_info["has_local_business"] = True
            schema_info["types"].append(stype)
            nap["name"] = nap["name"] or item.get("name")
            addr = item.get("address", {})
            if isinstance(addr, dict):
                parts = [addr.get("streetAddress", ""), addr.get("addressLocality", ""),
                         addr.get("postalCode", ""), addr.get("addressCountry", "")]
                nap["address"] = ", ".join(p for p in parts if p) or None
            elif isinstance(addr, str):
                nap["address"] = addr
            nap["phone"] = nap["phone"] or item.get("telephone")
            schema_info["fields"] = {
                "name": bool(item.get("name")),
                "address": bool(item.get("address")),
                "telephone": bool(item.get("telephone")),
                "openingHours": bool(item.get("openingHours") or item.get("openingHoursSpecification")),
                "geo": bool(item.get("geo")),
                "image": bool(item.get("image")),
                "url": bool(item.get("url")),
                "priceRange": bool(item.get("priceRange")),
            }

    # 2. Microdata fallback
    if not nap["name"]:
        el = soup.find(attrs={"itemprop": "name"})
        if el:
            nap["name"] = el.get_text(strip=True)
    if not nap["phone"]:
        el = soup.find(attrs={"itemprop": "telephone"})
        if el:
            nap["phone"] = el.get_text(strip=True)
    if not nap["address"]:
        el = soup.find(attrs={"itemprop": "address"})
        if el:
            nap["address"] = el.get_text(separator=", ", strip=True)

    # 3. Regex phone extraction
    if not nap["phone"]:
        for pattern in _PHONE_PATTERNS:
            m = re.search(pattern, text)
            if m:
                nap["phone"] = m.group(0).strip()
                break

    # 4. Google Maps embed
    maps_embed = False
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")
        if "maps.google" in src or "google.com/maps" in src or "maps/embed" in src:
            maps_embed = True
            break

    # 5. Contact page
    contact_page = False
    contact_keywords = ["contact", "kontakt", "about", "o-nas", "o-firmie"]
    for a in soup.find_all("a", href=True):
        href_lower = a["href"].lower()
        text_lower = a.get_text(strip=True).lower()
        if any(kw in href_lower or kw in text_lower for kw in contact_keywords):
            contact_page = True
            break

    # 6. Social media links
    social_links: dict = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        for domain, name in _SOCIAL_DOMAINS.items():
            if domain in href:
                social_links[name] = href
                break

    # 7. Opening hours in text
    has_hours = bool(re.search(
        r'(?:pon|wt|sr|czw|pt|sob|niedz|mon|tue|wed|thu|fri|sat|sun|godziny|hours|otwarcie)'
        r'.*?\d{1,2}[:.]\d{2}',
        text.lower(),
    ))

    # Score
    score = 1
    if nap["name"]:
        score += 1
    if nap["address"]:
        score += 1
    if nap["phone"]:
        score += 1
    if schema_info["has_local_business"]:
        score += 2
    if maps_embed:
        score += 1
    if contact_page:
        score += 1
    if social_links:
        score += 1
    if has_hours:
        score += 1
    score = min(10, score)

    # Issues & recommendations
    if not schema_info["has_local_business"]:
        issues.append({"severity": "high", "message": "No LocalBusiness schema found"})
        recs.append("Add LocalBusiness JSON-LD schema with full NAP details")
    if not nap["name"]:
        issues.append({"severity": "high", "message": "Business name not found"})
    if not nap["address"]:
        issues.append({"severity": "high", "message": "Business address not found"})
        recs.append("Add structured address (schema or microdata)")
    if not nap["phone"]:
        issues.append({"severity": "medium", "message": "Phone number not found"})
        recs.append("Add phone number in schema and visible on page")
    if not maps_embed:
        issues.append({"severity": "low", "message": "No Google Maps embed"})
        recs.append("Embed Google Maps to improve local relevance")
    if not social_links:
        recs.append("Add social media links (Facebook, LinkedIn, etc.)")
    if not has_hours:
        recs.append("Add opening hours (in schema or visible on page)")

    return {
        "status": "success",
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "nap": nap,
            "schema": schema_info,
            "maps_embed": maps_embed,
            "contact_page": contact_page,
            "social_links": social_links,
            "opening_hours_detected": has_hours,
        },
        "score": score,
        "issues": issues,
        "recommendations": recs,
    }
