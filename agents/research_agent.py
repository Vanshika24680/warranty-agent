
import re

from tools.web_search_tool import resilient_web_search
from tools.web_reader_tool import read_webpage, is_official_domain


MAX_PAGES = 6
MAX_STEPS = 6
MAX_CONTENT_CHARS = 12000

SYMPTOM_PATTERNS = {
    "battery_drain": [
        r"\bbattery drain\w*\b",
        r"\bbattery discharg\w*\b",
        r"\bbattery backup\b",
        r"\bbattery life\b",
        r"\bdrains? (?:too )?quickly\b",
        r"\brapid battery loss\b",
        r"\bshort battery life\b",
        r"\bpoor battery life\b",
        r"\bbattery.*(?:reduced|decreased|shortened)\b",
    ],
    "charging_failure": [
        r"\bnot charg\w*\b",
        r"\bwon't charg\w*\b",
        r"\bdoesn't charg\w*\b",
        r"\bunable to charg\w*\b",
        r"\bcharging port\b",
        r"\bpower adapter\b",
        r"\bac adapter\b",
        r"\bcharger not detected\b",
        r"\bnot working when unplugged\b",
    ],
    "overheating": [
        r"\boverheat\w*\b",
        r"\btoo hot\b",
        r"\bexcessive heat\b",
        r"\btemperature too high\b",
        r"\bhigh temperature\b",
    ],
    "fan_noise": [
        r"\bfan noise\b",
        r"\bnoisy fan\b",
        r"\bloud fan\b",
        r"\bfan is loud\b",
        r"\bfan making noise\b",
    ],
    "slow_performance": [
        r"\bslow performance\b",
        r"\brunning slowly\b",
        r"\bslow laptop\b",
        r"\bpoor performance\b",
        r"\blagging\b",
        r"\bfreezing\b",
    ],
    "display_problem": [
        r"\bblack screen\b",
        r"\bblank screen\b",
        r"\bflickering\b",
        r"\bdisplay problem\b",
        r"\bscreen not working\b",
    ],
    "network_problem": [
        r"\bwi-?fi\b",
        r"\binternet connection\b",
        r"\bnetwork connection\b",
        r"\bnot connecting to internet\b",
    ],
    "audio_problem": [
        r"\bno sound\b",
        r"\baudio problem\b",
        r"\bspeaker not working\b",
        r"\bmicrophone not working\b",
    ],
}

ACTION_RULES = {
    "battery_drain": [
        ("brightness", r"\b(?:reduce|lower|decrease|adjust|dim)\b.{0,100}\bbrightness\b|\bbrightness\b.{0,100}\b(?:reduce|lower|decrease|adjust)\b"),
        ("battery saver", r"\b(?:enable|turn on|use|select|activate)\b.{0,70}\bbattery saver\b|\bbattery saver\b.{0,70}\b(?:enable|turn on|use|select|activate)\b"),
        ("power settings", r"\b(?:change|adjust|select|set|configure)\b.{0,100}\b(?:power settings|power plan|power mode)\b"),
        ("background applications", r"\b(?:close|stop|disable|limit|manage)\b.{0,100}\b(?:background apps|background applications|unnecessary applications|unnecessary programs)\b"),
        ("battery diagnostics", r"\b(?:run|perform|use|start)\b.{0,80}\b(?:battery check|battery test|battery diagnostics|battery diagnostic)\b"),
        ("battery health", r"\b(?:check|test|monitor|assess)\b.{0,80}\bbattery health\b"),
    ],
    "charging_failure": [
        ("power adapter", r"\b(?:check|inspect|connect|disconnect|reconnect|replace)\b.{0,80}\b(?:power adapter|ac adapter|charger)\b"),
        ("charging port", r"\b(?:check|inspect|clean)\b.{0,60}\bcharging port\b"),
        ("battery diagnostics", r"\b(?:run|perform|use|start)\b.{0,80}\b(?:battery check|battery test|battery diagnostics|battery diagnostic)\b"),
        ("hard reset", r"\b(?:perform|try|complete)\b.{0,50}\bhard reset\b"),
    ],
    "overheating": [
        ("ventilation", r"\b(?:keep|place|move|position|ensure)\b.{0,100}\b(?:vents|ventilation|airflow)\b"),
        ("cooling", r"\b(?:clean|check|inspect|ensure)\b.{0,80}\b(?:fan|cooling system|air vents)\b"),
    ],
    "fan_noise": [
        ("fan", r"\b(?:check|inspect|clean|test)\b.{0,80}\b(?:fan|cooling system)\b"),
        ("ventilation", r"\b(?:check|clean|clear|ensure)\b.{0,80}\b(?:vents|airflow|ventilation)\b"),
    ],
    "slow_performance": [
        ("task manager", r"\b(?:open|use|check|review)\b.{0,60}\btask manager\b"),
        ("background applications", r"\b(?:close|stop|disable|manage)\b.{0,100}\b(?:background apps|background applications|unnecessary programs)\b"),
        ("startup applications", r"\b(?:disable|manage|review|change)\b.{0,80}\bstartup applications\b"),
    ],
    "display_problem": [
        ("display settings", r"\b(?:change|adjust|check|configure)\b.{0,80}\bdisplay settings\b"),
        ("display driver", r"\b(?:update|reinstall|check)\b.{0,80}\bdisplay driver\b"),
        ("external monitor", r"\b(?:connect|test|try|use)\b.{0,80}\bexternal monitor\b"),
    ],
    "network_problem": [
        ("network troubleshooter", r"\b(?:run|use|open|start)\b.{0,80}\bnetwork troubleshooter\b"),
        ("network adapter", r"\b(?:check|update|reset|enable|disable)\b.{0,80}\bnetwork adapter\b"),
    ],
    "audio_problem": [
        ("audio troubleshooter", r"\b(?:run|use|open|start)\b.{0,80}\baudio troubleshooter\b"),
        ("audio settings", r"\b(?:check|change|adjust|configure)\b.{0,80}\b(?:audio|sound) settings\b"),
        ("audio driver", r"\b(?:update|reinstall|check)\b.{0,80}\baudio driver\b"),
    ],
}


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def safe_text(value):
    return str(value or "").strip()


