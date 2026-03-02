"""Structured data and schema markup tools — validation, generation, rich results."""

import logging
from datetime import datetime, timezone

from seoleo.core.collectors import fetch_html
from seoleo.core.parsers import parse_schema

logger = logging.getLogger(__name__)

# --------------- Schema Type Definitions ---------------

SCHEMA_REQUIREMENTS: dict[str, dict] = {
    "Article": {
        "required": ["headline", "author", "datePublished", "image"],
        "recommended": ["dateModified", "publisher"],
    },
    "NewsArticle": {
        "required": ["headline", "author", "datePublished", "image"],
        "recommended": ["dateModified", "publisher"],
    },
    "BlogPosting": {
        "required": ["headline", "author", "datePublished", "image"],
        "recommended": ["dateModified", "publisher"],
    },
    "Product": {
        "required": ["name", "image"],
        "recommended": ["price", "availability", "review", "brand"],
    },
    "FAQPage": {
        "required": ["mainEntity"],
        "recommended": [],
    },
    "LocalBusiness": {
        "required": ["name", "address"],
        "recommended": ["telephone", "openingHours", "geo"],
    },
    "Organization": {
        "required": ["name", "url"],
        "recommended": ["logo", "contactPoint", "sameAs"],
    },
    "HowTo": {
        "required": ["name", "step"],
        "recommended": ["totalTime", "image"],
    },
    "Recipe": {
        "required": ["name", "image"],
        "recommended": ["author", "prepTime", "cookTime", "nutrition"],
    },
    "Event": {
        "required": ["name", "startDate", "location"],
        "recommended": ["endDate", "image", "description"],
    },
    "VideoObject": {
        "required": ["name", "uploadDate", "thumbnailUrl"],
        "recommended": ["description", "duration"],
    },
    "Person": {
        "required": ["name"],
        "recommended": ["jobTitle", "image", "sameAs"],
    },
    "BreadcrumbList": {
        "required": ["itemListElement"],
        "recommended": [],
    },
    "Review": {
        "required": ["itemReviewed", "reviewRating", "author"],
        "recommended": [],
    },
}

# Map of schema types that inherit Article requirements
_ARTICLE_SUBTYPES = {"NewsArticle", "BlogPosting"}

RICH_RESULT_MAP: dict[str, str] = {
    "Article": "Article rich result",
    "NewsArticle": "Article rich result",
    "BlogPosting": "Article rich result",
    "FAQPage": "FAQ rich result",
    "Product": "Product snippet",
    "Recipe": "Recipe card",
    "HowTo": "How-to rich result",
    "Event": "Event listing",
    "Review": "Review snippet",
    "BreadcrumbList": "Breadcrumb trail",
    "VideoObject": "Video rich result",
}

GENERATOR_TYPES: dict[str, dict] = {
    "Article": {
        "required": ["headline", "author", "datePublished", "image"],
        "optional": ["dateModified", "publisher", "description", "mainEntityOfPage"],
    },
    "Product": {
        "required": ["name", "image"],
        "optional": [
            "description", "brand", "sku", "offers", "review",
            "aggregateRating", "price", "availability",
        ],
    },
    "FAQ": {
        "required": ["mainEntity"],
        "optional": [],
    },
    "HowTo": {
        "required": ["name", "step"],
        "optional": ["description", "totalTime", "image", "supply", "tool"],
    },
    "LocalBusiness": {
        "required": ["name", "address"],
        "optional": [
            "telephone", "openingHours", "geo", "url", "image",
            "priceRange", "sameAs",
        ],
    },
    "Organization": {
        "required": ["name", "url"],
        "optional": ["logo", "contactPoint", "sameAs", "description", "foundingDate"],
    },
    "Event": {
        "required": ["name", "startDate", "location"],
        "optional": [
            "endDate", "image", "description", "organizer",
            "performer", "offers", "eventStatus", "eventAttendanceMode",
        ],
    },
    "Recipe": {
        "required": ["name", "image"],
        "optional": [
            "author", "prepTime", "cookTime", "totalTime", "nutrition",
            "recipeYield", "recipeIngredient", "recipeInstructions",
            "recipeCategory", "recipeCuisine", "description",
        ],
    },
    "VideoObject": {
        "required": ["name", "uploadDate", "thumbnailUrl"],
        "optional": [
            "description", "duration", "contentUrl", "embedUrl",
            "interactionStatistic",
        ],
    },
    "Person": {
        "required": ["name"],
        "optional": [
            "jobTitle", "image", "sameAs", "url", "email",
            "worksFor", "alumniOf", "description",
        ],
    },
}


