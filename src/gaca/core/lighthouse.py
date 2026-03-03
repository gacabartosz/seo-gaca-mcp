"""Lighthouse CLI wrapper — runs mobile & desktop audits and parses results."""

import json
import logging
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)


def is_lighthouse_available() -> bool:
    """Check if npx lighthouse is available."""
    try:
        result = subprocess.run(
            ["npx", "lighthouse", "--version"],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def run_lighthouse(url: str, form_factor: str, output_path: str) -> bool:
    """Run Lighthouse CLI for given form factor. Returns True on success."""
    cmd = [
        "npx", "lighthouse", url,
        f"--form-factor={form_factor}",
        "--output=json",
        f"--output-path={output_path}",
        "--chrome-flags=--headless --no-sandbox --disable-gpu",
        "--quiet",
    ]
    if form_factor == "desktop":
        cmd.extend([
            "--screenEmulation.mobile=false",
            "--screenEmulation.width=1350",
            "--screenEmulation.height=940",
        ])

    logger.info("Running Lighthouse (%s)...", form_factor)
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
        return False
    except subprocess.TimeoutExpired:
        logger.warning("Lighthouse (%s) timed out", form_factor)
        return False
    except FileNotFoundError:
        logger.warning("Lighthouse CLI not found")
        return False


def parse_lighthouse_scores(json_path: str) -> dict:
    """Extract category scores (0-100) from Lighthouse JSON."""
    try:
        with open(json_path) as f:
            data = json.load(f)
        categories = data.get("categories", {})
        scores: dict = {}
        for key, cat in categories.items():
            score = cat.get("score")
            if score is not None:
                scores[key] = round(score * 100)
        return scores
    except Exception as e:
        return {"error": str(e)}


def parse_cwv(json_path: str) -> dict:
    """Extract Core Web Vitals metrics from Lighthouse JSON."""
    metrics_map = {
        "first-contentful-paint": "fcp",
        "largest-contentful-paint": "lcp",
        "total-blocking-time": "tbt",
        "cumulative-layout-shift": "cls",
        "speed-index": "si",
        "interactive": "tti",
        "experimental-interaction-to-next-paint": "inp",
        "server-response-time": "ttfb",
    }
    try:
        with open(json_path) as f:
            data = json.load(f)
        audits = data.get("audits", {})
        cwv: dict = {}
        for audit_id, short_name in metrics_map.items():
            audit = audits.get(audit_id, {})
            value = audit.get("numericValue")
            display = audit.get("displayValue", "")
            score = audit.get("score")
            if value is not None:
                cwv[short_name] = {
                    "value": round(value, 2),
                    "display": display,
                    "score": score,
                }
        return cwv
    except Exception as e:
        return {"error": str(e)}


def parse_lighthouse_issues(json_path: str) -> list[dict]:
    """Extract audit failures and opportunities from Lighthouse."""
    try:
        with open(json_path) as f:
            data = json.load(f)
        audits = data.get("audits", {})
        issues: list = []
        for audit_id, audit in audits.items():
            score = audit.get("score")
            if score is not None and score < 1:
                details = audit.get("details", {})
                savings_ms = None
                savings_bytes = None
                if isinstance(details, dict):
                    overall = details.get("overallSavingsMs")
                    if overall:
                        savings_ms = round(overall)
                    overall_bytes = details.get("overallSavingsBytes")
                    if overall_bytes:
                        savings_bytes = round(overall_bytes)

                issues.append({
                    "id": audit_id,
                    "title": audit.get("title", audit_id),
                    "score": score,
                    "display": audit.get("displayValue", ""),
                    "savings_ms": savings_ms,
                    "savings_bytes": savings_bytes,
                })

        issues.sort(key=lambda x: (x["score"] or 0, -(x["savings_ms"] or 0)))
        return issues
    except Exception as e:
        return [{"error": str(e)}]


def parse_lighthouse_tap_targets(json_path: str) -> dict:
    """Extract tap-targets audit details."""
    try:
        with open(json_path) as f:
            data = json.load(f)
        audit = data.get("audits", {}).get("tap-targets", {})
        if audit.get("score") == 1:
            return {"pass": True, "items": []}
        items = audit.get("details", {}).get("items", [])
        results = []
        for item in items:
            tap_target = item.get("tapTarget", {})
            overlapping = item.get("overlappingTarget", {})
            results.append({
                "selector": tap_target.get("selector", ""),
                "snippet": tap_target.get("snippet", ""),
                "size": item.get("size", ""),
                "overlapping_selector": overlapping.get("selector", ""),
            })
        return {"pass": False, "score": audit.get("score"), "items": results}
    except Exception:
        return {"error": "Could not parse tap targets"}


def parse_lighthouse_font_size(json_path: str) -> dict:
    """Extract font-size audit details."""
    try:
        with open(json_path) as f:
            data = json.load(f)
        audit = data.get("audits", {}).get("font-size", {})
        if audit.get("score") == 1:
            return {"pass": True, "items": []}
        items = audit.get("details", {}).get("items", [])
        results = []
        for item in items:
            results.append({
                "selector": item.get("selector", ""),
                "font_size": item.get("fontSize", ""),
                "coverage": item.get("coverage", ""),
            })
        return {"pass": False, "score": audit.get("score"), "items": results}
    except Exception:
        return {"error": "Could not parse font sizes"}


def parse_lighthouse_color_contrast(json_path: str) -> dict:
    """Extract color-contrast audit details."""
    try:
        with open(json_path) as f:
            data = json.load(f)
        audit = data.get("audits", {}).get("color-contrast", {})
        if audit.get("score") == 1:
            return {"pass": True, "items": []}
        items = audit.get("details", {}).get("items", [])
        results = []
        for item in items:
            node = item.get("node", {})
            results.append({
                "selector": node.get("selector", ""),
                "snippet": node.get("snippet", ""),
                "explanation": node.get("explanation", ""),
            })
        return {"pass": False, "score": audit.get("score"), "items": results}
    except Exception:
        return {"error": "Could not parse color contrast"}


def run_full_lighthouse(url: str, form_factor: str = "both") -> dict:
    """Run Lighthouse and return structured results. Falls back to basic timing if unavailable."""
    if not is_lighthouse_available():
        return _fallback_performance(url)

    results: dict = {}
    factors = ["mobile", "desktop"] if form_factor == "both" else [form_factor]

    for ff in factors:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            success = run_lighthouse(url, ff, tmp_path)
            if success:
                results[ff] = {
                    "scores": parse_lighthouse_scores(tmp_path),
                    "cwv": parse_cwv(tmp_path),
                    "issues": parse_lighthouse_issues(tmp_path),
                    "tap_targets": parse_lighthouse_tap_targets(tmp_path),
                    "font_size": parse_lighthouse_font_size(tmp_path),
                    "color_contrast": parse_lighthouse_color_contrast(tmp_path),
                }
            else:
                results[ff] = {"error": "Lighthouse run failed"}
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    return results


def _fallback_performance(url: str) -> dict:
    """Basic performance check without Lighthouse."""
    import time
    import requests

    try:
        start = time.time()
        r = requests.get(url, timeout=15)
        elapsed = round((time.time() - start) * 1000)
        return {
            "fallback": True,
            "message": "Lighthouse niedostępny — podstawowy pomiar czasu ładowania",
            "load_time_ms": elapsed,
            "status_code": r.status_code,
            "content_length": len(r.content),
        }
    except Exception as e:
        return {"fallback": True, "error": str(e)}
