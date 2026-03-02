"""HTML parsers — meta tags, headings, images, links, schema, scripts, UX elements."""

import json
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

TIMEOUT = 15
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


# --------------- SEO Parsers ---------------


def parse_meta_tags(html: str) -> dict:
    """Extract all SEO-relevant meta tags from HTML."""
    soup = BeautifulSoup(html, "lxml")
    meta: dict = {
        "title": None, "description": None, "canonical": None,
        "charset": None, "viewport": None, "robots": None,
        "generator": None, "og": {}, "twitter": {}, "other": [],
    }

    title_tag = soup.find("title")
    if title_tag:
        meta["title"] = title_tag.get_text(strip=False).strip()
        meta["title_length"] = len(meta["title"])

    canonical = soup.find("link", rel="canonical")
    if canonical:
        meta["canonical"] = canonical.get("href", "").strip()

    for tag in soup.find_all("meta"):
        name = (tag.get("name") or "").lower()
        prop = (tag.get("property") or "").lower()
        content = tag.get("content", "").strip()
        charset = tag.get("charset")
        http_equiv = (tag.get("http-equiv") or "").lower()

        if charset:
            meta["charset"] = charset
        elif name == "description":
            meta["description"] = content
            meta["description_length"] = len(content)
        elif name == "viewport":
            meta["viewport"] = content
        elif name == "robots":
            meta["robots"] = content
        elif name == "generator":
            meta["generator"] = content
        elif prop.startswith("og:"):
            meta["og"][prop] = content
        elif name.startswith("twitter:") or prop.startswith("twitter:"):
            key = name or prop
            meta["twitter"][key] = content
        elif http_equiv == "content-type" and "charset" in content.lower():
            charset_match = re.search(r"charset=([^\s;]+)", content, re.I)
            if charset_match:
                meta["charset"] = charset_match.group(1)
        elif name or prop:
            meta["other"].append({"name": name or prop, "content": content})

    # Alternate hreflang
    hreflangs = []
    for link in soup.find_all("link", rel="alternate"):
        hl = link.get("hreflang")
        if hl:
            hreflangs.append({"lang": hl, "href": link.get("href", "")})
    if hreflangs:
        meta["hreflang"] = hreflangs

    # Favicon
    favicon = None
    for link in soup.find_all("link"):
        rels = link.get("rel", [])
        if isinstance(rels, list):
            rels = [r.lower() for r in rels]
        else:
            rels = [rels.lower()]
        if "icon" in rels or "shortcut" in rels:
            favicon = link.get("href", "")
            break
    meta["favicon"] = favicon

    return meta


def parse_headings(html: str) -> dict:
    """Extract all heading tags (H1-H6) with their text content."""
    soup = BeautifulSoup(html, "lxml")
    headings: dict = {f"h{i}": [] for i in range(1, 7)}
    for i in range(1, 7):
        for tag in soup.find_all(f"h{i}"):
            text = tag.get_text(strip=True)
            if text:
                headings[f"h{i}"].append(text)
    return headings


def parse_images(html: str, base_url: str | None = None) -> dict:
    """Extract image info: count, missing alt, formats, sizes."""
    soup = BeautifulSoup(html, "lxml")
    images = []
    without_alt = 0
    formats: dict = {}

    for img in soup.find_all("img"):
        src = img.get("src", "")
        alt = img.get("alt")
        loading = img.get("loading")
        width = img.get("width")
        height = img.get("height")

        if base_url and src and not src.startswith(("http://", "https://", "data:")):
            src = urljoin(base_url, src)

        ext = ""
        if src and "." in src.split("?")[0]:
            ext = src.split("?")[0].rsplit(".", 1)[-1].lower()

        if ext:
            formats[ext] = formats.get(ext, 0) + 1

        if alt is None or alt.strip() == "":
            without_alt += 1

        images.append({
            "src": src, "alt": alt, "loading": loading,
            "width": width, "height": height, "format": ext,
        })

    return {
        "count": len(images), "without_alt": without_alt,
        "formats": formats, "images": images,
    }