# --------------- Helpers ---------------


def _resolve_schema_type(schema: dict) -> str | None:
    """Extract the primary @type from a JSON-LD block, handling lists and URLs."""
    raw_type = schema.get("@type")
    if raw_type is None:
        return None
    if isinstance(raw_type, list):
        raw_type = raw_type[0] if raw_type else None
    if raw_type is None:
        return None
    # Strip schema.org prefix if present (e.g. "https://schema.org/Article")
    if "/" in raw_type:
        raw_type = raw_type.rsplit("/", 1)[-1]
    return raw_type


def _has_field(schema: dict, field: str) -> bool:
    """Check if a schema dict contains a given field with a non-empty value."""
    value = schema.get(field)
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    if isinstance(value, list) and len(value) == 0:
        return False
    return True


def _validate_faq_structure(schema: dict) -> list[str]:
    """Validate FAQ-specific structure: mainEntity must have Question+acceptedAnswer."""
    issues: list[str] = []
    main_entity = schema.get("mainEntity")
    if not main_entity:
        issues.append("FAQPage: missing 'mainEntity' array")
        return issues

    if not isinstance(main_entity, list):
        main_entity = [main_entity]

    if len(main_entity) == 0:
        issues.append("FAQPage: 'mainEntity' is empty — add at least one question")
        return issues

    for i, item in enumerate(main_entity):
        item_type = _resolve_schema_type(item)
        if item_type != "Question":
            issues.append(f"FAQPage: mainEntity[{i}] should be type 'Question', got '{item_type}'")
        if not _has_field(item, "name") and not _has_field(item, "text"):
            issues.append(f"FAQPage: mainEntity[{i}] missing question text ('name' or 'text')")
        accepted = item.get("acceptedAnswer")
        if not accepted:
            issues.append(f"FAQPage: mainEntity[{i}] missing 'acceptedAnswer'")
        elif isinstance(accepted, dict):
            if not _has_field(accepted, "text"):
                issues.append(f"FAQPage: mainEntity[{i}].acceptedAnswer missing 'text'")

    return issues


def _validate_single_schema(schema: dict) -> dict:
    """Validate one JSON-LD block against Google requirements."""
    schema_type = _resolve_schema_type(schema)
    if not schema_type:
        return {
            "type": "Unknown",
            "valid": False,
            "missing_required": [],
            "missing_recommended": [],
            "issues": ["No @type found in JSON-LD block"],
        }

    # Look up requirements — check for exact match first, then canonical parent
    reqs = SCHEMA_REQUIREMENTS.get(schema_type)
    if not reqs:
        return {
            "type": schema_type,
            "valid": True,
            "missing_required": [],
            "missing_recommended": [],
            "issues": [],
            "note": f"Type '{schema_type}' is not in the validation ruleset — skipped detailed check",
        }

    missing_required: list[str] = []
    missing_recommended: list[str] = []

    for field in reqs["required"]:
        if not _has_field(schema, field):
            missing_required.append(field)

    for field in reqs["recommended"]:
        if not _has_field(schema, field):
            missing_recommended.append(field)

    # Additional structural validations
    extra_issues: list[str] = []

    if schema_type == "FAQPage":
        extra_issues.extend(_validate_faq_structure(schema))

    if schema_type == "BreadcrumbList":
        items = schema.get("itemListElement")
        if isinstance(items, list):
            for i, item in enumerate(items):
                if not _has_field(item, "position"):
                    extra_issues.append(f"BreadcrumbList: itemListElement[{i}] missing 'position'")
                if not _has_field(item, "name") and not _has_field(item, "item"):
                    extra_issues.append(
                        f"BreadcrumbList: itemListElement[{i}] missing 'name' or 'item'"
                    )

    # Product with offers sub-object — check price/availability there too
    if schema_type == "Product":
        offers = schema.get("offers")
        if isinstance(offers, dict):
            if _has_field(offers, "price"):
                # Remove price from missing_recommended if found in offers
                if "price" in missing_recommended:
                    missing_recommended.remove("price")
            if _has_field(offers, "availability"):
                if "availability" in missing_recommended:
                    missing_recommended.remove("availability")
        elif isinstance(offers, list):
            has_price = any(_has_field(o, "price") for o in offers)
            has_avail = any(_has_field(o, "availability") for o in offers)
            if has_price and "price" in missing_recommended:
                missing_recommended.remove("price")
            if has_avail and "availability" in missing_recommended:
                missing_recommended.remove("availability")

    # Review nested in author
    if schema_type in ("Article", "NewsArticle", "BlogPosting", "Review"):
        author = schema.get("author")
        if isinstance(author, dict) and _has_field(author, "name"):
            pass  # author is valid as an object
        elif isinstance(author, list) and len(author) > 0:
            pass  # author is valid as a list
        elif isinstance(author, str) and author.strip():
            pass  # author is valid as a string
        elif "author" not in missing_required:
            pass  # already flagged
        # else: already captured in missing_required

    is_valid = len(missing_required) == 0 and len(extra_issues) == 0

    return {
        "type": schema_type,
        "valid": is_valid,
        "missing_required": missing_required,
        "missing_recommended": missing_recommended,
        "issues": extra_issues,
    }