def detect_symptoms(text):
    text = safe_text(text).lower()

    return {
        category
        for category, patterns in SYMPTOM_PATTERNS.items()
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)
    }


def insufficient_result(trace, message, warnings=None, sources=None):
    return {
        "status": "INSUFFICIENT_EVIDENCE",
        "recommendation": {
            "summary": message,
            "safe_steps": [],
            "step_evidence": [],
            "supported_symptoms": [],
            "unsupported_symptoms": [],
            "warnings": warnings or [
                "No explicit, verifiable manufacturer troubleshooting instruction was identified."
            ],
            "confidence": "LOW",
            "next_action": (
                "Consult the manufacturer's authorised support service "
                "for product-specific assistance."
            ),
        },
        "sources": sources or [],
        "execution_trace": trace,
    }


def get_source_fallbacks(brand):
    fallbacks = {
        "hp": [
            "https://support.hp.com/us-en/help/computer/battery-adapter-issues",
            "https://www.hp.com/us-en/tech-takes/laptops/maintenance/hp-laptop-battery-life-tips.html",
            "https://www.hp.com/us-en/tech-takes/laptops/troubleshooting/how-to-fix-laptop-that-wont-charge.html",
        ]
    }

    return fallbacks.get(safe_text(brand).lower(), [])


def build_candidates(official_candidates, brand):
    selected = []
    seen = set()

    for url in get_source_fallbacks(brand):
        key = url.rstrip("/").lower()

        if key not in seen:
            selected.append({
                "url": url,
                "title": "Manufacturer support source",
                "snippet": "",
            })
            seen.add(key)

    for item in official_candidates:
        if not isinstance(item, dict):
            continue

        url = safe_text(item.get("url"))

        if not url:
            continue

        key = url.rstrip("/").lower()

        if key in seen:
            continue

        selected.append({
            "url": url,
            "title": safe_text(item.get("title")),
            "snippet": safe_text(item.get("snippet")),
        })
        seen.add(key)

        if len(selected) >= MAX_PAGES:
            break

    return selected[:MAX_PAGES]


def split_into_sentences(content):
    """
    Split page text while preserving the original sentence wording.
    """
    content = re.sub(r"\s+", " ", safe_text(content)).strip()

    if not content:
        return []

    # Split at sentence-ending punctuation, including when the
    # next sentence begins with a lowercase letter.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Za-z0-9])", content)

    return [
        part.strip()
        for part in parts
        if len(part.strip()) >= 35
    ]


