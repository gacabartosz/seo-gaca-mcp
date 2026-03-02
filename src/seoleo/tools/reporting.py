"""Report generation — structured JSON + optional PDF via pdf-generator."""

import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# pdf-generator paths (local install)
_PDF_PYTHON = Path.home() / "tools/document-edit-mcp/.venv/bin/python"
_PDF_SCRIPT = Path.home() / ".agents/skills/pdf-generator/scripts/generate_pdf.py"

# Brand auto-detection from CWD
_BRAND_HINTS = {
    "beecommerce": "beecommerce",
    "personal": "bartoszgaca",
    "clients": "neutral",
}


def _detect_brand() -> str:
    """Auto-detect brand from CWD path."""
    cwd = os.getcwd()
    for hint, brand in _BRAND_HINTS.items():
        if hint in cwd:
            return brand
    return "bartoszgaca"


def _pdf_available() -> bool:
    """Check if pdf-generator is installed locally."""
    return _PDF_PYTHON.exists() and _PDF_SCRIPT.exists()


def _build_report_json(
    audit_data: dict, language: str = "en", title: str = ""
) -> dict:
    """Convert audit tool output to pdf-generator JSON format.

    Handles output from any seoleo tool (technical audit, GEO, meta check, etc.).
    Returns the content blocks structure expected by pdf-generator.
    """
    url = audit_data.get("url", "")
    timestamp = audit_data.get("timestamp", datetime.now(timezone.utc).isoformat())
    status = audit_data.get("status", "unknown")

    labels = _labels(language)
    auto_title = title or f"{labels['seo_report']}: {url}" if url else labels["seo_report"]

    content: list[dict] = []

    # Header info
    content.append({"type": "paragraph", "text": f"{labels['url']}: <b>{url}</b>"})
    content.append({"type": "paragraph", "text": f"{labels['date']}: {timestamp[:10]}"})
    content.append({"type": "separator"})

    # Overall score (if present)
    if "overall_score" in audit_data:
        score = audit_data["overall_score"]
        content.append({
            "type": "heading", "level": 1,
            "text": f"{labels['overall_score']}: {score}/10",
        })
    elif "overall_geo_score" in audit_data:
        score = audit_data["overall_geo_score"]
        content.append({
            "type": "heading", "level": 1,
            "text": f"{labels['geo_score']}: {score}/10",
        })
    elif "ai_visibility_score" in audit_data:
        score = audit_data["ai_visibility_score"]
        content.append({
            "type": "heading", "level": 1,
            "text": f"{labels['ai_visibility']}: {score}/10",
        })

    # Scores table (technical audit)
    if "scores" in audit_data and isinstance(audit_data["scores"], dict):
        content.append({"type": "heading", "level": 2, "text": labels["scores"]})
        rows = []
        for cat, val in audit_data["scores"].items():
            score_val = val if isinstance(val, (int, float)) else str(val)
            rows.append([cat.replace("_", " ").title(), f"{score_val}/10"])
        content.append({
            "type": "table",
            "headers": [labels["category"], labels["score"]],
            "rows": rows,
        })

    # Method scores (GEO audit)
    if "method_scores" in audit_data:
        content.append({"type": "heading", "level": 2, "text": labels["geo_methods"]})
        rows = []
        for method, data in audit_data["method_scores"].items():
            if "score" in data:
                rows.append([
                    method.replace("_", " ").title(),
                    f"{data['score']}/10",
                    data.get("recommendation", ""),
                ])
            elif "detected" in data:
                rows.append([
                    method.replace("_", " ").title(),
                    labels["yes"] if data["detected"] else labels["no"],
                    data.get("recommendation", ""),
                ])
        content.append({
            "type": "table",
            "headers": [labels["method"], labels["score"], labels["recommendation"]],
            "rows": rows,
        })

    # Data section (meta check, headers, etc.)
    if "data" in audit_data and isinstance(audit_data["data"], dict):
        content.append({"type": "heading", "level": 2, "text": labels["details"]})
        _render_dict(content, audit_data["data"], labels, depth=0)

    # Signals (AI visibility)
    if "signals" in audit_data and isinstance(audit_data["signals"], dict):
        content.append({"type": "heading", "level": 2, "text": labels["signals"]})
        rows = []
        for signal, value in audit_data["signals"].items():
            display = signal.replace("_", " ").title()
            if isinstance(value, bool):
                rows.append([display, labels["pass"] if value else labels["fail"]])
            else:
                rows.append([display, str(value)])
        content.append({
            "type": "table",
            "headers": [labels["signal"], labels["status_col"]],
            "rows": rows,
        })

    # Issues
    if "issues" in audit_data and isinstance(audit_data["issues"], list):
        content.append({"type": "heading", "level": 2, "text": labels["issues"]})
        for issue in audit_data["issues"][:30]:
            if isinstance(issue, dict):
                sev = issue.get("severity", "info").upper()
                msg = issue.get("message", str(issue))
                content.append({
                    "type": "paragraph",
                    "text": f"<b>[{sev}]</b> {msg}",
                })
            else:
                content.append({"type": "paragraph", "text": str(issue)})

    # TOP 5 problems
    if "top5_problems" in audit_data:
        content.append({"type": "heading", "level": 2, "text": labels["top5_problems"]})
        items = [str(p) if isinstance(p, str) else p.get("message", str(p))
                 for p in audit_data["top5_problems"]]
        content.append({"type": "list", "ordered": True, "items": items})

    # Quick wins
    if "top5_quickwins" in audit_data:
        content.append({"type": "heading", "level": 2, "text": labels["quick_wins"]})
        items = [str(q) if isinstance(q, str) else q.get("message", str(q))
                 for q in audit_data["top5_quickwins"]]
        content.append({"type": "list", "ordered": True, "items": items})

    # Recommendations
    recs = audit_data.get("recommendations", [])
    if recs:
        content.append({"type": "heading", "level": 2, "text": labels["recommendations"]})
        items = [str(r) for r in recs if r]
        if items:
            content.append({"type": "list", "ordered": False, "items": items})

    # Schema info
    if "schema" in audit_data and isinstance(audit_data["schema"], dict):
        content.append({"type": "heading", "level": 2, "text": labels["schema"]})
        rows = []
        for k, v in audit_data["schema"].items():
            rows.append([k.replace("_", " ").title(), str(v)])
        content.append({
            "type": "table",
            "headers": [labels["property"], labels["value"]],
            "rows": rows,
        })

    # AI crawlers summary
    if "crawlers" in audit_data and isinstance(audit_data["crawlers"], dict):
        content.append({"type": "heading", "level": 2, "text": labels["ai_crawlers"]})
        rows = []
        for bot, info in audit_data["crawlers"].items():
            if isinstance(info, dict):
                status_text = labels["allowed"] if info.get("allowed") else labels["blocked"]
                rows.append([bot, status_text])
        if rows:
            content.append({
                "type": "table",
                "headers": [labels["crawler"], labels["status_col"]],
                "rows": rows,
            })

    return {
        "title": auto_title,
        "subtitle": f"seoleo-mcp | {timestamp[:10]}",
        "date": timestamp[:10],
        "author": "seoleo-mcp",
        "show_logo": True,
        "content": content,
    }