def _compute_schema_score(validation_results: list[dict], schemas_found: int) -> int:
    """Compute a 1-10 score based on validation results."""
    if schemas_found == 0:
        return 1

    total_checks = 0
    passed_checks = 0

    for result in validation_results:
        reqs = SCHEMA_REQUIREMENTS.get(result["type"])
        if not reqs:
            # Unknown type — give neutral credit
            total_checks += 1
            passed_checks += 1
            continue

        n_required = len(reqs["required"])
        n_recommended = len(reqs["recommended"])
        n_missing_required = len(result["missing_required"])
        n_missing_recommended = len(result["missing_recommended"])
        n_issues = len(result["issues"])

        # Required fields: weighted 2x
        total_checks += n_required * 2
        passed_checks += (n_required - n_missing_required) * 2

        # Recommended fields: weighted 1x
        total_checks += n_recommended
        passed_checks += n_recommended - n_missing_recommended

        # Extra issues penalty
        total_checks += n_issues
        # passed_checks stays the same (0 credit for extra issues)

    if total_checks == 0:
        return 5

    ratio = passed_checks / total_checks
    # Scale to 1-10 range, with a bonus point for having schemas at all
    score = max(1, min(10, round(ratio * 9) + 1))
    return score


# --------------- Public Functions ---------------


