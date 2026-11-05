
from ddgs import DDGS
from urllib.parse import urlparse
import json
import re


def live_web_search(query, max_results=5, official_only=False, brand=None):
    """
    Search the live internet and return structured search results.

    Search results are candidates only. They are not treated as
    verified manufacturer evidence.
    """
    search_query = query

    if official_only and brand:
        search_query = f"{brand} official support {query}"

    try:
        results = DDGS().text(
            search_query,
            max_results=max_results
        )

        verified_results = []

        for result in results or []:
            url = result.get("href", "").strip()

            if not url.startswith("https://"):
                continue

            parsed = urlparse(url)

            if not parsed.netloc:
                continue

            verified_results.append({
                "title": result.get("title", ""),
                "url": url,
                "domain": parsed.netloc.lower(),
                "snippet": result.get("body", ""),
                "source_type": "LIVE_WEB_SEARCH",
                "official_status": "NOT_VERIFIED",
                "search_query": search_query
            })

        return {
            "status": "SUCCESS" if verified_results else "NO_RESULTS",
            "query": search_query,
            "results": verified_results
        }

    except Exception as error:
        return {
            "status": "SEARCH_FAILED",
            "query": search_query,
            "error": str(error),
            "results": []
        }


def build_search_queries(brand, product, issue):
    """
    Build complementary searches for the same reported problem.
    Queries remain specific to the supplied product and symptoms.
    """
    brand = str(brand).strip()
    product = str(product).strip()
    issue = re.sub(r"\s+", " ", str(issue)).strip()

    return [
        f'"{brand}" "{product}" {issue} official support',
        f'{brand} {product} {issue} troubleshooting',
        f'{brand} official support {issue}',
        f'{brand} {product} user manual troubleshooting {issue}',
    ]


def resilient_web_search(brand, product, issue, max_results=5):
    """
    Run multiple live searches, combine results and remove duplicates.

    The returned results are unverified candidates. Manufacturer-domain
    verification and webpage extraction happen in separate tools.
    """
    queries = build_search_queries(
        brand=brand,
        product=product,
        issue=issue
    )

    attempts = []
    collected = []
    seen_urls = set()

    # Each query gets its own result allowance.
    per_query_limit = max(3, max_results)

    for query in queries:
        response = live_web_search(
            query=query,
            max_results=per_query_limit
        )

        attempts.append({
            "query": query,
            "status": response.get("status", "UNKNOWN"),
            "results_found": len(response.get("results", [])),
            "error": response.get("error")
        })

        for item in response.get("results", []):
            url = item.get("url", "").rstrip("/")

            if not url or url in seen_urls:
                continue

            item["url"] = url
            collected.append(item)
            seen_urls.add(url)

    return {
        "status": "SUCCESS" if collected else "ALL_SEARCHES_FAILED",
        "results": collected,
        "search_attempts": attempts,
        "total_results": len(collected),
        "unique_results": len(collected)
    }


if __name__ == "__main__":
    response = resilient_web_search(
        brand="HP",
        product="HP Laptop",
        issue="battery drains quickly and laptop becomes warm while charging",
        max_results=5
    )

    print(json.dumps(
        response,
        indent=2,
        ensure_ascii=False
    ))
