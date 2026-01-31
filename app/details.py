"""
Property details fetcher using Scraper API.
Fetches detailed property information from Zillow using property ID or URL.
"""
import json
import logging
import os
import re
from html import unescape
from json import loads
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Configuration
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY")
if not SCRAPER_API_KEY:
    logger.warning("SCRAPER_API_KEY environment variable not set - school ratings will fail")
SCRAPER_API_URL = "https://api.scraperapi.com/"
REQUEST_TIMEOUT = 60

# Cache configuration
CACHE_FILE = Path(__file__).parent / "data" / "school_cache.json"

# Regex for cleaning whitespace
REGEX_SPACE = re.compile(r"[\s ]+")


def _remove_space(value: str) -> str:
    """Remove unwanted spaces in given string."""
    return REGEX_SPACE.sub(" ", value.strip())


def _load_cache() -> dict:
    """Load the school ratings cache from disk."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load cache: {e}")
    return {}


def _save_cache(cache: dict) -> None:
    """Save the school ratings cache to disk."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save cache: {e}")


def _get_nested_value(dic: dict, key_path: str, default=None) -> Any:
    """Get a nested value from a dictionary using dot notation."""
    keys = key_path.split(".")
    current = dic
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, {})
        else:
            return default
        if current == {} or current is None:
            return default
    return current


def _make_scraperapi_request(target_url: str) -> requests.Response:
    """Makes a request to the target URL via ScraperAPI."""
    payload = {
        "api_key": SCRAPER_API_KEY,
        "url": target_url,
    }

    try:
        response = requests.get(SCRAPER_API_URL, params=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        status_code = e.response.status_code if e.response is not None else "N/A"
        response_text = e.response.text[:200] if e.response is not None else "N/A"
        logger.error(f"Error fetching {target_url} via ScraperAPI. Status Code: {status_code}")
        logger.error(f"Exception Type: {type(e).__name__}")
        logger.error(f"Response Body (first 200 chars): {response_text}")
        raise


def _parse_html_for_json(body: bytes) -> dict[str, Any]:
    """Parse HTML content to retrieve JSON data from __NEXT_DATA__ script tag."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("beautifulsoup4 is required. Install with: pip install beautifulsoup4")

    soup = BeautifulSoup(body, "html.parser")
    selection = soup.select_one("#__NEXT_DATA__")

    if not selection:
        logger.error("Could not find __NEXT_DATA__ script tag in HTML")
        return {}

    html_data = selection.getText()
    html_data = _remove_space(unescape(html_data))
    data = loads(html_data)

    return _get_nested_value(data, "props.pageProps.componentProps", {})


def _parse_property_data(body: bytes) -> dict[str, Any]:
    """Parse HTML content to extract property data."""
    component_props = _parse_html_for_json(body)

    if not component_props:
        return {}

    # Extract property data from gdpClientCache
    gdp_cache_raw = _get_nested_value(component_props, "gdpClientCache")
    if not gdp_cache_raw:
        logger.error("Could not find gdpClientCache in component props")
        return {}

    try:
        property_json = loads(gdp_cache_raw)
    except (TypeError, ValueError) as e:
        logger.error(f"Failed to parse gdpClientCache JSON: {e}")
        return {}

    # Find property data in the parsed JSON
    parsed_data = {}
    for data in property_json.values():
        if isinstance(data, dict) and "property" in data:
            parsed_data = data.get("property", {})
            break

    return parsed_data


def get_property_details_by_zpid(zpid: int | str) -> dict[str, Any]:
    """
    Fetch detailed property information by Zillow Property ID (zpid).
    Results are cached to avoid expensive API calls.

    Args:
        zpid: Zillow property ID (can be int or string)

    Returns:
        Dictionary containing detailed property information including:
        - Basic info: address, price, beds, baths, area
        - Extended info: year built, lot size, HOA, school ratings
        - Media: images, 3D tours, videos
        - Market data: zestimate, rent estimate, days on Zillow
    """
    zpid_str = str(zpid)

    # Check cache first
    cache = _load_cache()
    if zpid_str in cache:
        logger.info(f"Cache hit for zpid: {zpid_str}")
        return cache[zpid_str]

    # Fetch from API
    logger.info(f"Cache miss for zpid: {zpid_str}, fetching from API")
    home_url = f"https://www.zillow.com/homedetails/property/{zpid_str}_zpid/"
    details = get_property_details_by_url(home_url)

    # Save to cache
    if details:
        cache[zpid_str] = details
        _save_cache(cache)

    return details


def get_property_details_by_url(home_url: str) -> dict[str, Any]:
    """
    Fetch detailed property information by Zillow URL.

    Args:
        home_url: Full Zillow property URL

    Returns:
        Dictionary containing detailed property information
    """
    logger.info(f"Fetching property details from: {home_url}")
    response = _make_scraperapi_request(home_url)
    data = _parse_property_data(response.content)
    return data


def extract_summary_from_details(details: dict[str, Any]) -> dict[str, Any]:
    """
    Extract a summary of key fields from the full property details.

    Args:
        details: Full property details dictionary

    Returns:
        Dictionary with commonly needed fields
    """
    if not details:
        return {}

    # Extract address components
    address = _get_nested_value(details, "address", {})

    return {
        "zpid": details.get("zpid"),
        "url": details.get("url"),
        "status": details.get("homeStatus"),
        "price": details.get("price"),
        "zestimate": details.get("zestimate"),
        "rent_zestimate": details.get("rentZestimate"),
        "address": {
            "street": address.get("streetAddress"),
            "city": address.get("city"),
            "state": address.get("state"),
            "zipcode": address.get("zipcode"),
            "full": f"{address.get('streetAddress', '')}, {address.get('city', '')}, {address.get('state', '')} {address.get('zipcode', '')}",
        },
        "beds": details.get("bedrooms"),
        "baths": details.get("bathrooms"),
        "area": details.get("livingArea"),
        "lot_size": details.get("lotSize"),
        "year_built": details.get("yearBuilt"),
        "home_type": details.get("homeType"),
        "days_on_zillow": details.get("daysOnZillow"),
        "monthly_hoa": details.get("monthlyHoaFee"),
        "tax_assessed_value": details.get("taxAssessedValue"),
        "schools": details.get("schools", []),
        "description": details.get("description"),
        "photos": [p.get("url") for p in details.get("photos", [])[:5]] if details.get("photos") else [],
        "latitude": _get_nested_value(details, "latitude"),
        "longitude": _get_nested_value(details, "longitude"),
    }


# Async wrapper for FastAPI
async def get_property_details_by_zpid_async(zpid: int | str) -> dict[str, Any]:
    """Async wrapper for get_property_details_by_zpid."""
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: get_property_details_by_zpid(zpid))


async def get_property_details_by_url_async(home_url: str) -> dict[str, Any]:
    """Async wrapper for get_property_details_by_url."""
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: get_property_details_by_url(home_url))