def validate_schema(url: str) -> dict:
    """Validate structured data (JSON-LD) on a page against Google requirements.

    Fetches the page, parses JSON-LD blocks, and validates each against known
    schema type requirements (required + recommended fields).

    Returns dict with status, url, timestamp, data (schemas_found, validation_results),
    score (1-10), issues, and recommendations.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    html, status_code, _headers = fetch_html(url)
    if not html:
        return {
            "status": "error",
            "url": url,
            "timestamp": timestamp,
            "message": f"Failed to fetch page (HTTP {status_code})",
        }

    schema_data = parse_schema(html)
    json_ld_blocks = schema_data.get("json_ld", [])
    microdata = schema_data.get("microdata", [])

    # Flatten @graph blocks
    flattened: list[dict] = []
    for block in json_ld_blocks:
        if isinstance(block, dict) and "@graph" in block:
            graph = block["@graph"]
            if isinstance(graph, list):
                flattened.extend(graph)
            else:
                flattened.append(block)
        else:
            flattened.append(block)

    # Build schemas_found list
    schemas_found: list[dict] = []
    for block in flattened:
        schema_type = _resolve_schema_type(block)
        schemas_found.append({
            "type": schema_type or "Unknown",
            "fields": list(block.keys()) if isinstance(block, dict) else [],
        })

    # Validate each block
    validation_results: list[dict] = []
    for block in flattened:
        if isinstance(block, dict):
            result = _validate_single_schema(block)
            validation_results.append(result)

    # Collect all issues
    all_issues: list[str] = []
    if len(flattened) == 0 and len(microdata) == 0:
        all_issues.append("No structured data found on this page")
    elif len(flattened) == 0 and len(microdata) > 0:
        all_issues.append(
            "Only Microdata found — consider adding JSON-LD for better Google compatibility"
        )

    for result in validation_results:
        for field in result["missing_required"]:
            all_issues.append(
                f"{result['type']}: missing required field '{field}'"
            )
        for issue in result["issues"]:
            all_issues.append(issue)

    # Generate recommendations
    recommendations: list[str] = []
    if len(flattened) == 0:
        recommendations.append(
            "Add JSON-LD structured data to improve search engine understanding"
        )
        recommendations.append(
            "Start with the most relevant type for your page (Article, Product, LocalBusiness, etc.)"
        )
    else:
        for result in validation_results:
            if result["missing_required"]:
                recommendations.append(
                    f"Fix {result['type']}: add required fields — "
                    + ", ".join(result["missing_required"])
                )
            if result["missing_recommended"]:
                recommendations.append(
                    f"Improve {result['type']}: add recommended fields — "
                    + ", ".join(result["missing_recommended"])
                )

    # Check for common missing types
    found_types = {_resolve_schema_type(b) for b in flattened if isinstance(b, dict)}
    if "BreadcrumbList" not in found_types:
        recommendations.append(
            "Add BreadcrumbList schema to enable breadcrumb trail in search results"
        )

    score = _compute_schema_score(validation_results, len(flattened))

    return {
        "status": "success",
        "url": url,
        "timestamp": timestamp,
        "data": {
            "schemas_found": schemas_found,
            "validation_results": validation_results,
            "microdata_count": len(microdata),
        },
        "score": score,
        "issues": all_issues,
        "recommendations": recommendations,
    }


def generate_schema(schema_type: str, data: dict) -> dict:
    """Generate valid JSON-LD markup for a given schema type.

    Fills in provided data fields and inserts placeholders for missing required fields.
    Supported types: Article, Product, FAQ, HowTo, LocalBusiness, Organization,
    Event, Recipe, VideoObject, Person.

    Returns dict with status, schema_type, json_ld, required_fields, optional_fields.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Normalise type name
    normalized_type = schema_type.strip()
    # Allow common aliases
    type_aliases: dict[str, str] = {
        "FAQ": "FAQ",
        "FAQPage": "FAQ",
        "faq": "FAQ",
        "article": "Article",
        "product": "Product",
        "howto": "HowTo",
        "how-to": "HowTo",
        "localbusiness": "LocalBusiness",
        "local_business": "LocalBusiness",
        "organization": "Organization",
        "event": "Event",
        "recipe": "Recipe",
        "videoobject": "VideoObject",
        "video": "VideoObject",
        "person": "Person",
    }
    canonical_type = type_aliases.get(normalized_type.lower(), normalized_type)

    gen_spec = GENERATOR_TYPES.get(canonical_type)
    if not gen_spec:
        return {
            "status": "error",
            "schema_type": schema_type,
            "timestamp": timestamp,
            "message": (
                f"Unsupported schema type '{schema_type}'. "
                f"Supported: {', '.join(sorted(GENERATOR_TYPES.keys()))}"
            ),
        }

    # Build the JSON-LD structure
    json_ld = _build_json_ld(canonical_type, data, gen_spec)

    return {
        "status": "success",
        "schema_type": canonical_type,
        "timestamp": timestamp,
        "json_ld": json_ld,
        "required_fields": gen_spec["required"],
        "optional_fields": gen_spec["optional"],
    }


def _build_json_ld(schema_type: str, data: dict, spec: dict) -> dict:
    """Build a JSON-LD dict for the given type, filling data and placeholders."""
    # Map canonical type to schema.org @type
    type_map: dict[str, str] = {
        "FAQ": "FAQPage",
        "Article": "Article",
        "Product": "Product",
        "HowTo": "HowTo",
        "LocalBusiness": "LocalBusiness",
        "Organization": "Organization",
        "Event": "Event",
        "Recipe": "Recipe",
        "VideoObject": "VideoObject",
        "Person": "Person",
    }

    json_ld: dict = {
        "@context": "https://schema.org",
        "@type": type_map.get(schema_type, schema_type),
    }

    all_fields = spec["required"] + spec["optional"]

    for field in all_fields:
        if field in data and data[field] is not None:
            json_ld[field] = data[field]
        elif field in spec["required"]:
            json_ld[field] = _placeholder_for_field(schema_type, field)

    # Type-specific enrichments
    if schema_type == "FAQ":
        json_ld = _enrich_faq(json_ld, data)
    elif schema_type == "Article":
        json_ld = _enrich_article(json_ld, data)
    elif schema_type == "Product":
        json_ld = _enrich_product(json_ld, data)
    elif schema_type == "Event":
        json_ld = _enrich_event(json_ld, data)
    elif schema_type == "LocalBusiness":
        json_ld = _enrich_local_business(json_ld, data)
    elif schema_type == "HowTo":
        json_ld = _enrich_howto(json_ld, data)

    return json_ld


