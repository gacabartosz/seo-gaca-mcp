"""Accessibility audit tools — WCAG 2.2 Level AA checks."""

import logging
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from gaca.core.collectors import fetch_html
from gaca.core.parsers import parse_headings

logger = logging.getLogger(__name__)

# Valid BCP 47 primary language subtags (ISO 639-1 subset).
_VALID_LANG_CODES = {
    "aa", "ab", "af", "ak", "am", "an", "ar", "as", "av", "ay", "az",
    "ba", "be", "bg", "bh", "bi", "bm", "bn", "bo", "br", "bs",
    "ca", "ce", "ch", "co", "cr", "cs", "cu", "cv", "cy",
    "da", "de", "dv", "dz",
    "ee", "el", "en", "eo", "es", "et", "eu",
    "fa", "ff", "fi", "fj", "fo", "fr", "fy",
    "ga", "gd", "gl", "gn", "gu", "gv",
    "ha", "he", "hi", "ho", "hr", "ht", "hu", "hy", "hz",
    "ia", "id", "ie", "ig", "ii", "ik", "io", "is", "it", "iu",
    "ja", "jv",
    "ka", "kg", "ki", "kj", "kk", "kl", "km", "kn", "ko", "kr", "ks", "ku", "kv", "kw", "ky",
    "la", "lb", "lg", "li", "ln", "lo", "lt", "lu", "lv",
    "mg", "mh", "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my",
    "na", "nb", "nd", "ne", "ng", "nl", "nn", "no", "nr", "nv", "ny",
    "oc", "oj", "om", "or", "os",
    "pa", "pi", "pl", "ps", "pt",
    "qu",
    "rm", "rn", "ro", "ru", "rw",
    "sa", "sc", "sd", "se", "sg", "si", "sk", "sl", "sm", "sn", "so", "sq", "sr", "ss", "st",
    "su", "sv", "sw",
    "ta", "te", "tg", "th", "ti", "tk", "tl", "tn", "to", "tr", "ts", "tt", "tw", "ty",
    "ug", "uk", "ur", "uz",
    "ve", "vi", "vo",
    "wa", "wo",
    "xh",
    "yi", "yo",
    "za", "zh", "zu",
}

# Generic link texts that signal poor accessibility (case-insensitive).
_GENERIC_LINK_TEXTS = {
    "click here", "here", "read more", "more", "link",
    "learn more", "this", "go", "details",
}

# Focusable element tags for aria-hidden check.
_FOCUSABLE_TAGS = {"a", "button", "input", "select", "textarea"}

# Form input types that do NOT need labels.
_LABEL_EXEMPT_TYPES = {"hidden", "submit", "button", "reset", "image"}