def parse_links(html: str, base_url: str) -> dict:
    """Extract internal and external links."""
    soup = BeautifulSoup(html, "lxml")
    base_domain = urlparse(base_url).netloc
    internal: list[dict] = []
    external: list[dict] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(strip=True)
        rel = a.get("rel", [])
        if isinstance(rel, list):
            rel = " ".join(rel)
        target = a.get("target", "")

        if href and not href.startswith(
            ("http://", "https://", "mailto:", "tel:", "javascript:", "#")
        ):
            href = urljoin(base_url, href)

        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue

        parsed = urlparse(href)
        link_info = {"href": href, "text": text, "rel": rel, "target": target}

        if parsed.netloc == base_domain or parsed.netloc == "":
            internal.append(link_info)
        else:
            external.append(link_info)

    return {"internal": internal, "external": external}


def parse_schema(html: str) -> dict:
    """Extract JSON-LD structured data from HTML."""
    soup = BeautifulSoup(html, "lxml")
    schemas: list = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                schemas.extend(data)
            else:
                schemas.append(data)
        except (json.JSONDecodeError, TypeError):
            continue

    microdata: list = []
    for elem in soup.find_all(itemscope=True):
        itemtype = elem.get("itemtype", "")
        if itemtype:
            microdata.append({"type": "microdata", "itemtype": itemtype})

    return {"json_ld": schemas, "microdata": microdata}


def parse_html_tag(html: str) -> dict:
    """Extract attributes from the <html> tag."""
    soup = BeautifulSoup(html, "lxml")
    html_tag = soup.find("html")
    if not html_tag:
        return {"lang": None, "dir": None}
    return {
        "lang": html_tag.get("lang"),
        "dir": html_tag.get("dir"),
        "itemscope": html_tag.get("itemscope") is not None,
        "itemtype": html_tag.get("itemtype"),
        "class": html_tag.get("class"),
        "prefix": html_tag.get("prefix"),
    }


def parse_scripts(html: str) -> dict:
    """Analyze script tags and preloaded resources."""
    soup = BeautifulSoup(html, "lxml")
    head = soup.find("head")
    body = soup.find("body")

    in_head: list = []
    in_body: list = []

    if head:
        for script in head.find_all("script"):
            src = script.get("src", "")
            stype = script.get("type", "")
            in_head.append({
                "src": src, "type": stype,
                "async": script.get("async") is not None,
                "defer": script.get("defer") is not None,
            })

    if body:
        for script in body.find_all("script"):
            src = script.get("src", "")
            stype = script.get("type", "")
            in_body.append({
                "src": src, "type": stype,
                "async": script.get("async") is not None,
                "defer": script.get("defer") is not None,
            })

    preloads: list = []
    for link in soup.find_all("link", rel="preload"):
        preloads.append({
            "href": link.get("href", ""),
            "as": link.get("as", ""),
            "type": link.get("type", ""),
        })

    stylesheets = [link.get("href", "") for link in soup.find_all("link", rel="stylesheet")]

    return {
        "in_head": in_head, "in_body": in_body,
        "preloads": preloads, "stylesheets": stylesheets,
        "total_scripts": len(in_head) + len(in_body),
        "total_stylesheets": len(stylesheets),
    }


# --------------- UX Parsers ---------------


def parse_ux_elements(html: str, base_url: str | None = None) -> dict:
    """Extract UX-relevant elements from static HTML."""
    soup = BeautifulSoup(html, "lxml")
    return {
        "navigation": _parse_navigation(soup),
        "search": _parse_search(soup),
        "semantic_structure": _parse_semantic_structure(soup),
        "interactive_elements": _parse_interactive_elements(soup),
        "badges": _parse_badges(soup),
        "overlays": _parse_overlays(soup),
        "responsive_meta": _parse_responsive_indicators(soup),
        "css_links": _extract_css_links(soup, base_url),
    }


