"""SEO & UX analysis engine — issue detection, scoring, recommendations."""

CRITICAL = "critical"
HIGH = "high"
MEDIUM = "medium"
LOW = "low"

SEVERITY_PENALTY = {CRITICAL: 3, HIGH: 2, MEDIUM: 1, LOW: 0.5}
SEVERITY_ORDER = {CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3}

SCORE_CATEGORIES = {
    "meta": "Meta tagi i SEO on-page",
    "content": "Treść i struktura",
    "images": "Obrazy i multimedia",
    "links": "Linkowanie",
    "schema": "Dane strukturalne",
    "crawl": "Crawlability",
    "security": "Bezpieczeństwo",
    "performance": "Wydajność",
    "seo": "SEO techniczne",
    "accessibility": "Dostępność",
    "ux": "User Experience",
}


def detect_issues(data: dict) -> list[dict]:
    """Analyze collected data and return a list of issues with severity."""
    issues: list[dict] = []
    homepage = data.get("homepage", {})
    meta = homepage.get("meta", {})
    headings = homepage.get("headings", {})
    images = homepage.get("images", {})
    links = homepage.get("links", {})
    schema = homepage.get("schema", {})
    html_tag = homepage.get("html_tag", {})
    scripts = homepage.get("scripts", {})
    robots_txt = data.get("robots_txt")
    sitemap_urls = data.get("sitemap_urls", [])
    headers = data.get("headers", {})
    lighthouse_mobile = data.get("lighthouse_mobile", {})
    lighthouse_desktop = data.get("lighthouse_desktop", {})
    subpages = data.get("subpages", {})

    _check_meta(issues, meta, html_tag)
    _check_headings(issues, headings)
    _check_images(issues, images)
    _check_links(issues, links)
    _check_schema(issues, schema)
    _check_crawl(issues, robots_txt, sitemap_urls)
    _check_headers(issues, headers)
    _check_lighthouse(issues, lighthouse_mobile, lighthouse_desktop)
    _check_scripts(issues, scripts)
    _check_subpages(issues, subpages)

    return issues


def _check_meta(issues: list, meta: dict, html_tag: dict) -> None:
    title = meta.get("title")
    if not title:
        issues.append({"category": "meta", "severity": CRITICAL,
                        "issue": "Brak tagu <title>",
                        "recommendation": "Dodaj unikalny, opisowy tag <title> (50-60 znaków)."})
    elif len(title) < 30:
        issues.append({"category": "meta", "severity": MEDIUM,
                        "issue": f"Tag <title> za krótki ({len(title)} znaków)",
                        "recommendation": "Rozbuduj tytuł do 50-60 znaków."})
    elif len(title) > 60:
        issues.append({"category": "meta", "severity": MEDIUM,
                        "issue": f"Tag <title> za długi ({len(title)} znaków)",
                        "recommendation": "Skróć tytuł do max 60 znaków."})

    desc = meta.get("description")
    if not desc:
        issues.append({"category": "meta", "severity": HIGH,
                        "issue": "Brak meta description",
                        "recommendation": "Dodaj meta description (120-155 znaków) z call-to-action."})
    elif len(desc) < 70:
        issues.append({"category": "meta", "severity": MEDIUM,
                        "issue": f"Meta description za krótki ({len(desc)} znaków)",
                        "recommendation": "Rozbuduj opis do 120-155 znaków."})
    elif len(desc) > 160:
        issues.append({"category": "meta", "severity": LOW,
                        "issue": f"Meta description za długi ({len(desc)} znaków)",
                        "recommendation": "Skróć opis do max 155 znaków."})

    if not meta.get("canonical"):
        issues.append({"category": "meta", "severity": HIGH,
                        "issue": "Brak tagu canonical",
                        "recommendation": "Dodaj <link rel='canonical'> na każdej stronie."})

    if not meta.get("viewport"):
        issues.append({"category": "meta", "severity": CRITICAL,
                        "issue": "Brak meta viewport",
                        "recommendation": "Dodaj <meta name='viewport' content='width=device-width, initial-scale=1'>."})

    if not meta.get("og") or len(meta.get("og", {})) < 3:
        issues.append({"category": "meta", "severity": MEDIUM,
                        "issue": "Niekompletne tagi Open Graph",
                        "recommendation": "Dodaj og:title, og:description, og:image, og:url, og:type."})

    if not meta.get("twitter"):
        issues.append({"category": "meta", "severity": LOW,
                        "issue": "Brak Twitter Cards",
                        "recommendation": "Dodaj twitter:card, twitter:title, twitter:description."})

    if not html_tag.get("lang"):
        issues.append({"category": "meta", "severity": HIGH,
                        "issue": "Brak atrybutu lang w tagu <html>",
                        "recommendation": "Dodaj <html lang='pl'> (lub odpowiedni język)."})

    if not meta.get("favicon"):
        issues.append({"category": "meta", "severity": LOW,
                        "issue": "Brak favicona w HTML",
                        "recommendation": "Dodaj <link rel='icon'> z favicon."})