def _placeholder_for_field(schema_type: str, field: str) -> str:
    """Return a descriptive placeholder string for a missing required field."""
    placeholders: dict[str, str] = {
        "headline": "[PLACEHOLDER: Article headline — max 110 characters]",
        "author": "[PLACEHOLDER: Author name or Person object]",
        "datePublished": "[PLACEHOLDER: ISO 8601 date, e.g. 2026-03-02]",
        "dateModified": "[PLACEHOLDER: ISO 8601 date]",
        "image": "[PLACEHOLDER: Full image URL, min 1200x630px recommended]",
        "name": "[PLACEHOLDER: Name/title]",
        "address": "[PLACEHOLDER: PostalAddress object or string]",
        "url": "[PLACEHOLDER: Full URL, e.g. https://example.com]",
        "step": "[PLACEHOLDER: Array of HowToStep objects]",
        "startDate": "[PLACEHOLDER: ISO 8601 datetime, e.g. 2026-06-15T19:00:00+02:00]",
        "location": "[PLACEHOLDER: Place object with name and address]",
        "uploadDate": "[PLACEHOLDER: ISO 8601 date]",
        "thumbnailUrl": "[PLACEHOLDER: Thumbnail image URL]",
        "mainEntity": "[PLACEHOLDER: Array of Question objects with acceptedAnswer]",
        "itemListElement": "[PLACEHOLDER: Array of ListItem objects]",
        "itemReviewed": "[PLACEHOLDER: Object being reviewed (e.g. Product, LocalBusiness)]",
        "reviewRating": "[PLACEHOLDER: Rating object with ratingValue and bestRating]",
    }
    return placeholders.get(field, f"[PLACEHOLDER: {field}]")


def _enrich_faq(json_ld: dict, data: dict) -> dict:
    """Enrich FAQ JSON-LD with properly structured mainEntity."""
    main_entity = data.get("mainEntity")
    if isinstance(main_entity, list) and len(main_entity) > 0:
        structured_items: list[dict] = []
        for item in main_entity:
            if isinstance(item, dict):
                q = item.get("question") or item.get("name") or item.get("text", "")
                a = item.get("answer") or item.get("acceptedAnswer", "")
                if isinstance(a, dict):
                    a = a.get("text", "")
                structured_items.append({
                    "@type": "Question",
                    "name": q,
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": a,
                    },
                })
            elif isinstance(item, str):
                structured_items.append({
                    "@type": "Question",
                    "name": item,
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "[PLACEHOLDER: Answer text]",
                    },
                })
        json_ld["mainEntity"] = structured_items
    elif not isinstance(main_entity, list):
        # Provide example structure
        json_ld["mainEntity"] = [
            {
                "@type": "Question",
                "name": "[PLACEHOLDER: Question text]",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "[PLACEHOLDER: Answer text]",
                },
            }
        ]
    return json_ld


def _enrich_article(json_ld: dict, data: dict) -> dict:
    """Enrich Article JSON-LD with proper author/publisher structure."""
    author = data.get("author")
    if isinstance(author, str):
        json_ld["author"] = {"@type": "Person", "name": author}
    elif isinstance(author, dict) and "name" in author:
        if "@type" not in author:
            author["@type"] = "Person"
        json_ld["author"] = author

    publisher = data.get("publisher")
    if isinstance(publisher, str):
        json_ld["publisher"] = {"@type": "Organization", "name": publisher}
    elif isinstance(publisher, dict) and "name" in publisher:
        if "@type" not in publisher:
            publisher["@type"] = "Organization"
        json_ld["publisher"] = publisher

    return json_ld


def _enrich_product(json_ld: dict, data: dict) -> dict:
    """Enrich Product JSON-LD with offers structure."""
    price = data.get("price")
    availability = data.get("availability")
    currency = data.get("priceCurrency", data.get("currency"))

    if price is not None and "offers" not in json_ld:
        offers: dict = {"@type": "Offer", "price": price}
        if currency:
            offers["priceCurrency"] = currency
        if availability:
            avail_str = str(availability)
            if not avail_str.startswith("https://schema.org/"):
                avail_str = f"https://schema.org/{avail_str}"
            offers["availability"] = avail_str
        json_ld["offers"] = offers

    return json_ld


def _enrich_event(json_ld: dict, data: dict) -> dict:
    """Enrich Event JSON-LD with location structure."""
    location = data.get("location")
    if isinstance(location, str):
        json_ld["location"] = {
            "@type": "Place",
            "name": location,
            "address": "[PLACEHOLDER: Full address]",
        }
    elif isinstance(location, dict):
        if "@type" not in location:
            location["@type"] = "Place"
        json_ld["location"] = location

    return json_ld