def _parse_navigation(soup: BeautifulSoup) -> dict:
    navs = soup.find_all("nav")
    nav_info = []
    for nav in navs:
        nav_info.append({
            "aria_label": nav.get("aria-label", ""),
            "role": nav.get("role", ""),
            "id": nav.get("id", ""),
            "classes": " ".join(nav.get("class", [])),
            "links_count": len(nav.find_all("a")),
        })

    hamburger_buttons: list = []
    selectors = [
        lambda s: s.find_all("button", class_=re.compile(r"menu|hamburger|toggle|mobile", re.I)),
        lambda s: s.find_all("button", attrs={"aria-label": re.compile(r"menu|nawigac", re.I)}),
        lambda s: s.find_all(attrs={"data-toggle": "collapse"}),
        lambda s: s.find_all("div", class_=re.compile(r"hamburger|menu-icon", re.I)),
    ]
    seen_ids: set = set()
    for selector_fn in selectors:
        for btn in selector_fn(soup):
            btn_id = id(btn)
            if btn_id in seen_ids:
                continue
            seen_ids.add(btn_id)
            hamburger_buttons.append({
                "tag": btn.name,
                "classes": " ".join(btn.get("class", [])),
                "aria_label": btn.get("aria-label", ""),
                "aria_expanded": btn.get("aria-expanded"),
                "aria_controls": btn.get("aria-controls"),
            })

    return {
        "nav_elements": nav_info, "nav_count": len(navs),
        "hamburger_buttons": hamburger_buttons,
        "has_mobile_menu_trigger": len(hamburger_buttons) > 0,
    }


def _parse_search(soup: BeautifulSoup) -> dict:
    search_inputs: list = []
    for inp in soup.find_all("input"):
        input_type = (inp.get("type") or "").lower()
        name = (inp.get("name") or "").lower()
        placeholder = (inp.get("placeholder") or "").lower()
        aria_label = (inp.get("aria-label") or "").lower()
        classes = " ".join(inp.get("class", [])).lower()

        is_search = (
            input_type == "search"
            or "search" in name or "szukaj" in name or "query" in name
            or "search" in placeholder or "szukaj" in placeholder
            or "search" in aria_label or "szukaj" in aria_label
            or "search" in classes
        )
        if is_search:
            search_inputs.append({
                "type": input_type, "name": inp.get("name", ""),
                "placeholder": inp.get("placeholder", ""),
                "aria_label": inp.get("aria-label", ""),
                "in_nav": inp.find_parent("nav") is not None,
                "in_header": inp.find_parent("header") is not None,
            })

    search_forms: list = []
    for form in soup.find_all("form"):
        action = (form.get("action") or "").lower()
        role = (form.get("role") or "").lower()
        classes = " ".join(form.get("class", [])).lower()
        if "search" in action or role == "search" or "search" in classes:
            search_forms.append({
                "action": form.get("action", ""), "role": role,
                "in_nav": form.find_parent("nav") is not None,
                "in_header": form.find_parent("header") is not None,
            })

    search_buttons = soup.find_all(
        lambda tag: tag.name in ("button", "a", "div", "span") and (
            any(kw in " ".join(tag.get("class", [])).lower() for kw in ["search", "szukaj"])
            or (tag.get("aria-label") or "").lower() in ("search", "szukaj", "wyszukaj")
        )
    )

    return {
        "search_inputs": search_inputs, "search_forms": search_forms,
        "has_search_in_nav": any(
            s.get("in_nav") or s.get("in_header") for s in search_inputs + search_forms
        ),
        "has_search": len(search_inputs) > 0 or len(search_forms) > 0 or len(search_buttons) > 0,
    }


def _parse_semantic_structure(soup: BeautifulSoup) -> dict:
    return {
        "has_main": soup.find("main") is not None,
        "has_header": soup.find("header") is not None,
        "has_footer": soup.find("footer") is not None,
        "sections": len(soup.find_all("section")),
        "articles": len(soup.find_all("article")),
        "asides": len(soup.find_all("aside")),
        "navs": len(soup.find_all("nav")),
        "has_skip_link": _has_skip_link(soup),
        "landmark_roles": _count_landmark_roles(soup),
    }


def _has_skip_link(soup: BeautifulSoup) -> bool:
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        text = a.get_text(strip=True).lower()
        if href.startswith("#") and ("skip" in text or "content" in text or "tresc" in text):
            return True
    return False


def _count_landmark_roles(soup: BeautifulSoup) -> dict:
    roles = [
        "banner", "navigation", "main", "complementary",
        "contentinfo", "search", "form", "region",
    ]
    counts: dict = {}
    for role in roles:
        elements = soup.find_all(attrs={"role": role})
        if elements:
            counts[role] = len(elements)
    return counts