def _check_headings(issues: list, headings: dict) -> None:
    h1_list = headings.get("h1", [])
    if not h1_list:
        issues.append({"category": "content", "severity": CRITICAL,
                        "issue": "Brak nagłówka H1",
                        "recommendation": "Dodaj dokładnie jeden H1 z głównym słowem kluczowym."})
    elif len(h1_list) > 1:
        issues.append({"category": "content", "severity": MEDIUM,
                        "issue": f"Wiele nagłówków H1 ({len(h1_list)})",
                        "recommendation": "Ogranicz do jednego H1 na stronę."})

    if not headings.get("h2", []):
        issues.append({"category": "content", "severity": MEDIUM,
                        "issue": "Brak nagłówków H2",
                        "recommendation": "Dodaj nagłówki H2 strukturyzujące treść."})


def _check_images(issues: list, images: dict) -> None:
    if images.get("without_alt", 0) > 0:
        n = images["without_alt"]
        issues.append({"category": "images", "severity": HIGH,
                        "issue": f"{n} obrazów bez atrybutu alt",
                        "recommendation": "Dodaj opisowe atrybuty alt do wszystkich obrazów."})

    img_count = images.get("count", 0)
    if img_count > 2:
        formats = images.get("formats", {})
        modern_formats = {"webp", "avif", "svg"}
        if not any(f in modern_formats for f in formats):
            issues.append({"category": "images", "severity": MEDIUM,
                            "issue": "Brak nowoczesnych formatów obrazów (WebP/AVIF)",
                            "recommendation": "Konwertuj obrazy do WebP/AVIF."})

    if img_count > 3:
        lazy_count = sum(1 for img in images.get("images", []) if img.get("loading") == "lazy")
        if lazy_count == 0:
            issues.append({"category": "images", "severity": MEDIUM,
                            "issue": "Brak lazy loading dla obrazów",
                            "recommendation": "Dodaj loading='lazy' do obrazów poza viewportem."})


def _check_links(issues: list, links: dict) -> None:
    internal = links.get("internal", [])
    external = links.get("external", [])

    nofollow_internal = sum(1 for l in internal if "nofollow" in l.get("rel", ""))
    if nofollow_internal > 0:
        issues.append({"category": "links", "severity": MEDIUM,
                        "issue": f"{nofollow_internal} linków wewnętrznych z rel='nofollow'",
                        "recommendation": "Usuń nofollow z linków wewnętrznych."})

    ext_no_rel = sum(1 for l in external if not l.get("rel") and l.get("target") == "_blank")
    if ext_no_rel > 0:
        issues.append({"category": "security", "severity": MEDIUM,
                        "issue": f"{ext_no_rel} linków zewnętrznych target='_blank' bez rel='noopener'",
                        "recommendation": "Dodaj rel='noopener noreferrer' do linków zewnętrznych."})


def _check_schema(issues: list, schema: dict) -> None:
    if not schema.get("json_ld"):
        issues.append({"category": "schema", "severity": HIGH,
                        "issue": "Brak danych strukturalnych JSON-LD",
                        "recommendation": "Dodaj Schema.org: Organization, WebSite, breadcrumbs."})