def _enrich_local_business(json_ld: dict, data: dict) -> dict:
    """Enrich LocalBusiness JSON-LD with address structure."""
    address = data.get("address")
    if isinstance(address, str):
        json_ld["address"] = {
            "@type": "PostalAddress",
            "streetAddress": address,
        }
    elif isinstance(address, dict):
        if "@type" not in address:
            address["@type"] = "PostalAddress"
        json_ld["address"] = address

    geo = data.get("geo")
    if isinstance(geo, dict):
        if "@type" not in geo:
            geo["@type"] = "GeoCoordinates"
        json_ld["geo"] = geo

    return json_ld


def _enrich_howto(json_ld: dict, data: dict) -> dict:
    """Enrich HowTo JSON-LD with step structure."""
    steps = data.get("step")
    if isinstance(steps, list):
        structured_steps: list[dict] = []
        for i, step in enumerate(steps):
            if isinstance(step, str):
                structured_steps.append({
                    "@type": "HowToStep",
                    "position": i + 1,
                    "text": step,
                })
            elif isinstance(step, dict):
                if "@type" not in step:
                    step["@type"] = "HowToStep"
                if "position" not in step:
                    step["position"] = i + 1
                structured_steps.append(step)
        json_ld["step"] = structured_steps
    return json_ld


def check_rich_results(url: str) -> dict:
    """Check eligibility for Google Rich Results based on structured data found on a page.

    Fetches the page, parses JSON-LD, and for each schema type checks if it meets
    the minimum requirements for the corresponding Rich Result type.

    Returns dict with status, url, timestamp, data (eligible, not_eligible, missing_types),
    and recommendations.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    html, status_code, _headers = fetch_html(url)
    if not html:
        return {
            "status": "error",
            "url": url,
            "timestamp": timestamp,
            "message": f"Failed to fetch page (HTTP {status_code})",
        }

    schema_data = parse_schema(html)
    json_ld_blocks = schema_data.get("json_ld", [])

    # Flatten @graph blocks
    flattened: list[dict] = []
    for block in json_ld_blocks:
        if isinstance(block, dict) and "@graph" in block:
            graph = block["@graph"]
            if isinstance(graph, list):
                flattened.extend(graph)
            else:
                flattened.append(block)
        else:
            flattened.append(block)

    eligible: list[dict] = []
    not_eligible: list[dict] = []
    found_types: set[str] = set()

    for block in flattened:
        if not isinstance(block, dict):
            continue

        schema_type = _resolve_schema_type(block)
        if not schema_type:
            continue

        found_types.add(schema_type)

        rich_result = RICH_RESULT_MAP.get(schema_type)
        if not rich_result:
            continue

        # Validate against requirements to check eligibility
        validation = _validate_single_schema(block)

        entry = {
            "schema_type": schema_type,
            "rich_result_type": rich_result,
            "missing_required": validation["missing_required"],
            "missing_recommended": validation["missing_recommended"],
            "issues": validation["issues"],
        }

        if validation["valid"]:
            eligible.append(entry)
        else:
            not_eligible.append(entry)

    # Determine common rich result types that are missing entirely
    # Only suggest commonly useful types that are missing
    common_useful_types = {
        "Article", "FAQPage", "BreadcrumbList", "Organization",
    }
    missing_types: list[dict] = []
    for rt in sorted(common_useful_types - found_types):
        if rt in RICH_RESULT_MAP:
            missing_types.append({
                "schema_type": rt,
                "rich_result_type": RICH_RESULT_MAP[rt],
                "note": f"Add {rt} schema to be eligible for {RICH_RESULT_MAP[rt]}",
            })

    # Generate recommendations
    recommendations: list[str] = []
    if not eligible and not not_eligible:
        recommendations.append(
            "No rich result-eligible schemas found — add structured data to unlock rich results"
        )
    for entry in not_eligible:
        recommendations.append(
            f"Fix {entry['schema_type']} to unlock {entry['rich_result_type']}: "
            f"add missing fields — {', '.join(entry['missing_required'])}"
        )
    for entry in missing_types:
        recommendations.append(entry["note"])

    if eligible:
        recommendations.append(
            f"{len(eligible)} schema type(s) eligible for rich results — "
            "use Google Rich Results Test to verify live rendering"
        )

    return {
        "status": "success",
        "url": url,
        "timestamp": timestamp,
        "data": {
            "eligible": eligible,
            "not_eligible": not_eligible,
            "missing_types": missing_types,
        },
        "recommendations": recommendations,
    }