def _parse_interactive_elements(soup: BeautifulSoup) -> dict:
    buttons = soup.find_all("button")
    links = soup.find_all("a", href=True)
    inputs = soup.find_all(["input", "select", "textarea"])

    small_explicit: list = []
    for elem in buttons + links:
        style = elem.get("style", "")
        if style:
            w_match = re.search(r"width:\s*(\d+)px", style)
            h_match = re.search(r"height:\s*(\d+)px", style)
            if w_match and int(w_match.group(1)) < 44:
                small_explicit.append({"tag": elem.name, "style_width": w_match.group(1) + "px"})
            if h_match and int(h_match.group(1)) < 44:
                small_explicit.append({"tag": elem.name, "style_height": h_match.group(1) + "px"})

    return {
        "buttons_count": len(buttons), "links_count": len(links),
        "form_inputs_count": len(inputs),
        "total_interactive": len(buttons) + len(links) + len(inputs),
        "small_explicit_sizing": small_explicit,
    }


def _parse_badges(soup: BeautifulSoup) -> dict:
    badge_patterns = re.compile(r"badge|label|tag|chip|promo|sticker|ribbon", re.I)
    badge_elements = soup.find_all(class_=badge_patterns)
    results: list = []
    for badge in badge_elements[:20]:
        parent = badge.parent
        results.append({
            "tag": badge.name,
            "classes": " ".join(badge.get("class", [])),
            "text": badge.get_text(strip=True)[:50],
            "parent_tag": parent.name if parent else None,
            "parent_classes": " ".join(parent.get("class", [])) if parent else "",
        })
    return {"count": len(badge_elements), "badges": results}


def _parse_overlays(soup: BeautifulSoup) -> dict:
    overlay_patterns = re.compile(
        r"modal|overlay|drawer|bottom.?sheet|sidebar|offcanvas|popup|dialog", re.I
    )
    overlays = soup.find_all(class_=overlay_patterns)
    dialogs = soup.find_all(attrs={"role": "dialog"})
    dialog_elements = soup.find_all("dialog")

    results: list = []
    seen: set = set()
    for elem in overlays + dialogs + dialog_elements:
        elem_id = id(elem)
        if elem_id in seen:
            continue
        seen.add(elem_id)
        style = elem.get("style", "")
        close_btn = elem.find("button", class_=re.compile(r"close|dismiss|zamknij", re.I))
        results.append({
            "tag": elem.name,
            "classes": " ".join(elem.get("class", [])),
            "id": elem.get("id", ""),
            "role": elem.get("role", ""),
            "aria_modal": elem.get("aria-modal"),
            "inline_style": style[:200] if style else "",
            "has_close_button": close_btn is not None,
        })
    return {"count": len(results), "overlays": results}


def _parse_responsive_indicators(soup: BeautifulSoup) -> dict:
    responsive_stylesheets: list = []
    for link in soup.find_all("link", rel="stylesheet"):
        media = link.get("media", "")
        if media and media != "all":
            responsive_stylesheets.append({"href": link.get("href", ""), "media": media})

    picture_count = len(soup.find_all("picture"))
    srcset_count = len(soup.find_all(attrs={"srcset": True}))

    return {
        "responsive_stylesheets": responsive_stylesheets,
        "picture_elements": picture_count,
        "srcset_elements": srcset_count,
        "uses_responsive_images": picture_count > 0 or srcset_count > 0,
    }


def _extract_css_links(soup: BeautifulSoup, base_url: str | None) -> list[str]:
    css_links: list[str] = []
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href", "")
        if href and base_url:
            href = urljoin(base_url, href)
        css_links.append(href)
    return css_links


def fetch_and_parse_css_media_queries(css_urls: list[str]) -> dict:
    """Fetch external CSS files and extract @media query breakpoints."""
    breakpoints: set = set()
    tablet_found = False

    for url in css_urls[:5]:
        try:
            r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": DEFAULT_UA})
            if r.status_code != 200:
                continue
            media_rules = re.findall(
                r"@media\s*[^{]*\b(min|max)-width\s*:\s*(\d+)(?:px|em|rem)", r.text
            )
            for direction, value in media_rules:
                val = int(value)
                breakpoints.add(val)
                if 720 <= val <= 1024:
                    tablet_found = True
        except Exception:
            continue

    return {
        "breakpoints": sorted(breakpoints),
        "has_tablet_breakpoint": tablet_found,
        "breakpoint_count": len(breakpoints),
    }