def _check_crawl(issues: list, robots_txt: str | None, sitemap_urls: list) -> None:
    if robots_txt is None:
        issues.append({"category": "crawl", "severity": HIGH,
                        "issue": "Brak pliku robots.txt",
                        "recommendation": "Utwórz robots.txt z regułami i linkiem do sitemapy."})
    elif "disallow: /" == robots_txt.strip().lower():
        issues.append({"category": "crawl", "severity": CRITICAL,
                        "issue": "robots.txt blokuje cały serwis",
                        "recommendation": "Zmień Disallow: / na bardziej precyzyjne reguły."})

    if not sitemap_urls:
        issues.append({"category": "crawl", "severity": HIGH,
                        "issue": "Brak sitemapy XML",
                        "recommendation": "Utwórz sitemap.xml i zgłoś w Google Search Console."})


def _check_headers(issues: list, headers: dict) -> None:
    security_headers = {
        "strict-transport-security": ("Brak nagłówka HSTS", MEDIUM),
        "x-content-type-options": ("Brak X-Content-Type-Options", LOW),
        "x-frame-options": ("Brak X-Frame-Options", LOW),
        "content-security-policy": ("Brak Content-Security-Policy", MEDIUM),
    }
    h_lower = {k.lower(): v for k, v in headers.items()}
    for header_name, (desc, sev) in security_headers.items():
        if header_name not in h_lower:
            issues.append({"category": "security", "severity": sev,
                            "issue": desc,
                            "recommendation": f"Dodaj nagłówek {header_name}."})


def _check_lighthouse(issues: list, lh_mobile: dict, lh_desktop: dict) -> None:
    for label, lh_data in [("mobile", lh_mobile), ("desktop", lh_desktop)]:
        scores = lh_data.get("scores", {})
        perf = scores.get("performance", 0)
        if perf and perf < 50:
            issues.append({"category": "performance", "severity": CRITICAL,
                            "issue": f"Niska wydajność Lighthouse ({label}): {perf}/100",
                            "recommendation": f"Optymalizuj wydajność strony ({label})."})
        elif perf and perf < 90:
            issues.append({"category": "performance", "severity": MEDIUM,
                            "issue": f"Średnia wydajność Lighthouse ({label}): {perf}/100",
                            "recommendation": f"Popraw wydajność ({label}) do ≥90."})

        seo_score = scores.get("seo", 0)
        if seo_score and seo_score < 90:
            issues.append({"category": "seo", "severity": HIGH,
                            "issue": f"Niski wynik SEO Lighthouse ({label}): {seo_score}/100",
                            "recommendation": "Napraw problemy wskazane przez Lighthouse SEO audit."})

        a11y = scores.get("accessibility", 0)
        if a11y and a11y < 80:
            issues.append({"category": "accessibility", "severity": MEDIUM,
                            "issue": f"Problemy z dostępnością ({label}): {a11y}/100",
                            "recommendation": "Popraw dostępność wg WCAG 2.1."})

        cwv = lh_data.get("cwv", {})
        lcp = cwv.get("lcp", {})
        if lcp and lcp.get("value", 0) > 4000:
            issues.append({"category": "performance", "severity": HIGH,
                            "issue": f"LCP za wysoki ({label}): {lcp.get('display', '')}",
                            "recommendation": "Optymalizuj LCP (cel: <2.5s)."})
        cls = cwv.get("cls", {})
        if cls and cls.get("value", 0) > 0.25:
            issues.append({"category": "performance", "severity": HIGH,
                            "issue": f"CLS za wysoki ({label}): {cls.get('display', '')}",
                            "recommendation": "Napraw przesunięcia layoutu (cel: CLS <0.1)."})
        tbt = cwv.get("tbt", {})
        if tbt and tbt.get("value", 0) > 600:
            issues.append({"category": "performance", "severity": MEDIUM,
                            "issue": f"TBT za wysoki ({label}): {tbt.get('display', '')}",
                            "recommendation": "Zmniejsz Total Blocking Time (cel: <200ms)."})
        inp = cwv.get("inp", {})
        if inp and inp.get("value", 0) > 500:
            issues.append({"category": "performance", "severity": HIGH,
                            "issue": f"INP za wysoki ({label}): {inp.get('display', '')}",
                            "recommendation": "Optymalizuj Interaction to Next Paint (cel: <200ms)."})
        elif inp and inp.get("value", 0) > 200:
            issues.append({"category": "performance", "severity": MEDIUM,
                            "issue": f"INP wymaga poprawy ({label}): {inp.get('display', '')}",
                            "recommendation": "Popraw INP (cel: <200ms, akceptowalne: <500ms)."})
        ttfb = cwv.get("ttfb", {})
        if ttfb and ttfb.get("value", 0) > 1800:
            issues.append({"category": "performance", "severity": HIGH,
                            "issue": f"TTFB za wysoki ({label}): {ttfb.get('display', '')}",
                            "recommendation": "Optymalizuj TTFB (cel: <800ms)."})
        elif ttfb and ttfb.get("value", 0) > 800:
            issues.append({"category": "performance", "severity": MEDIUM,
                            "issue": f"TTFB wymaga poprawy ({label}): {ttfb.get('display', '')}",
                            "recommendation": "Popraw TTFB (cel: <800ms)."})


