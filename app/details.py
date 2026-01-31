"""
Property details fetcher using Scraper API.
Fetches detailed property information from Zillow using property ID or URL.
"""
import logging
import os
import re
from html import unescape
from json import loads
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Configuration
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "REDACTED_API_KEY")
SCRAPER_API_URL = "https://api.scraperapi.com/"
REQUEST_TIMEOUT = 60

# Regex for cleaning whitespace
REGEX_SPACE = re.compile(r"[\s ]+")


def _remove_space(value: str) -> str:
    """Remove unwanted spaces in given string."""
    return REGEX_SPACE.sub(" ", value.strip())


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

    Args:
        zpid: Zillow property ID (can be int or string)

    Returns:
        Dictionary containing detailed property information including:
        - Basic info: address, price, beds, baths, area
        - Extended info: year built, lot size, HOA, school ratings
        - Media: images, 3D tours, videos
        - Market data: zestimate, rent estimate, days on Zillow
    """
    zpid = str(zpid)
    home_url = f"https://www.zillow.com/homedetails/property/{zpid}_zpid/"
    return get_property_details_by_url(home_url)


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
