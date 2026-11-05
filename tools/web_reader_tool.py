
import requests
import trafilatura
from urllib.parse import urlparse


TRUSTED_DOMAINS = {
    "lg": ["lg.com"],
    "samsung": ["samsung.com"],
    "hp": ["hp.com"],
    "dell": ["dell.com"],
    "lenovo": ["lenovo.com"],
    "sony": ["sony.com"],
    "whirlpool": ["whirlpool.com", "whirlpoolindia.com"],
    "bajaj": ["bajajelectricals.com"],
}

COMMUNITY_HOST_MARKERS = (
    "community",
    "forum",
    "forums",
    "discussions",
)


def get_source_class(url, brand):
    """
    Classify a URL by manufacturer domain and host type.

    Community pages are not accepted as authoritative
    manufacturer documentation.
    """
    hostname = (urlparse(url).hostname or "").lower()
    brand = str(brand or "").lower().strip()

    allowed = TRUSTED_DOMAINS.get(brand, [])

    if not any(
        hostname == domain or hostname.endswith("." + domain)
        for domain in allowed
    ):
        return "THIRD_PARTY"

    labels = hostname.split(".")

    if any(
        marker in label
        for label in labels
        for marker in COMMUNITY_HOST_MARKERS
    ):
        return "MANUFACTURER_COMMUNITY"

    if brand == "hp" and hostname.startswith("h30434."):
        return "MANUFACTURER_COMMUNITY"

    if (
        hostname.startswith("support.")
        or ".support." in hostname
    ):
        return "OFFICIAL_SUPPORT"

    return "MANUFACTURER_PUBLISHED"


def is_official_domain(url, brand):
    """
    True only for manufacturer-owned domains.

    Community pages are classified separately and must not
    be used as authoritative repair evidence.
    """
    return get_source_class(url, brand) in {
        "OFFICIAL_SUPPORT",
        "MANUFACTURER_PUBLISHED",
    }


def read_webpage(url, brand=None):
    """
    Retrieve and extract readable webpage content.

    Only HTTPS manufacturer-owned, non-community pages
    are accepted when a brand is supplied.
    """
    try:
        parsed = urlparse(url)

        if parsed.scheme != "https" or not parsed.hostname:
            return {
                "status": "BLOCKED",
                "url": url,
                "reason": "Only valid HTTPS URLs are accepted."
            }

        if brand:
            source_class = get_source_class(url, brand)

            if source_class == "MANUFACTURER_COMMUNITY":
                return {
                    "status": "UNVERIFIED_SOURCE",
                    "url": url,
                    "source_class": source_class,
                    "reason": (
                        "Community discussions are not treated "
                        "as authoritative manufacturer documentation."
                    )
                }

            if source_class == "THIRD_PARTY":
                return {
                    "status": "UNVERIFIED_SOURCE",
                    "url": url,
                    "source_class": source_class,
                    "reason": "Domain is not in the trusted manufacturer list."
                }

        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 WarrantyResearchDemo/1.0"
                )
            },
            allow_redirects=True
        )

        response.raise_for_status()

        final_url = response.url

        if brand and not is_official_domain(final_url, brand):
            return {
                "status": "UNVERIFIED_REDIRECT",
                "url": url,
                "final_url": final_url,
                "reason": (
                    "The page redirected outside the accepted "
                    "manufacturer documentation domain."
                )
            }

        if "text/html" not in response.headers.get(
            "Content-Type", ""
        ).lower():
            return {
                "status": "UNSUPPORTED_CONTENT",
                "url": final_url,
                "reason": "The response is not an HTML webpage."
            }

        content = trafilatura.extract(
            response.text,
            include_links=False,
            include_tables=True,
            favor_recall=True
        )

        if not content or len(content.strip()) < 100:
            return {
                "status": "EXTRACTION_FAILED",
                "url": final_url,
                "reason": "Insufficient readable webpage content."
            }

        metadata = trafilatura.extract_metadata(response.text)

        title = (
            metadata.title
            if metadata and metadata.title
            else ""
        )

        source_class = (
            get_source_class(final_url, brand)
            if brand else "UNCLASSIFIED"
        )

        return {
            "status": "SUCCESS",
            "url": final_url,
            "brand": brand,
            "title": title,
            "source_class": source_class,
            "official_domain": bool(
                brand and is_official_domain(final_url, brand)
            ),
            "content": content[:12000],
            "characters_extracted": len(content)
        }

    except requests.RequestException as error:
        return {
            "status": "FETCH_FAILED",
            "url": url,
            "error": str(error)
        }

    except Exception as error:
        return {
            "status": "ERROR",
            "url": url,
            "error": str(error)
        }


def retrieve_with_fallback(url, brand, issue):
    """
    Try direct official webpage extraction.
    If unavailable, search again but keep snippets unverified.
    """
    from tools.web_search_tool import live_web_search

    result = read_webpage(url, brand=brand)

    if result["status"] == "SUCCESS":
        return {
            "status": "VERIFIED_CONTENT",
            "method": "DIRECT_WEBPAGE",
            "evidence": result,
            "execution_trace": [
                "Official manufacturer webpage retrieved.",
                "Page content extracted successfully."
            ]
        }

    query = f"{brand} official support {issue}"

    fallback = live_web_search(
        query,
        max_results=5
    )

    official_results = [
        item for item in fallback.get("results", [])
        if is_official_domain(item.get("url", ""), brand)
    ]

    return {
        "status": (
            "SEARCH_SNIPPETS_ONLY"
            if official_results else "NO_VERIFIED_EVIDENCE"
        ),
        "method": "LIVE_SEARCH_FALLBACK",
        "evidence": official_results,
        "execution_trace": [
            f"Direct retrieval result: {result['status']}",
            "Performed a fresh live search.",
            f"Found {len(official_results)} official-domain candidates.",
            "Search snippets are not accepted as repair evidence."
        ]
    }


if __name__ == "__main__":
    test_urls = [
        "https://support.hp.com/us-en/help/computer/battery-adapter-issues",
        "https://www.hp.com/us-en/tech-takes/laptops/maintenance/hp-laptop-battery-life-tips.html",
        "https://h30434.www3.hp.com/t5/Notebook-Hardware-and-Upgrade-Questions/"
    ]

    for test_url in test_urls:
        print(
            test_url,
            "=>",
            get_source_class(test_url, "hp")
        )