def _check_scripts(issues: list, scripts: dict) -> None:
    total_scripts = scripts.get("total_scripts", 0)
    if total_scripts > 20:
        issues.append({"category": "performance", "severity": MEDIUM,
                        "issue": f"Zbyt wiele skryptów JS ({total_scripts})",
                        "recommendation": "Zredukuj liczbę skryptów."})

    total_css = scripts.get("total_stylesheets", 0)
    if total_css > 10:
        issues.append({"category": "performance", "severity": LOW,
                        "issue": f"Zbyt wiele arkuszy CSS ({total_css})",
                        "recommendation": "Połącz arkusze CSS."})


def _check_subpages(issues: list, subpages: dict) -> None:
    for path, sp_data in subpages.items():
        sp_meta = sp_data.get("meta", {})
        if not sp_meta.get("title"):
            issues.append({"category": "meta", "severity": HIGH,
                            "issue": f"Podstrona {path}: brak <title>",
                            "recommendation": f"Dodaj unikalny <title> na {path}."})
        if not sp_meta.get("description"):
            issues.append({"category": "meta", "severity": MEDIUM,
                            "issue": f"Podstrona {path}: brak meta description",
                            "recommendation": f"Dodaj meta description na {path}."})
        sp_h1 = sp_data.get("headings", {}).get("h1", [])
        if not sp_h1:
            issues.append({"category": "content", "severity": MEDIUM,
                            "issue": f"Podstrona {path}: brak H1",
                            "recommendation": f"Dodaj nagłówek H1 na {path}."})


