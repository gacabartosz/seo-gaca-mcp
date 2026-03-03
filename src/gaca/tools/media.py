"""Media audit tools for images, video, and other asset optimization."""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from gaca.core.collectors import fetch_html
from gaca.core.parsers import parse_schema, parse_meta_tags

logger = logging.getLogger(__name__)

_MODERN_FORMATS = {".webp", ".avif"}
_GENERIC_ALT = {"image", "photo", "img", "picture", "logo", "icon", "banner",
                 "screenshot", "grafika", "zdjecie", "obrazek", "foto"}


def audit_media(url: str) -> dict:
    """Audit images and media assets for alt text, format, sizes, and lazy loading."""
    html, status, headers = fetch_html(url)
    if not html:
        return {
            "status": "error", "url": url,
            "message": f"Failed to fetch page (status: {status})",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    schema = parse_schema(html)
    meta = parse_meta_tags(html)

    issues: list[dict] = []
    recs: list[str] = []

    # --- IMAGE ANALYSIS ---
    img_tags = soup.find_all("img")
    total_images = len(img_tags)
    with_alt = 0
    missing_alt = 0
    empty_alt = 0
    generic_alt = 0
    long_alt = 0
    modern_format = 0
    lazy_loaded = 0
    with_srcset = 0
    with_dimensions = 0
    large_without_srcset = 0

    for img in img_tags:
        src = img.get("src", "") or ""
        alt = img.get("alt")
        loading = img.get("loading", "")
        srcset = img.get("srcset", "")
        width = img.get("width")
        height = img.get("height")

        # Alt text
        if alt is None:
            missing_alt += 1
        elif alt.strip() == "":
            empty_alt += 1
        else:
            with_alt += 1
            alt_lower = alt.strip().lower()
            if alt_lower in _GENERIC_ALT:
                generic_alt += 1
            if len(alt) > 125:
                long_alt += 1

        # Format
        ext = _get_ext(src)
        if ext in _MODERN_FORMATS:
            modern_format += 1

        # Lazy loading
        if loading == "lazy":
            lazy_loaded += 1

        # srcset
        if srcset:
            with_srcset += 1

        # Dimensions
        if width and height:
            with_dimensions += 1
            try:
                w = int(str(width).replace("px", ""))
                if w > 800 and not srcset:
                    large_without_srcset += 1
            except ValueError:
                pass

    # Check for <picture> with <source type="image/webp">
    picture_webp = len(soup.find_all("source", type=re.compile(r"image/(webp|avif)")))
    if picture_webp:
        modern_format += picture_webp

    # --- VIDEO ANALYSIS ---
    video_elements = soup.find_all("video")
    youtube_embeds = soup.find_all("iframe", src=re.compile(r"youtube\.com|youtu\.be"))
    vimeo_embeds = soup.find_all("iframe", src=re.compile(r"vimeo\.com"))
    total_videos = len(video_elements) + len(youtube_embeds) + len(vimeo_embeds)

    video_schema = False
    json_ld_types = [s.get("@type", "") for s in schema.get("json_ld", [])]
    if "VideoObject" in json_ld_types:
        video_schema = True

    og_video = bool(meta.get("og", {}).get("og:video"))

    # --- SCORE ---
    score = 5
    if total_images > 0:
        alt_ratio = with_alt / total_images
        if alt_ratio >= 0.9:
            score += 2
        elif alt_ratio >= 0.7:
            score += 1
        elif alt_ratio < 0.5:
            score -= 2

        modern_ratio = modern_format / total_images
        if modern_ratio >= 0.5:
            score += 1

        if lazy_loaded > 0:
            score += 1

        if with_srcset > 0:
            score += 1

    if total_videos > 0 and video_schema:
        score += 1

    if missing_alt > 3:
        score -= 1

    score = max(1, min(10, score))

    # --- ISSUES ---
    if missing_alt > 0:
        issues.append({"severity": "high", "message": f"{missing_alt} images missing alt attribute"})
        recs.append("Add descriptive alt text to all images")
    if generic_alt > 0:
        issues.append({"severity": "medium", "message": f"{generic_alt} images with generic alt text"})
        recs.append("Replace generic alt text (e.g., 'image', 'photo') with descriptive text")
    if long_alt > 0:
        issues.append({"severity": "low", "message": f"{long_alt} images with alt text >125 chars"})
    if total_images > 0 and modern_format == 0:
        issues.append({"severity": "medium", "message": "No modern image formats (WebP/AVIF) detected"})
        recs.append("Convert images to WebP or AVIF for smaller file sizes")
    if total_images > 5 and lazy_loaded == 0:
        issues.append({"severity": "medium", "message": "No lazy-loaded images detected"})
        recs.append("Add loading='lazy' to below-fold images")
    if large_without_srcset > 0:
        issues.append({"severity": "medium", "message": f"{large_without_srcset} large images without srcset"})
        recs.append("Add srcset/sizes for responsive images")
    if total_images > 0 and with_dimensions < total_images * 0.5:
        issues.append({"severity": "low", "message": "Many images missing width/height (causes CLS)"})
        recs.append("Add explicit width and height attributes to prevent layout shift")
    if total_videos > 0 and not video_schema:
        issues.append({"severity": "medium", "message": "Videos found but no VideoObject schema"})
        recs.append("Add VideoObject JSON-LD schema for video rich results")

    return {
        "status": "success",
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "images": {
                "total": total_images,
                "with_alt": with_alt,
                "missing_alt": missing_alt,
                "empty_alt": empty_alt,
                "generic_alt": generic_alt,
                "long_alt": long_alt,
                "modern_format": modern_format,
                "lazy_loaded": lazy_loaded,
                "with_srcset": with_srcset,
                "with_dimensions": with_dimensions,
                "large_without_srcset": large_without_srcset,
            },
            "videos": {
                "total": total_videos,
                "video_elements": len(video_elements),
                "youtube_embeds": len(youtube_embeds),
                "vimeo_embeds": len(vimeo_embeds),
                "has_video_schema": video_schema,
                "has_og_video": og_video,
            },
        },
        "score": score,
        "issues": issues,
        "recommendations": recs,
    }


def _get_ext(src: str) -> str:
    """Extract file extension from URL."""
    try:
        path = urlparse(src).path.lower()
        if "." in path:
            return "." + path.rsplit(".", 1)[-1].split("?")[0]
    except Exception:
        pass
    return ""
