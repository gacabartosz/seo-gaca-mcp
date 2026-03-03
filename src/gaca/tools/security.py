"""Security audit tools — SSL/TLS certificate analysis and HTTP security headers."""

import logging
import re
import socket
import ssl
from datetime import datetime, timezone
from urllib.parse import urlparse

from gaca.core.collectors import fetch_headers, fetch_html, fetch_ssl_info

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAFE_REFERRER_POLICIES = frozenset({
    "strict-origin-when-cross-origin",
    "no-referrer",
    "no-referrer-when-downgrade",
    "same-origin",
    "strict-origin",
    "origin",
    "origin-when-cross-origin",
})


def _parse_hostname(url: str) -> str:
    """Extract hostname from URL, tolerating missing scheme."""
    if "://" not in url:
        url = f"https://{url}"
    return urlparse(url).hostname or url


def _normalise_url(url: str) -> str:
    """Ensure *url* has an https:// scheme."""
    if "://" not in url:
        return f"https://{url}"
    return url


def _get_cert_via_stdlib(hostname: str, port: int = 443, timeout: float = 10.0) -> dict:
    """Connect with Python's *ssl* module and return the peer certificate dict."""
    ctx = ssl.create_default_context()
    with socket.create_connection((hostname, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
            return ssock.getpeercert() or {}


def _parse_cert_date(date_str: str) -> datetime | None:
    """Parse the notBefore / notAfter format returned by ssl.getpeercert()."""
    # Typical format: 'Sep 11 00:00:00 2023 GMT'
    for fmt in ("%b %d %H:%M:%S %Y %Z", "%b  %d %H:%M:%S %Y %Z"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _extract_san(cert: dict) -> list[str]:
    """Return list of Subject Alternative Names from a cert dict."""
    san_tuples = cert.get("subjectAltName", ())
    return [value for _kind, value in san_tuples]


def _extract_subject_field(cert: dict, field: str = "commonName") -> str | None:
    """Pull a single field from the certificate subject RDN sequence."""
    for rdn in cert.get("subject", ()):
        for key, value in rdn:
            if key == field:
                return value
    return None


def _extract_issuer_cn(cert: dict) -> str | None:
    """Pull commonName from the issuer field."""
    for rdn in cert.get("issuer", ()):
        for key, value in rdn:
            if key == "commonName":
                return value
    return None


def _extract_issuer_org(cert: dict) -> str | None:
    """Pull organizationName from the issuer field."""
    for rdn in cert.get("issuer", ()):
        for key, value in rdn:
            if key == "organizationName":
                return value
    return None


def _check_protocol_support(hostname: str, port: int = 443) -> dict:
    """Check which TLS protocol versions the server accepts.

    Returns a dict with protocol names as keys and bool (supported) as values.
    We only probe TLS 1.0 and TLS 1.1 to confirm they are *disabled*.
    TLS 1.2 and 1.3 are probed to confirm they are *enabled*.
    """
    results: dict[str, bool | None] = {
        "TLS_1_0": None,
        "TLS_1_1": None,
        "TLS_1_2": None,
        "TLS_1_3": None,
    }

    proto_map = {
        "TLS_1_0": ssl.TLSVersion.TLSv1,
        "TLS_1_1": ssl.TLSVersion.TLSv1_1,
        "TLS_1_2": ssl.TLSVersion.TLSv1_2,
        "TLS_1_3": ssl.TLSVersion.TLSv1_3,
    }

    for name, version in proto_map.items():
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.minimum_version = version
            ctx.maximum_version = version
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.load_default_certs()
            with socket.create_connection((hostname, port), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    _ = ssock.version()
                    results[name] = True
        except (ssl.SSLError, OSError, socket.timeout):
            results[name] = False
        except Exception:
            results[name] = None
    return results


def _find_mixed_content(html: str) -> list[str]:
    """Scan HTML for http:// references inside src= and href= attributes."""
    pattern = re.compile(
        r"""(?:src|href)\s*=\s*["']?(http://[^"'\s>]+)""",
        re.IGNORECASE,
    )
    return list(set(pattern.findall(html)))


# ---------------------------------------------------------------------------
# 1. audit_ssl
# ---------------------------------------------------------------------------

def audit_ssl(url: str, check_mixed_content: bool = False) -> dict:
    """Audit SSL/TLS certificate validity, protocol support, HSTS, and
    optionally scan for mixed content.

    Parameters
    ----------
    url : str
        Target URL (scheme optional — defaults to https).
    check_mixed_content : bool
        When *True*, fetch the page HTML and look for ``http://`` references
        in ``src`` / ``href`` attributes.

    Returns
    -------
    dict
        ``{status, url, timestamp, data, score, issues, recommendations}``
    """
    url = _normalise_url(url)
    hostname = _parse_hostname(url)
    issues: list[str] = []
    recommendations: list[str] = []
    score = 10  # start perfect, deduct for problems

    cert_data: dict = {
        "subject": None,
        "issuer": None,
        "issuer_org": None,
        "not_before": None,
        "not_after": None,
        "days_until_expiry": None,
        "san": [],
        "valid": None,
        "error": None,
    }
    protocol_data: dict = {}
    hsts_data: dict = {"present": False, "max_age": None, "include_subdomains": False, "preload": False}
    mixed: list[str] = []

    # ------------------------------------------------------------------
    # Certificate check via stdlib
    # ------------------------------------------------------------------
    try:
        cert = _get_cert_via_stdlib(hostname)
        cert_data["valid"] = True
        cert_data["subject"] = _extract_subject_field(cert, "commonName")
        cert_data["issuer"] = _extract_issuer_cn(cert)
        cert_data["issuer_org"] = _extract_issuer_org(cert)
        cert_data["san"] = _extract_san(cert)

        not_before = cert.get("notBefore")
        not_after = cert.get("notAfter")
        if not_before:
            dt = _parse_cert_date(not_before)
            cert_data["not_before"] = dt.isoformat() if dt else not_before
        if not_after:
            dt = _parse_cert_date(not_after)
            if dt:
                cert_data["not_after"] = dt.isoformat()
                days_left = (dt - datetime.now(timezone.utc)).days
                cert_data["days_until_expiry"] = days_left
                if days_left < 0:
                    issues.append("SSL certificate has EXPIRED.")
                    recommendations.append("Renew the SSL certificate immediately.")
                    score -= 5
                elif days_left < 30:
                    issues.append(f"SSL certificate expires in {days_left} days.")
                    recommendations.append("Renew the SSL certificate soon (< 30 days remaining).")
                    score -= 2
                elif days_left < 90:
                    issues.append(f"SSL certificate expires in {days_left} days — consider renewing.")
                    score -= 1
            else:
                cert_data["not_after"] = not_after

    except ssl.SSLCertVerificationError as exc:
        cert_data["valid"] = False
        cert_data["error"] = str(exc)
        issues.append(f"SSL certificate verification failed: {exc}")
        recommendations.append("Install a valid, trusted SSL certificate (e.g. Let's Encrypt).")
        score -= 5
    except (socket.gaierror, socket.timeout, OSError) as exc:
        cert_data["valid"] = False
        cert_data["error"] = str(exc)
        issues.append(f"Could not connect to {hostname}:443 — {exc}")
        recommendations.append("Ensure the server is reachable on port 443 with a valid certificate.")
        score -= 5

    # Enrich with collector-based info (curl fallback) — non-critical
    try:
        collector_info = fetch_ssl_info(hostname)
        if not cert_data["issuer"] and collector_info.get("issuer"):
            cert_data["issuer"] = collector_info["issuer"]
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Protocol check
    # ------------------------------------------------------------------
    try:
        protocol_data = _check_protocol_support(hostname)
        if protocol_data.get("TLS_1_0"):
            issues.append("TLS 1.0 is still enabled — this is insecure.")
            recommendations.append("Disable TLS 1.0 on the server.")
            score -= 2
        if protocol_data.get("TLS_1_1"):
            issues.append("TLS 1.1 is still enabled — this is deprecated.")
            recommendations.append("Disable TLS 1.1 on the server.")
            score -= 1
        if protocol_data.get("TLS_1_2") is False and protocol_data.get("TLS_1_3") is False:
            issues.append("Neither TLS 1.2 nor TLS 1.3 are supported.")
            recommendations.append("Enable at least TLS 1.2 (preferably TLS 1.3).")
            score -= 3
    except Exception as exc:
        logger.debug("Protocol check failed for %s: %s", hostname, exc)
        protocol_data = {"error": str(exc)}

    # ------------------------------------------------------------------
    # HSTS header check
    # ------------------------------------------------------------------
    try:
        headers, _status = fetch_headers(url)
        hsts_value = None
        for hdr_name, hdr_val in headers.items():
            if hdr_name.lower() == "strict-transport-security":
                hsts_value = hdr_val
                break

        if hsts_value:
            hsts_data["present"] = True
            hsts_data["raw"] = hsts_value
            ma_match = re.search(r"max-age\s*=\s*(\d+)", hsts_value, re.IGNORECASE)
            if ma_match:
                max_age = int(ma_match.group(1))
                hsts_data["max_age"] = max_age
                if max_age < 31536000:
                    issues.append(f"HSTS max-age is {max_age}s (recommended ≥ 31536000).")
                    recommendations.append("Set HSTS max-age to at least 31536000 (1 year).")
                    score -= 1
            hsts_data["include_subdomains"] = "includesubdomains" in hsts_value.lower()
            hsts_data["preload"] = "preload" in hsts_value.lower()
        else:
            hsts_data["present"] = False
            issues.append("Strict-Transport-Security (HSTS) header is missing.")
            recommendations.append(
                "Add HSTS header: Strict-Transport-Security: max-age=31536000; includeSubDomains; preload"
            )
            score -= 2
    except Exception as exc:
        logger.debug("HSTS check failed for %s: %s", url, exc)
        hsts_data["error"] = str(exc)

    # ------------------------------------------------------------------
    # Mixed-content scan (optional)
    # ------------------------------------------------------------------
    if check_mixed_content:
        try:
            html, _status_code, _resp_headers = fetch_html(url)
            if html:
                mixed = _find_mixed_content(html)
                if mixed:
                    issues.append(f"Found {len(mixed)} mixed-content reference(s) (http:// on HTTPS page).")
                    recommendations.append(
                        "Replace all http:// resource URLs with https:// or protocol-relative //."
                    )
                    score -= min(len(mixed), 3)  # cap deduction at 3
        except Exception as exc:
            logger.debug("Mixed-content scan failed for %s: %s", url, exc)

    score = max(1, min(10, score))

    return {
        "status": "success",
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "certificate": cert_data,
            "protocols": protocol_data,
            "hsts": hsts_data,
            "mixed_content": mixed,
        },
        "score": score,
        "issues": issues,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# 2. check_security_headers
# ---------------------------------------------------------------------------

# Definition of the 7 security headers to audit.
# Each entry: (canonical_name, check_fn) where check_fn(value) -> (pass, recommendation)

def _check_hsts(value: str | None) -> tuple[bool, str]:
    if not value:
        return False, "Add Strict-Transport-Security: max-age=31536000; includeSubDomains; preload"
    ma_match = re.search(r"max-age\s*=\s*(\d+)", value, re.IGNORECASE)
    if not ma_match or int(ma_match.group(1)) < 31536000:
        return False, "Set max-age to at least 31536000 (1 year) and add includeSubDomains."
    if "includesubdomains" not in value.lower():
        return False, "Add includeSubDomains directive to HSTS header."
    return True, "HSTS is correctly configured."


def _check_csp(value: str | None) -> tuple[bool, str]:
    if not value:
        return False, "Add a Content-Security-Policy header to control allowed resource origins."
    return True, "Content-Security-Policy is present."


def _check_xfo(value: str | None) -> tuple[bool, str]:
    if not value:
        return False, "Add X-Frame-Options: DENY or SAMEORIGIN to prevent clickjacking."
    val = value.strip().upper()
    if val in ("DENY", "SAMEORIGIN"):
        return True, f"X-Frame-Options is set to {val}."
    return False, "X-Frame-Options should be DENY or SAMEORIGIN."


def _check_xcto(value: str | None) -> tuple[bool, str]:
    if not value:
        return False, "Add X-Content-Type-Options: nosniff to prevent MIME-type sniffing."
    if "nosniff" in value.lower():
        return True, "X-Content-Type-Options: nosniff is set."
    return False, "X-Content-Type-Options should be 'nosniff'."


def _check_referrer(value: str | None) -> tuple[bool, str]:
    if not value:
        return False, "Add Referrer-Policy: strict-origin-when-cross-origin (or stricter)."
    normalised = value.strip().lower()
    # The header may contain a comma-separated fallback list; check the last entry
    policies = [p.strip() for p in normalised.split(",")]
    if any(p in _SAFE_REFERRER_POLICIES for p in policies):
        return True, f"Referrer-Policy is set to {value.strip()}."
    return False, (
        f"Referrer-Policy '{value.strip()}' may leak information. "
        "Use strict-origin-when-cross-origin or no-referrer."
    )


def _check_permissions(value: str | None) -> tuple[bool, str]:
    if not value:
        return False, "Add Permissions-Policy header to restrict browser features (camera, microphone, etc.)."
    return True, "Permissions-Policy is present."


def _check_xxss(value: str | None) -> tuple[bool, str]:
    if not value:
        return False, (
            "Add X-XSS-Protection: 0 (rely on CSP) or 1; mode=block for legacy browser support."
        )
    val = value.strip()
    if val == "0":
        return True, "X-XSS-Protection: 0 — CSP is preferred for XSS mitigation (modern approach)."
    if "1" in val and "mode=block" in val.lower():
        return True, "X-XSS-Protection: 1; mode=block is set."
    return False, "X-XSS-Protection should be 0 (modern) or 1; mode=block (legacy)."


_HEADER_CHECKS: list[tuple[str, callable]] = [
    ("Strict-Transport-Security", _check_hsts),
    ("Content-Security-Policy", _check_csp),
    ("X-Frame-Options", _check_xfo),
    ("X-Content-Type-Options", _check_xcto),
    ("Referrer-Policy", _check_referrer),
    ("Permissions-Policy", _check_permissions),
    ("X-XSS-Protection", _check_xxss),
]


def check_security_headers(url: str) -> dict:
    """Check the presence and correctness of 7 key HTTP security headers.

    Parameters
    ----------
    url : str
        Target URL (scheme optional — defaults to https).

    Returns
    -------
    dict
        ``{status, url, timestamp, data: {headers: {…}}, score, recommendations}``
    """
    url = _normalise_url(url)
    issues: list[str] = []
    recommendations: list[str] = []
    header_results: dict[str, dict] = {}

    try:
        raw_headers, status_code = fetch_headers(url)
    except Exception as exc:
        return {
            "status": "error",
            "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {},
            "score": 1,
            "issues": [f"Failed to fetch headers: {exc}"],
            "recommendations": ["Ensure the URL is reachable and returns valid HTTP headers."],
        }

    if status_code == 0:
        return {
            "status": "error",
            "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {},
            "score": 1,
            "issues": ["Could not connect to the server (status 0)."],
            "recommendations": ["Verify the URL is correct and the server is running."],
        }

    # Build a lowercase-key lookup for case-insensitive matching
    lower_headers: dict[str, str] = {k.lower(): v for k, v in raw_headers.items()}

    passed = 0
    total = len(_HEADER_CHECKS)

    for canonical_name, check_fn in _HEADER_CHECKS:
        value = lower_headers.get(canonical_name.lower())
        is_pass, recommendation = check_fn(value)

        header_results[canonical_name] = {
            "present": value is not None,
            "value": value,
            "pass": is_pass,
            "recommendation": recommendation,
        }

        if is_pass:
            passed += 1
        else:
            if value is None:
                issues.append(f"Missing header: {canonical_name}")
            else:
                issues.append(f"Misconfigured header: {canonical_name} = {value}")
            recommendations.append(recommendation)

    # Score: scale passed/total to 1-10
    # 0/7 → 1, 7/7 → 10
    score = max(1, round(1 + (passed / total) * 9))

    return {
        "status": "success",
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "headers": header_results,
            "http_status": status_code,
        },
        "score": score,
        "issues": issues,
        "recommendations": recommendations,
    }
