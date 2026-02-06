"""
Property details fetcher using Bright Data Web Unlocker.
Fetches detailed property information from Zillow using property ID or URL.
"""
import atexit
import json
import logging
import os
import re
import threading
from html import unescape
from json import loads
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv
import urllib3

# Suppress SSL warnings for Bright Data proxy
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

# Configuration - Bright Data Web Unlocker
BRIGHTDATA_HOST = os.environ.get("BRIGHTDATA_HOST", "brd.superproxy.io")
BRIGHTDATA_PORT = int(os.environ.get("BRIGHTDATA_PORT", "33335"))
BRIGHTDATA_USERNAME = os.environ.get("BRIGHTDATA_USERNAME")
BRIGHTDATA_PASSWORD = os.environ.get("BRIGHTDATA_PASSWORD")

if not BRIGHTDATA_USERNAME or not BRIGHTDATA_PASSWORD:
    logger.warning("BRIGHTDATA_USERNAME or BRIGHTDATA_PASSWORD not set - school ratings will fail")

REQUEST_TIMEOUT = 60

# Cache configuration - thread-safe in-memory cache with disk persistence
CACHE_FILE = Path(__file__).parent / "data" / "school_cache.json"
_cache: dict = {}
_cache_lock = threading.Lock()
_cache_dirty = False  # Track if cache needs to be saved

# Regex for cleaning whitespace
REGEX_SPACE = re.compile(r"[\s ]+")


def _remove_space(value: str) -> str:
    """Remove unwanted spaces in given string."""
    return REGEX_SPACE.sub(" ", value.strip())


def _init_cache() -> None:
    """Initialize the in-memory cache from disk (called once at module load)."""
    global _cache
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                _cache = json.load(f)
            logger.info(f"Loaded {len(_cache)} entries from school cache")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load cache: {e}")
            _cache = {}
    else:
        _cache = {}


def _save_cache_to_disk() -> None:
    """Save the in-memory cache to disk (thread-safe)."""
    global _cache_dirty
    with _cache_lock:
        if not _cache_dirty:
            return
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w") as f:
                json.dump(_cache, f, indent=2)
            _cache_dirty = False
            logger.info(f"Saved {len(_cache)} entries to school cache")
        except IOError as e:
            logger.error(f"Failed to save cache: {e}")


def _cache_get(zpid: str) -> dict | None:
    """Thread-safe cache lookup."""
    with _cache_lock:
        return _cache.get(zpid)


def _cache_set(zpid: str, data: dict) -> None:
    """Thread-safe cache insert."""
    global _cache_dirty
    with _cache_lock:
        _cache[zpid] = data
        _cache_dirty = True


def save_school_cache() -> None:
    """Public function to force save the cache to disk."""
    _save_cache_to_disk()


# Initialize cache at module load
_init_cache()

# Save cache when the process exits
atexit.register(_save_cache_to_disk)


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


def _make_brightdata_request(target_url: str) -> requests.Response:
    """Makes a request to the target URL via Bright Data Web Unlocker proxy."""
    if not BRIGHTDATA_USERNAME or not BRIGHTDATA_PASSWORD:
        raise RuntimeError("Bright Data credentials not configured")

    # Encode password in case it contains special characters
    encoded_password = quote(BRIGHTDATA_PASSWORD, safe='')
    proxy_url = f"http://{BRIGHTDATA_USERNAME}:{encoded_password}@{BRIGHTDATA_HOST}:{BRIGHTDATA_PORT}"
    proxies = {"http": proxy_url, "https": proxy_url}

    try:
        response = requests.get(
            target_url,
            proxies=proxies,
            verify=False,  # Bright Data may require this for SSL
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        status_code = e.response.status_code if e.response is not None else "N/A"
        response_text = e.response.text[:200] if e.response is not None else "N/A"
        logger.error(f"Error fetching {target_url} via Bright Data. Status Code: {status_code}")
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

    # Check cache first (thread-safe)
    cached = _cache_get(zpid_str)
    if cached is not None:
        logger.info(f"Cache hit for zpid: {zpid_str}")
        return cached

    # Fetch from API
    logger.info(f"Cache miss for zpid: {zpid_str}, fetching from API")
    home_url = f"https://www.zillow.com/homedetails/property/{zpid_str}_zpid/"
    details = get_property_details_by_url(home_url)

    # Save to cache (thread-safe)
    if details:
        _cache_set(zpid_str, details)

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
    response = _make_brightdata_request(home_url)
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
