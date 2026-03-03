"""Data collectors — fetches HTML, headers, robots, sitemap, SSL, hosting info."""

import logging
import re
import socket
import subprocess
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests

logger = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
TIMEOUT = 15


def fetch_html(url: str, ua: str = DEFAULT_UA) -> tuple[str | None, int, dict]:
    """Fetch page HTML with a browser-like User-Agent."""
    try:
        r = requests.get(url, headers={"User-Agent": ua}, timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        return r.text, r.status_code, dict(r.headers)
    except requests.RequestException as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None, getattr(e.response, "status_code", 0) if e.response else 0, {}


def fetch_headers(url: str, ua: str | None = None) -> tuple[dict, int]:
    """Fetch HTTP response headers (HEAD request)."""
    headers = {"User-Agent": ua} if ua else {}
    try:
        r = requests.head(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        return dict(r.headers), r.status_code
    except requests.RequestException:
        return {}, 0


def fetch_robots(base_url: str) -> str | None:
    """Fetch robots.txt content."""
    url = urljoin(base_url, "/robots.txt")
    try:
        r = requests.get(url, headers={"User-Agent": DEFAULT_UA}, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.text
        return None
    except requests.RequestException:
        return None


def fetch_sitemap(url: str) -> list[dict]:
    """Fetch and parse sitemap XML, returning list of {loc, lastmod, priority}."""
    try:
        r = requests.get(url, headers={"User-Agent": DEFAULT_UA}, timeout=TIMEOUT)
        if r.status_code != 200:
            return []
        root = ElementTree.fromstring(r.content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        # Check if it's a sitemap index
        sitemaps = root.findall("sm:sitemap", ns)
        if sitemaps:
            all_urls: list[dict] = []
            for sm in sitemaps:
                loc = sm.find("sm:loc", ns)
                if loc is not None and loc.text:
                    all_urls.extend(fetch_sitemap(loc.text.strip()))
            return all_urls

        # Regular sitemap
        urls: list[dict] = []
        for url_elem in root.findall("sm:url", ns):
            entry: dict = {}
            loc = url_elem.find("sm:loc", ns)
            if loc is not None and loc.text:
                entry["loc"] = loc.text.strip()
            lastmod = url_elem.find("sm:lastmod", ns)
            if lastmod is not None and lastmod.text:
                entry["lastmod"] = lastmod.text.strip()
            priority = url_elem.find("sm:priority", ns)
            if priority is not None and priority.text:
                entry["priority"] = priority.text.strip()
            changefreq = url_elem.find("sm:changefreq", ns)
            if changefreq is not None and changefreq.text:
                entry["changefreq"] = changefreq.text.strip()
            if entry.get("loc"):
                urls.append(entry)
        return urls
    except Exception:
        return []


def check_resource(url: str) -> int:
    """Check if a URL is accessible, return status code."""
    try:
        r = requests.head(
            url, headers={"User-Agent": DEFAULT_UA}, timeout=TIMEOUT, allow_redirects=True
        )
        return r.status_code
    except requests.RequestException:
        return 0


def get_hosting_info(domain: str) -> dict:
    """Get IP address and reverse DNS for a domain."""
    info: dict = {"domain": domain, "ip": None, "reverse_dns": None}
    try:
        ip = socket.gethostbyname(domain)
        info["ip"] = ip
        try:
            reverse = socket.gethostbyaddr(ip)
            info["reverse_dns"] = reverse[0]
        except socket.herror:
            pass
    except socket.gaierror:
        pass
    return info


def fetch_page_without_ua(url: str) -> int:
    """Fetch a page with no User-Agent to test for 403 blocks."""
    try:
        r = requests.get(url, headers={"User-Agent": ""}, timeout=TIMEOUT, allow_redirects=True)
        return r.status_code
    except requests.RequestException:
        return 0


def discover_sitemap_urls(base_url: str, robots_txt: str | None = None) -> list[str]:
    """Discover sitemap URL(s) from robots.txt or common paths."""
    sitemap_urls: list[str] = []

    if robots_txt:
        for line in robots_txt.splitlines():
            line = line.strip()
            if line.lower().startswith("sitemap:"):
                sitemap_url = line.split(":", 1)[1].strip()
                if sitemap_url:
                    sitemap_urls.append(sitemap_url)

    if not sitemap_urls:
        common = ["/sitemap.xml", "/sitemap_index.xml", "/sitemap/sitemap.xml"]
        for path in common:
            url = urljoin(base_url, path)
            status = check_resource(url)
            if status == 200:
                sitemap_urls.append(url)
                break

    return sitemap_urls


def fetch_ssl_info(domain: str) -> dict:
    """Get basic SSL certificate info via curl."""
    try:
        result = subprocess.run(
            ["curl", "-vI", f"https://{domain}", "--connect-timeout", "5"],
            capture_output=True, text=True, timeout=10,
        )
        stderr = result.stderr
        info: dict = {"valid": False, "issuer": None, "expire_date": None}
        if "SSL certificate verify ok" in stderr:
            info["valid"] = True
        for line in stderr.splitlines():
            line_s = line.strip()
            if "issuer:" in line_s.lower():
                info["issuer"] = line_s.split(":", 1)[1].strip() if ":" in line_s else line_s
            if "expire date:" in line_s.lower():
                info["expire_date"] = (
                    line_s.split(":", 1)[1].strip() if ":" in line_s else line_s
                )
        return info
    except Exception:
        return {"valid": False, "issuer": None, "expire_date": None}