def detect_ux_issues(ux_data: dict, lighthouse_ux: dict | None = None) -> list[dict]:
    """Analyze UX data and return issues with severity."""
    issues: list[dict] = []
    lighthouse_ux = lighthouse_ux or {}

    # Touch targets
    tap_data = lighthouse_ux.get("tap_targets", {})
    if tap_data and not tap_data.get("pass") and not tap_data.get("error"):
        items = tap_data.get("items", [])
        if len(items) > 5:
            issues.append({"category": "ux", "severity": HIGH,
                            "issue": f"{len(items)} elementów z za małym obszarem dotyku",
                            "recommendation": "Zwiększ rozmiary do min. 48x48px."})
        elif len(items) > 0:
            issues.append({"category": "ux", "severity": MEDIUM,
                            "issue": f"{len(items)} elementów z za małym obszarem dotyku",
                            "recommendation": "Zwiększ rozmiary do min. 48x48px."})

    # Font size
    font_data = lighthouse_ux.get("font_size", {})
    if font_data and not font_data.get("pass") and not font_data.get("error"):
        issues.append({"category": "ux", "severity": MEDIUM,
                        "issue": "Tekst nie spełnia wymagań minimalnego rozmiaru czcionki",
                        "recommendation": "Użyj min. 16px bazowego rozmiaru na mobile."})

    # Color contrast
    contrast_data = lighthouse_ux.get("color_contrast", {})
    if contrast_data and not contrast_data.get("pass") and not contrast_data.get("error"):
        issues.append({"category": "ux", "severity": HIGH,
                        "issue": f"Niedostateczny kontrast kolorów ({len(contrast_data.get('items', []))} elementów)",
                        "recommendation": "Zapewnij kontrast min. 4.5:1 (WCAG AA)."})

    # Search
    search = ux_data.get("search", {})
    if not search.get("has_search"):
        issues.append({"category": "ux", "severity": MEDIUM,
                        "issue": "Brak funkcji wyszukiwania",
                        "recommendation": "Dodaj pole wyszukiwania w nawigacji."})
    elif not search.get("has_search_in_nav"):
        issues.append({"category": "ux", "severity": LOW,
                        "issue": "Wyszukiwarka nie jest w nawigacji/nagłówku",
                        "recommendation": "Przenieś wyszukiwarkę do nagłówka."})

    # Semantic structure
    semantic = ux_data.get("semantic_structure", {})
    if not semantic.get("has_main"):
        issues.append({"category": "ux", "severity": MEDIUM,
                        "issue": "Brak elementu <main>",
                        "recommendation": "Dodaj <main> okalający główną treść."})
    if not semantic.get("has_skip_link"):
        issues.append({"category": "ux", "severity": LOW,
                        "issue": "Brak linku 'Przejdź do treści'",
                        "recommendation": "Dodaj skip link na początku strony."})

    # Navigation
    nav = ux_data.get("navigation", {})
    if nav.get("nav_count", 0) == 0:
        issues.append({"category": "ux", "severity": HIGH,
                        "issue": "Brak elementu <nav>",
                        "recommendation": "Opakuj menu w <nav> z aria-label."})

    # Responsive
    responsive = ux_data.get("responsive_meta", {})
    if not responsive.get("uses_responsive_images"):
        issues.append({"category": "ux", "severity": LOW,
                        "issue": "Brak responsywnych obrazów (<picture>/srcset)",
                        "recommendation": "Użyj srcset do serwowania odpowiednich rozmiarów."})

    return issues


def calculate_scores(issues: list[dict]) -> dict:
    """Calculate category scores (1-10) based on detected issues."""
    categories = {k: {"name": v, "base": 10.0} for k, v in SCORE_CATEGORIES.items()}

    for issue in issues:
        cat = issue.get("category", "meta")
        sev = issue.get("severity", LOW)
        if cat in categories:
            categories[cat]["base"] -= SEVERITY_PENALTY.get(sev, 0)

    for cat in categories:
        categories[cat]["score"] = max(1, min(10, round(categories[cat]["base"])))

    return categories


def generate_recommendations(issues: list[dict]) -> list[dict]:
    """Generate sorted recommendations from issues."""
    sorted_issues = sorted(issues, key=lambda x: SEVERITY_ORDER.get(x.get("severity", LOW), 4))
    return [
        {
            "severity": i["severity"], "category": i["category"],
            "issue": i["issue"], "recommendation": i["recommendation"],
        }
        for i in sorted_issues
    ]


def generate_top5_problems(issues: list[dict]) -> list[dict]:
    """TOP 5 most critical problems."""
    sorted_issues = sorted(issues, key=lambda x: SEVERITY_ORDER.get(x.get("severity", LOW), 4))
    return sorted_issues[:5]


def generate_top5_quickwins(issues: list[dict]) -> list[dict]:
    """TOP 5 quick wins — high impact, low effort fixes."""
    quick_keywords = [
        "meta description", "alt", "canonical", "viewport", "lang",
        "robots.txt", "sitemap", "favicon", "noopener", "title",
        "Open Graph", "Twitter", "HSTS", "X-Content-Type",
    ]
    seen: set = set()
    quick: list = []
    for issue in issues:
        text = issue.get("issue", "") + " " + issue.get("recommendation", "")
        for kw in quick_keywords:
            if kw.lower() in text.lower():
                key = issue["issue"]
                if key not in seen:
                    seen.add(key)
                    quick.append(issue)
                break
    return quick[:5]