def audit_accessibility(url: str) -> dict:
    """Audit a page for WCAG 2.2 Level AA accessibility issues.

    Checks 10 WCAG criteria covering images, forms, headings, landmarks,
    skip navigation, link text, language, color contrast hints, ARIA
    attributes, and keyboard accessibility.

    Args:
        url: The URL to audit.

    Returns:
        Dict with status, url, timestamp, data (checks, total_issues,
        by_severity), score, issues, and recommendations.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    html, status_code, _headers = fetch_html(url)
    if not html:
        return {
            "status": "error",
            "url": url,
            "timestamp": timestamp,
            "message": f"Failed to fetch page (status: {status_code})",
        }

    soup = BeautifulSoup(html, "lxml")
    issues: list[dict] = []
    checks: dict[str, dict] = {}

    # --- 1. Images (WCAG 1.1.1) ---
    checks["1.1.1_images"] = _check_images(soup, issues)

    # --- 2. Form labels (WCAG 1.3.1 + 4.1.2) ---
    checks["1.3.1_form_labels"] = _check_form_labels(soup, issues)

    # --- 3. Heading hierarchy (WCAG 1.3.1) ---
    checks["1.3.1_headings"] = _check_heading_hierarchy(html, issues)

    # --- 4. Landmarks (WCAG 1.3.1) ---
    checks["1.3.1_landmarks"] = _check_landmarks(soup, issues)

    # --- 5. Skip navigation (WCAG 2.4.1) ---
    checks["2.4.1_skip_navigation"] = _check_skip_navigation(soup, issues)

    # --- 6. Link text (WCAG 2.4.4) ---
    checks["2.4.4_link_text"] = _check_link_text(soup, issues)

    # --- 7. Language (WCAG 3.1.1) ---
    checks["3.1.1_language"] = _check_language(soup, issues)

    # --- 8. Color contrast hint (WCAG 1.4.3) ---
    checks["1.4.3_color_contrast"] = _check_color_contrast_hints(soup, issues)

    # --- 9. ARIA attributes (WCAG 4.1.2) ---
    checks["4.1.2_aria"] = _check_aria_attributes(soup, issues)

    # --- 10. Keyboard (WCAG 2.1.1) ---
    checks["2.1.1_keyboard"] = _check_keyboard(soup, issues)

    # Tally severities.
    by_severity: dict[str, int] = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
    for issue in issues:
        sev = issue.get("severity", "minor")
        by_severity[sev] = by_severity.get(sev, 0) + 1

    total_issues = len(issues)
    score = _calculate_score(checks, by_severity, total_issues)
    recommendations = _generate_recommendations(checks, by_severity)

    return {
        "status": "success",
        "url": url,
        "timestamp": timestamp,
        "data": {
            "checks": checks,
            "total_issues": total_issues,
            "by_severity": by_severity,
        },
        "score": score,
        "issues": issues,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Individual WCAG checks
# ---------------------------------------------------------------------------

def _check_images(soup: BeautifulSoup, issues: list[dict]) -> dict:
    """WCAG 1.1.1 — Non-text Content: all <img> must have alt."""
    images = soup.find_all("img")
    total = len(images)
    missing_alt: list[str] = []
    empty_alt_non_decorative: list[str] = []

    for img in images:
        src = img.get("src", "")[:120]
        alt = img.get("alt")

        if alt is None:
            missing_alt.append(src)
            issues.append({
                "severity": "critical",
                "wcag": "1.1.1",
                "message": f"Image missing alt attribute: {src}",
            })
        elif alt.strip() == "":
            # Empty alt is valid for decorative images. Heuristic: if the image
            # is inside <a>, <button>, or <figure> with <figcaption>, or has
            # role="presentation"/"none", treat as potentially decorative.
            role = (img.get("role") or "").lower()
            parent = img.parent
            is_decorative = (
                role in ("presentation", "none")
                or (parent and parent.name in ("a", "button"))
            )
            if not is_decorative:
                empty_alt_non_decorative.append(src)
                issues.append({
                    "severity": "critical",
                    "wcag": "1.1.1",
                    "message": f"Image has empty alt but appears non-decorative: {src}",
                })

    passed = total > 0 and not missing_alt and not empty_alt_non_decorative
    return {
        "status": "pass" if passed else ("fail" if missing_alt or empty_alt_non_decorative else "pass"),
        "details": {
            "total_images": total,
            "missing_alt_count": len(missing_alt),
            "missing_alt": missing_alt[:20],
            "empty_alt_non_decorative_count": len(empty_alt_non_decorative),
            "empty_alt_non_decorative": empty_alt_non_decorative[:20],
        },
    }


def _check_form_labels(soup: BeautifulSoup, issues: list[dict]) -> dict:
    """WCAG 1.3.1 + 4.1.2 — Form controls must have accessible labels."""
    form_elements = soup.find_all(["input", "select", "textarea"])
    total = 0
    unlabeled: list[dict] = []

    # Build a set of all element IDs in the document.
    all_ids = {el.get("id") for el in soup.find_all(id=True)}

    # Build a map: id -> True for IDs that have a <label for="id">.
    label_for_map: set[str] = set()
    for label in soup.find_all("label"):
        for_attr = label.get("for")
        if for_attr:
            label_for_map.add(for_attr)

    for el in form_elements:
        if el.name == "input":
            input_type = (el.get("type") or "text").lower()
            if input_type in _LABEL_EXEMPT_TYPES:
                continue

        total += 1
        el_id = el.get("id", "")
        has_label_for = el_id and el_id in label_for_map
        has_aria_label = bool(el.get("aria-label", "").strip())
        has_aria_labelledby = bool(el.get("aria-labelledby", "").strip())
        has_title = bool(el.get("title", "").strip())
        # Check if wrapped inside a <label>.
        has_wrapping_label = el.find_parent("label") is not None

        if not any([has_label_for, has_aria_label, has_aria_labelledby, has_title, has_wrapping_label]):
            tag_desc = el.name
            if el.name == "input":
                tag_desc += f'[type={el.get("type", "text")}]'
            name_attr = el.get("name", "")
            unlabeled.append({"tag": tag_desc, "name": name_attr, "id": el_id})
            issues.append({
                "severity": "critical",
                "wcag": "1.3.1",
                "message": f"Form control without accessible label: <{tag_desc}> name='{name_attr}'",
            })

    passed = total > 0 and not unlabeled
    status = "pass" if passed else ("fail" if unlabeled else "pass")
    if total == 0:
        status = "not_applicable"

    return {
        "status": status,
        "details": {
            "total_form_controls": total,
            "unlabeled_count": len(unlabeled),
            "unlabeled": unlabeled[:20],
        },
    }


def _check_heading_hierarchy(html: str, issues: list[dict]) -> dict:
    """WCAG 1.3.1 — Headings: exactly one h1, no skipped levels."""
    headings = parse_headings(html)
    h1_count = len(headings.get("h1", []))
    hierarchy_issues: list[str] = []

    # Check h1 count.
    if h1_count == 0:
        issues.append({
            "severity": "serious",
            "wcag": "1.3.1",
            "message": "Page has no <h1> element",
        })
        hierarchy_issues.append("No h1 found")
    elif h1_count > 1:
        issues.append({
            "severity": "serious",
            "wcag": "1.3.1",
            "message": f"Page has {h1_count} <h1> elements (should be exactly 1)",
        })
        hierarchy_issues.append(f"Multiple h1 ({h1_count})")

    # Check for skipped levels. Build the ordered list of used heading levels.
    used_levels: list[int] = []
    for level in range(1, 7):
        if headings.get(f"h{level}"):
            used_levels.append(level)

    for i in range(1, len(used_levels)):
        if used_levels[i] - used_levels[i - 1] > 1:
            skipped_from = used_levels[i - 1]
            skipped_to = used_levels[i]
            msg = f"Heading level skipped: h{skipped_from} -> h{skipped_to}"
            hierarchy_issues.append(msg)
            issues.append({
                "severity": "serious",
                "wcag": "1.3.1",
                "message": msg,
            })

    passed = h1_count == 1 and not hierarchy_issues
    return {
        "status": "pass" if passed else "fail",
        "details": {
            "h1_count": h1_count,
            "headings_summary": {k: len(v) for k, v in headings.items()},
            "hierarchy_issues": hierarchy_issues,
        },
    }


def _check_landmarks(soup: BeautifulSoup, issues: list[dict]) -> dict:
    """WCAG 1.3.1 — Landmarks: check for main, nav, header, footer."""
    landmarks_found: dict[str, bool] = {}

    # Semantic elements.
    for tag_name in ("main", "nav", "header", "footer"):
        landmarks_found[tag_name] = soup.find(tag_name) is not None

    # ARIA role equivalents.
    role_map = {
        "main": "main",
        "navigation": "nav",
        "banner": "header",
        "contentinfo": "footer",
    }
    for role, tag_name in role_map.items():
        if not landmarks_found.get(tag_name):
            if soup.find(attrs={"role": role}):
                landmarks_found[tag_name] = True

    missing = [name for name, found in landmarks_found.items() if not found]
    if missing:
        issues.append({
            "severity": "serious",
            "wcag": "1.3.1",
            "message": f"Missing landmark elements: {', '.join(missing)}",
        })

    passed = not missing
    return {
        "status": "pass" if passed else "fail",
        "details": {
            "landmarks": landmarks_found,
            "missing": missing,
        },
    }


def _check_skip_navigation(soup: BeautifulSoup, issues: list[dict]) -> dict:
    """WCAG 2.4.1 — Skip link: first link in body should be a skip link."""
    body = soup.find("body")
    has_skip_link = False
    skip_link_info: dict | None = None

    if body:
        # Look for skip links anywhere near the top (within first few elements).
        all_links = body.find_all("a", href=True)
        for link in all_links[:5]:
            href = link.get("href", "")
            text = link.get_text(strip=True).lower()
            if href.startswith("#") and len(href) > 1:
                skip_keywords = ("skip", "content", "main", "tresc", "nawigac")
                if any(kw in text for kw in skip_keywords):
                    has_skip_link = True
                    skip_link_info = {"href": href, "text": link.get_text(strip=True)}
                    break

        # Also check for role="navigation" with skip mechanism.
        if not has_skip_link:
            nav_role = body.find(attrs={"role": "navigation"})
            if nav_role:
                skip_inside = nav_role.find("a", href=re.compile(r"^#"))
                if skip_inside:
                    text = skip_inside.get_text(strip=True).lower()
                    if any(kw in text for kw in ("skip", "content", "main")):
                        has_skip_link = True
                        skip_link_info = {"href": skip_inside.get("href", ""), "text": skip_inside.get_text(strip=True)}

    if not has_skip_link:
        issues.append({
            "severity": "moderate",
            "wcag": "2.4.1",
            "message": "No skip navigation link found",
        })

    return {
        "status": "pass" if has_skip_link else "fail",
        "details": {
            "has_skip_link": has_skip_link,
            "skip_link": skip_link_info,
        },
    }


def _check_link_text(soup: BeautifulSoup, issues: list[dict]) -> dict:
    """WCAG 2.4.4 — Link Purpose: flag generic link text."""
    links = soup.find_all("a", href=True)
    total = len(links)
    generic_links: list[dict] = []

    for link in links:
        text = link.get_text(strip=True).lower()
        if text in _GENERIC_LINK_TEXTS:
            href = link.get("href", "")[:120]
            generic_links.append({"text": link.get_text(strip=True), "href": href})
            issues.append({
                "severity": "moderate",
                "wcag": "2.4.4",
                "message": f"Generic link text '{link.get_text(strip=True)}' — href: {href}",
            })

    passed = not generic_links
    return {
        "status": "pass" if passed else "fail",
        "details": {
            "total_links": total,
            "generic_link_count": len(generic_links),
            "generic_links": generic_links[:20],
        },
    }


def _check_language(soup: BeautifulSoup, issues: list[dict]) -> dict:
    """WCAG 3.1.1 — Language of Page: <html> must have valid lang attribute."""
    html_tag = soup.find("html")
    lang_attr = html_tag.get("lang", "").strip() if html_tag else ""

    has_lang = bool(lang_attr)
    is_valid = False

    if has_lang:
        # Extract primary language subtag (before hyphen, e.g., "en" from "en-US").
        primary = lang_attr.split("-")[0].lower()
        is_valid = primary in _VALID_LANG_CODES

    if not has_lang:
        issues.append({
            "severity": "serious",
            "wcag": "3.1.1",
            "message": "Missing lang attribute on <html> element",
        })
    elif not is_valid:
        issues.append({
            "severity": "serious",
            "wcag": "3.1.1",
            "message": f"Invalid lang attribute value: '{lang_attr}'",
        })

    passed = has_lang and is_valid
    return {
        "status": "pass" if passed else "fail",
        "details": {
            "lang": lang_attr or None,
            "is_valid": is_valid,
        },
    }


def _parse_color_value(color_str: str) -> tuple[int, int, int] | None:
    """Parse a CSS color string and return (r, g, b) or None.

    Supports: #RGB, #RRGGBB, rgb(r,g,b), rgba(r,g,b,a), and named
    near-white colors.
    """
    color_str = color_str.strip().lower()

    # Hex: #RGB or #RRGGBB
    hex_match = re.match(r"^#([0-9a-f]{3,8})$", color_str)
    if hex_match:
        h = hex_match.group(1)
        if len(h) == 3:
            r, g, b = int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16)
            return (r, g, b)
        elif len(h) >= 6:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return (r, g, b)

    # rgb(r, g, b) or rgba(r, g, b, a)
    rgb_match = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", color_str)
    if rgb_match:
        return (int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3)))

    return None


def _is_very_light_color(r: int, g: int, b: int) -> bool:
    """Return True if all RGB channels are > 200 (near-white)."""
    return r > 200 and g > 200 and b > 200


def _check_color_contrast_hints(soup: BeautifulSoup, issues: list[dict]) -> dict:
    """WCAG 1.4.3 — Contrast (Minimum): flag inline styles with very light text colors.

    Cannot fully compute contrast without rendering, but flags obvious
    violations: text with inline color where r, g, b are all > 200.
    """
    flagged: list[dict] = []

    # Check all elements with inline style containing "color:".
    elements_with_style = soup.find_all(style=re.compile(r"(?:^|;)\s*color\s*:", re.I))
    for el in elements_with_style:
        style = el.get("style", "")
        # Extract the color value (not background-color).
        # Use a regex that matches "color:" but not "background-color:".
        color_match = re.search(r"(?:^|;)\s*(?<!background-)color\s*:\s*([^;]+)", style, re.I)
        if not color_match:
            continue

        color_val = color_match.group(1).strip()
        rgb = _parse_color_value(color_val)
        if rgb and _is_very_light_color(*rgb):
            tag_text = el.get_text(strip=True)[:60]
            flagged.append({
                "tag": el.name,
                "color": color_val,
                "rgb": list(rgb),
                "text_preview": tag_text,
            })
            issues.append({
                "severity": "moderate",
                "wcag": "1.4.3",
                "message": f"Very light text color ({color_val}) may have insufficient contrast: '{tag_text}'",
            })

    return {
        "status": "pass" if not flagged else "fail",
        "details": {
            "flagged_count": len(flagged),
            "flagged_elements": flagged[:20],
            "note": "Heuristic only — full contrast check requires rendering engine",
        },
    }


def _check_aria_attributes(soup: BeautifulSoup, issues: list[dict]) -> dict:
    """WCAG 4.1.2 — ARIA: validate labelledby refs, aria-hidden on focusable."""
    all_ids = {el.get("id") for el in soup.find_all(id=True) if el.get("id")}
    aria_issues: list[dict] = []

    # Check aria-labelledby references existing IDs.
    for el in soup.find_all(attrs={"aria-labelledby": True}):
        ref_ids = el.get("aria-labelledby", "").split()
        for ref_id in ref_ids:
            if ref_id and ref_id not in all_ids:
                aria_issues.append({
                    "type": "broken_labelledby",
                    "element": el.name,
                    "reference_id": ref_id,
                })
                issues.append({
                    "severity": "minor",
                    "wcag": "4.1.2",
                    "message": f"aria-labelledby references non-existent ID '{ref_id}' on <{el.name}>",
                })

    # Check aria-hidden="true" on focusable elements.
    for el in soup.find_all(attrs={"aria-hidden": "true"}):
        tag = el.name
        is_focusable = (
            tag in _FOCUSABLE_TAGS
            or el.get("tabindex") is not None
            or el.get("contenteditable") == "true"
        )
        # Also check if it contains focusable children.
        has_focusable_children = False
        if not is_focusable:
            for child_tag in _FOCUSABLE_TAGS:
                if el.find(child_tag):
                    has_focusable_children = True
                    break
            if not has_focusable_children and el.find(attrs={"tabindex": True}):
                has_focusable_children = True

        if is_focusable:
            aria_issues.append({
                "type": "hidden_focusable",
                "element": tag,
                "id": el.get("id", ""),
            })
            issues.append({
                "severity": "minor",
                "wcag": "4.1.2",
                "message": f"aria-hidden='true' on focusable element <{tag}>",
            })
        elif has_focusable_children:
            aria_issues.append({
                "type": "hidden_contains_focusable",
                "element": tag,
                "id": el.get("id", ""),
            })
            issues.append({
                "severity": "minor",
                "wcag": "4.1.2",
                "message": f"aria-hidden='true' on <{tag}> that contains focusable children",
            })

    return {
        "status": "pass" if not aria_issues else "fail",
        "details": {
            "aria_issue_count": len(aria_issues),
            "aria_issues": aria_issues[:20],
        },
    }


def _check_keyboard(soup: BeautifulSoup, issues: list[dict]) -> dict:
    """WCAG 2.1.1 — Keyboard: flag positive tabindex and mouse-only events."""
    keyboard_issues: list[dict] = []

    # Flag tabindex > 0 (disrupts natural tab order).
    for el in soup.find_all(attrs={"tabindex": True}):
        try:
            tabindex_val = int(el.get("tabindex", "0"))
        except (ValueError, TypeError):
            continue
        if tabindex_val > 0:
            keyboard_issues.append({
                "type": "positive_tabindex",
                "element": el.name,
                "tabindex": tabindex_val,
                "id": el.get("id", ""),
            })
            issues.append({
                "severity": "minor",
                "wcag": "2.1.1",
                "message": f"Positive tabindex={tabindex_val} on <{el.name}> disrupts tab order",
            })

    # Flag onmouseover/onclick without keyboard equivalents.
    mouse_events = {
        "onmouseover": ("onfocus",),
        "onmouseout": ("onblur",),
        "onclick": ("onkeydown", "onkeyup", "onkeypress"),
    }
    for mouse_attr, keyboard_attrs in mouse_events.items():
        for el in soup.find_all(attrs={mouse_attr: True}):
            has_keyboard = any(el.get(ka) for ka in keyboard_attrs)
            if not has_keyboard:
                tag = el.name
                keyboard_issues.append({
                    "type": "mouse_only_event",
                    "element": tag,
                    "mouse_event": mouse_attr,
                    "missing_keyboard": list(keyboard_attrs),
                    "id": el.get("id", ""),
                })
                issues.append({
                    "severity": "minor",
                    "wcag": "2.1.1",
                    "message": (
                        f"<{tag}> has {mouse_attr} without keyboard equivalent "
                        f"({'/'.join(keyboard_attrs)})"
                    ),
                })

    return {
        "status": "pass" if not keyboard_issues else "fail",
        "details": {
            "keyboard_issue_count": len(keyboard_issues),
            "keyboard_issues": keyboard_issues[:20],
        },
    }


# ---------------------------------------------------------------------------
# Scoring & recommendations
# ---------------------------------------------------------------------------

def _calculate_score(
    checks: dict[str, dict],
    by_severity: dict[str, int],
    total_issues: int,
) -> int:
    """Calculate an accessibility score from 1-10.

    Starts at 10, deducts points based on severity and number of failures.
    """
    score = 10.0

    # Deduct per severity.
    score -= by_severity.get("critical", 0) * 1.5
    score -= by_severity.get("serious", 0) * 1.0
    score -= by_severity.get("moderate", 0) * 0.5
    score -= by_severity.get("minor", 0) * 0.25

    # Bonus deduction for many total issues.
    if total_issues > 20:
        score -= 1.0
    elif total_issues > 10:
        score -= 0.5

    # Count failed checks.
    failed_checks = sum(1 for c in checks.values() if c.get("status") == "fail")
    passed_checks = sum(1 for c in checks.values() if c.get("status") == "pass")
    total_checks = failed_checks + passed_checks

    # Additional deduction for proportion of failed checks.
    if total_checks > 0:
        fail_ratio = failed_checks / total_checks
        score -= fail_ratio * 2.0

    # Clamp to 1-10.
    return max(1, min(10, round(score)))


def _generate_recommendations(
    checks: dict[str, dict],
    by_severity: dict[str, int],
) -> list[str]:
    """Generate actionable recommendations based on failed checks."""
    recs: list[str] = []

    check_rec_map = {
        "1.1.1_images": (
            "Add descriptive alt text to all images. Use alt=\"\" only for truly decorative images."
        ),
        "1.3.1_form_labels": (
            "Associate every form control with a <label> (using for/id), "
            "aria-label, or aria-labelledby attribute."
        ),
        "1.3.1_headings": (
            "Ensure exactly one <h1> per page and maintain proper heading hierarchy "
            "(no skipping levels, e.g., h1 -> h3)."
        ),
        "1.3.1_landmarks": (
            "Add semantic landmarks: <main>, <nav>, <header>, <footer>. "
            "These help screen reader users navigate the page."
        ),
        "2.4.1_skip_navigation": (
            "Add a 'Skip to main content' link as the first focusable element in <body>."
        ),
        "2.4.4_link_text": (
            "Replace generic link text ('click here', 'read more') with descriptive text "
            "that makes sense out of context."
        ),
        "3.1.1_language": (
            "Add a valid lang attribute to the <html> element (e.g., lang=\"en\" or lang=\"pl\")."
        ),
        "1.4.3_color_contrast": (
            "Ensure text has sufficient contrast against its background. "
            "WCAG AA requires 4.5:1 for normal text, 3:1 for large text."
        ),
        "4.1.2_aria": (
            "Fix broken aria-labelledby references and remove aria-hidden from focusable elements."
        ),
        "2.1.1_keyboard": (
            "Ensure all interactive elements are keyboard accessible. "
            "Avoid positive tabindex values and provide keyboard event handlers alongside mouse events."
        ),
    }

    for check_name, rec_text in check_rec_map.items():
        if checks.get(check_name, {}).get("status") == "fail":
            recs.append(rec_text)

    if not recs:
        recs.append(
            "No major accessibility issues detected. Consider a full WCAG 2.2 audit "
            "with assistive technology testing for complete coverage."
        )

    return recs