def _render_dict(content: list, data: dict, labels: dict, depth: int) -> None:
    """Recursively render a dict into content blocks."""
    if depth > 2:
        return
    rows = []
    nested = {}
    for k, v in data.items():
        key_display = k.replace("_", " ").title()
        if isinstance(v, dict):
            nested[key_display] = v
        elif isinstance(v, list):
            if v and isinstance(v[0], dict):
                nested[key_display] = v
            else:
                rows.append([key_display, ", ".join(str(i) for i in v)])
        else:
            rows.append([key_display, str(v) if v is not None else "-"])

    if rows:
        content.append({
            "type": "table",
            "headers": [labels["property"], labels["value"]],
            "rows": rows,
        })

    for name, nested_data in nested.items():
        content.append({"type": "heading", "level": min(3, depth + 2), "text": name})
        if isinstance(nested_data, dict):
            _render_dict(content, nested_data, labels, depth + 1)
        elif isinstance(nested_data, list):
            for i, item in enumerate(nested_data[:10]):
                if isinstance(item, dict):
                    _render_dict(content, item, labels, depth + 1)
                    if i < len(nested_data) - 1:
                        content.append({"type": "spacer", "height": 6})


def _labels(language: str) -> dict:
    """UI labels in supported languages."""
    if language.startswith("pl"):
        return {
            "seo_report": "Raport SEO",
            "url": "Adres URL",
            "date": "Data",
            "overall_score": "Wynik ogolny",
            "geo_score": "Wynik GEO",
            "ai_visibility": "Widocznosc AI",
            "scores": "Wyniki",
            "category": "Kategoria",
            "score": "Wynik",
            "geo_methods": "Metody GEO (Princeton)",
            "method": "Metoda",
            "recommendation": "Rekomendacja",
            "details": "Szczegoly",
            "signals": "Sygnaly",
            "signal": "Sygnal",
            "status_col": "Status",
            "pass": "OK",
            "fail": "BRAK",
            "yes": "TAK",
            "no": "NIE",
            "issues": "Problemy",
            "top5_problems": "TOP 5 problemow",
            "quick_wins": "Szybkie poprawki",
            "recommendations": "Rekomendacje",
            "schema": "Dane strukturalne",
            "property": "Wlasciwosc",
            "value": "Wartosc",
            "ai_crawlers": "Crawlery AI",
            "crawler": "Crawler",
            "allowed": "Dozwolony",
            "blocked": "Zablokowany",
        }
    return {
        "seo_report": "SEO Audit Report",
        "url": "URL",
        "date": "Date",
        "overall_score": "Overall Score",
        "geo_score": "GEO Score",
        "ai_visibility": "AI Visibility",
        "scores": "Scores",
        "category": "Category",
        "score": "Score",
        "geo_methods": "GEO Methods (Princeton)",
        "method": "Method",
        "recommendation": "Recommendation",
        "details": "Details",
        "signals": "Signals",
        "signal": "Signal",
        "status_col": "Status",
        "pass": "PASS",
        "fail": "FAIL",
        "yes": "YES",
        "no": "NO",
        "issues": "Issues",
        "top5_problems": "TOP 5 Problems",
        "quick_wins": "Quick Wins",
        "recommendations": "Recommendations",
        "schema": "Structured Data",
        "property": "Property",
        "value": "Value",
        "ai_crawlers": "AI Crawlers",
        "crawler": "Crawler",
        "allowed": "Allowed",
        "blocked": "Blocked",
    }