def extract_explicit_actions(content, symptom):
    rules = ACTION_RULES.get(symptom, [])
    candidates = []

    for sentence in split_into_sentences(content):
        sentence_normalized = normalize_text(sentence)

        if len(sentence_normalized) > 700:
            continue

        for action_name, pattern in rules:
            if re.search(pattern, sentence_normalized, re.IGNORECASE):
                candidates.append({
                    "action_name": action_name,
                    "sentence": sentence,
                })
                break

    return candidates


def quote_is_verifiable(sentence, original_page):
    """
    Confirm that the extracted sentence occurs in the retrieved page.
    This verifies source wording, not model-specific applicability.
    """
    sentence_normalized = normalize_text(sentence)
    page_normalized = normalize_text(original_page)

    if len(sentence_normalized) < 35:
        return False

    return sentence_normalized in page_normalized


def build_recommendation_step(sentence):
    return sentence.strip()


def research_and_troubleshoot(brand, product, issue):
    brand = safe_text(brand)
    product = safe_text(product)
    issue = safe_text(issue)

    trace = [
        "Research agent started live manufacturer research.",
        f"Product: {brand} {product}",
        f"Reported issue: {issue}",
    ]

    requested_symptoms = detect_symptoms(issue)

    if not requested_symptoms:
        return insufficient_result(
            trace,
            "The reported issue could not be classified confidently.",
        )

    trace.append(
        "Recognised symptoms: " + ", ".join(sorted(requested_symptoms))
    )

    # 1. LIVE SEARCH
    try:
        search = resilient_web_search(
            brand=brand,
            product=product,
            issue=issue,
            max_results=8,
        )

        if not isinstance(search, dict):
            raise ValueError("Search returned an invalid response.")

        results = search.get("results", [])

        if not isinstance(results, list):
            results = []

    except Exception as error:
        trace.append(f"Live search failed: {type(error).__name__}: {error}")

        return insufficient_result(
            trace,
            "Live manufacturer research could not be completed.",
        )

    trace.append(f"Live search returned {len(results)} candidate results.")

    official_candidates = []

    for item in results:
        if not isinstance(item, dict):
            continue

        url = safe_text(item.get("url"))

        if not url:
            continue

        try:
            if is_official_domain(url, brand):
                official_candidates.append(item)
        except Exception as error:
            trace.append(f"Domain verification failed for {url}: {error}")

    issue_terms = set(re.findall(r"[a-zA-Z]{4,}", issue.lower()))

    def candidate_score(item):
        searchable = " ".join([
            safe_text(item.get("title")),
            safe_text(item.get("snippet")),
            safe_text(item.get("url")),
        ]).lower()

        return sum(term in searchable for term in issue_terms)

    official_candidates.sort(key=candidate_score, reverse=True)

    selected_candidates = build_candidates(official_candidates, brand)

    trace.append(
        f"Manufacturer candidates selected: {len(selected_candidates)}."
    )

    if not selected_candidates:
        return insufficient_result(
            trace,
            "No official manufacturer support pages were identified.",
        )

    # 2. RETRIEVE AND VERIFY MANUFACTURER PAGES
    evidence = []
    seen_urls = set()

    for item in selected_candidates:
        url = safe_text(item.get("url"))

        if not url:
            continue

        url_key = url.rstrip("/").lower()

        if url_key in seen_urls:
            continue

        seen_urls.add(url_key)

        try:
            # Verify fallback URLs as well as search-result URLs.
            if not is_official_domain(url, brand):
                trace.append(f"REJECTED non-official domain: {url}")
                continue

            page = read_webpage(url, brand=brand)

            if not isinstance(page, dict):
                trace.append(f"Invalid page response: {url}")
                continue

            if page.get("status") != "SUCCESS":
                trace.append(f"Page extraction failed: {url}")
                continue

            content = safe_text(page.get("content"))

            if len(content) < 100:
                trace.append(f"Page content too short: {url}")
                continue

            evidence.append({
                "url": url,
                "title": safe_text(item.get("title")),
                "source_class": safe_text(
                    page.get("source_class") or "UNSPECIFIED"
                ),
                "content": content[:MAX_CONTENT_CHARS],
            })

            trace.append(
                f"Retrieved manufacturer page: {url} "
                f"({len(content)} characters)."
            )

        except Exception as error:
            trace.append(
                f"Page retrieval error for {url}: "
                f"{type(error).__name__}: {error}"
            )

    source_list = [
        {
            "url": page["url"],
            "evidence_type": "FULL_PAGE",
            "source_class": page["source_class"],
        }
        for page in evidence
    ]

    if not evidence:
        return insufficient_result(
            trace,
            "Manufacturer pages could not be retrieved and verified.",
        )

    # 3. EXTRACT EXPLICIT, SYMPTOM-RELATED ACTIONS
    verified_steps = []
    step_evidence = []
    supported_symptoms = set()
    seen_steps = set()

    for symptom in sorted(requested_symptoms):
        symptom_candidates = []

        for page in evidence:
            actions = extract_explicit_actions(page["content"], symptom)

            for action in actions:
                sentence = action["sentence"]

                if not quote_is_verifiable(sentence, page["content"]):
                    trace.append(
                        "REJECTED: extracted sentence did not match retrieved page."
                    )
                    continue

                symptom_candidates.append({
                    "symptom": symptom,
                    "step": build_recommendation_step(sentence),
                    "action_name": action["action_name"],
                    "source_url": page["url"],
                    "evidence_quote": sentence,
                })

        accepted_for_symptom = False

        for candidate in symptom_candidates:
            normalized_step = normalize_text(candidate["step"])

            if normalized_step in seen_steps:
                accepted_for_symptom = True
                continue

            if len(verified_steps) >= MAX_STEPS:
                break

            verified_steps.append(candidate["step"])
            seen_steps.add(normalized_step)
            accepted_for_symptom = True

            step_evidence.append({
                "step": candidate["step"],
                "symptom": candidate["symptom"],
                "source_url": candidate["source_url"],
                "evidence_quote": candidate["evidence_quote"],
                "action_type": candidate["action_name"],
                "verification": "EXACT_SENTENCE_MATCH",
            })

            trace.append(
                "ACCEPTED: explicit manufacturer instruction matched | "
                + candidate["action_name"]
                + " | "
                + candidate["source_url"]
            )

        if accepted_for_symptom:
            supported_symptoms.add(symptom)

    unsupported_symptoms = requested_symptoms - supported_symptoms

    trace.append(
        "Symptoms with explicit manufacturer actions: "
        + (", ".join(sorted(supported_symptoms)) or "None")
    )

    trace.append(
        "Symptoms without explicit manufacturer actions: "
        + (", ".join(sorted(unsupported_symptoms)) or "None")
    )

    trace.append(f"Verified manufacturer instructions: {len(verified_steps)}.")

    # 4. FINAL RESPONSE
    if not verified_steps:
        return insufficient_result(
            trace,
            (
                "Manufacturer pages were retrieved, but no explicit "
                "troubleshooting instruction passed the action and "
                "source verification checks."
            ),
            warnings=[
                "No troubleshooting recommendation was generated.",
                "A component mention or general explanation is not treated as an instruction.",
                "The reported issue may require product-model-specific manufacturer assistance.",
            ],
            sources=source_list,
        )

    warnings = [
        "Instructions are quoted from retrieved manufacturer pages.",
        "The exact product model has not been confirmed.",
        "Exact sentence matching verifies source wording, not product-specific applicability.",
        "This system does not confirm warranty eligibility or diagnose hardware faults.",
    ]

    if unsupported_symptoms:
        warnings.append(
            "No explicit manufacturer action was identified for: "
            + ", ".join(sorted(unsupported_symptoms))
        )

    trace.append(
        "Research completed. Recommendations were extracted from "
        "manufacturer text and checked against the retrieved pages."
    )

    return {
        "status": "SUCCESS",
        "recommendation": {
            "summary": (
                "Explicit manufacturer instructions were found for "
                "at least one reported symptom."
            ),
            "safe_steps": verified_steps,
            "step_evidence": step_evidence,
            "supported_symptoms": sorted(supported_symptoms),
            "unsupported_symptoms": sorted(unsupported_symptoms),
            "warnings": warnings,
            "confidence": "LOW",
            "next_action": (
                "Follow only the displayed manufacturer instructions. "
                "If the issue continues, contact the manufacturer's "
                "authorised support service."
            ),
        },
        "sources": source_list,
        "execution_trace": trace,
    }