def generate_report(
    audit_data: dict,
    format: str = "json",
    language: str = "en",
    title: str = "",
    output_path: str = "",
    brand: str = "",
) -> dict:
    """Generate a structured SEO audit report from any seoleo tool output.

    Args:
        audit_data: Output dict from any seoleo tool (technical audit, GEO, meta, etc.)
        format: 'json' returns content blocks, 'pdf' generates PDF file
        language: 'en' or 'pl' for report labels
        title: Custom report title (auto-generated if empty)
        output_path: PDF output path (auto-generated if empty, only for format='pdf')
        brand: Brand profile for PDF: 'bartoszgaca', 'beecommerce', 'neutral' (auto-detected)

    Returns:
        dict with status, report_json (always), and pdf_path (if format='pdf')
    """
    report_json = _build_report_json(audit_data, language, title)

    result: dict = {
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "format": format,
        "report_json": report_json,
    }

    if format == "pdf":
        if not _pdf_available():
            result["pdf_status"] = "unavailable"
            result["pdf_message"] = (
                "PDF generator not found locally. "
                "The report_json field contains the full report structure — "
                "you can save it as JSON and pass it to any compatible PDF renderer."
            )
            return result

        brand = brand or _detect_brand()
        if not output_path:
            url = audit_data.get("url", "audit")
            domain = url.replace("https://", "").replace("http://", "").split("/")[0]
            safe_domain = domain.replace(".", "_")
            date_str = datetime.now().strftime("%Y%m%d_%H%M")
            output_dir = Path.home() / "output/personal"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / f"seoleo_{safe_domain}_{date_str}.pdf")

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as f:
                json.dump(report_json, f, ensure_ascii=False, indent=2)
                tmp_json = f.name

            cmd = [
                str(_PDF_PYTHON),
                str(_PDF_SCRIPT),
                tmp_json,
                output_path,
                "--brand", brand,
                "--title-page",
            ]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )

            os.unlink(tmp_json)

            if proc.returncode == 0 and Path(output_path).exists():
                result["pdf_status"] = "generated"
                result["pdf_path"] = output_path
                result["pdf_brand"] = brand
            else:
                result["pdf_status"] = "error"
                result["pdf_error"] = proc.stderr[:500] if proc.stderr else "Unknown error"
                logger.error("PDF generation failed: %s", proc.stderr)

        except subprocess.TimeoutExpired:
            result["pdf_status"] = "error"
            result["pdf_error"] = "PDF generation timed out (30s)"
        except Exception as e:
            result["pdf_status"] = "error"
            result["pdf_error"] = str(e)
            logger.error("PDF generation error: %s", e)

    return result
