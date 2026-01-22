"""
Zillow API wrapper using curl_cffi for browser impersonation.
"""
import json
import re
import logging
from typing import Any
from urllib.parse import unquote

from curl_cffi.requests import Session

logger = logging.getLogger(__name__)

ZILLOW_SEARCH_URL = "https://www.zillow.com/async-create-search-page-state"


def parse_bounds_from_url(zillow_url: str) -> dict[str, Any] | None:
    """
    Extract map bounds from a Zillow search URL.

    Args:
        zillow_url: A Zillow search URL containing searchQueryState

    Returns:
        Dictionary with ne_lat, ne_long, sw_lat, sw_long, zoom_value, custom_region_id
        or None if parsing fails
    """
    try:
        # Look for searchQueryState in the URL
        match = re.search(r'searchQueryState=([^&]+)', zillow_url)
        if not match:
            # Try to find it in a different format (embedded in path)
            match = re.search(r'searchQueryState%22%3A(%7B.+?%7D)(?:&|$)', zillow_url)
            if not match:
                logger.error("Could not find searchQueryState in URL")
                return None

        encoded_state = match.group(1)
        decoded_state = unquote(encoded_state)
        query_state = json.loads(decoded_state)

        map_bounds = query_state.get("mapBounds", {})

        return {
            "ne_lat": map_bounds.get("north"),
            "ne_long": map_bounds.get("east"),
            "sw_lat": map_bounds.get("south"),
            "sw_long": map_bounds.get("west"),
            "zoom_value": query_state.get("mapZoom", 12),
            "custom_region_id": query_state.get("customRegionId"),
            "original_url": zillow_url,
        }
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse Zillow URL: {e}")
        return None


def search_properties(
    bounds: dict[str, float],
    filters: dict[str, Any],
    search_type: str = "sale",
) -> dict[str, Any]:
    """
    Search Zillow properties using curl_cffi with browser impersonation.

    Args:
        bounds: Dictionary with ne_lat, ne_long, sw_lat, sw_long, zoom_value
        filters: Dictionary with beds, baths, price, year_built, property_types
        search_type: "sale" or "rent"

    Returns:
        Dictionary with mapResults and listResults
    """
    # Build filter state based on search type
    if search_type == "rent":
        filter_state = {
            "sortSelection": {"value": "priorityscore"},
            "isNewConstruction": {"value": False},
            "isForSaleForeclosure": {"value": False},
            "isForSaleByOwner": {"value": False},
            "isForSaleByAgent": {"value": False},
            "isForRent": {"value": True},
            "isComingSoon": {"value": False},
            "isAuction": {"value": False},
            "isAllHomes": {"value": True},
        }
    else:  # sale
        filter_state = {
            "sortSelection": {"value": "globalrelevanceex"},
            "isAllHomes": {"value": True},
        }

    # Add beds filter
    if filters.get("min_beds") is not None or filters.get("max_beds") is not None:
        beds = {}
        if filters.get("min_beds") is not None:
            beds["min"] = filters["min_beds"]
        if filters.get("max_beds") is not None:
            beds["max"] = filters["max_beds"]
        filter_state["beds"] = beds

    # Add baths filter
    if filters.get("min_baths") is not None or filters.get("max_baths") is not None:
        baths = {}
        if filters.get("min_baths") is not None:
            baths["min"] = filters["min_baths"]
        if filters.get("max_baths") is not None:
            baths["max"] = filters["max_baths"]
        filter_state["baths"] = baths

    # Add price filter
    if filters.get("min_price") is not None or filters.get("max_price") is not None:
        price = {}
        if filters.get("min_price") is not None:
            price["min"] = filters["min_price"]
        if filters.get("max_price") is not None:
            price["max"] = filters["max_price"]
        filter_state["price"] = price
        # For rentals, also set monthlyPayment filter
        if search_type == "rent":
            filter_state["monthlyPayment"] = price

    # Add year built filter
    if filters.get("min_year") is not None or filters.get("max_year") is not None:
        year_built = {}
        if filters.get("min_year") is not None:
            year_built["min"] = filters["min_year"]
        if filters.get("max_year") is not None:
            year_built["max"] = filters["max_year"]
        filter_state["built"] = year_built

    # Add property type filters
    property_types = filters.get("property_types", {})
    for prop_type, include in property_types.items():
        if prop_type in ["sf", "tow", "mf", "con", "land", "apa", "manu", "apco"]:
            filter_state[prop_type] = {"value": include}

    # Build request payload
    input_data = {
        "searchQueryState": {
            "isMapVisible": True,
            "isListVisible": True,
            "mapBounds": {
                "north": bounds["ne_lat"],
                "east": bounds["ne_long"],
                "south": bounds["sw_lat"],
                "west": bounds["sw_long"],
            },
            "filterState": filter_state,
            "mapZoom": bounds.get("zoom_value", 12),
            "pagination": {"currentPage": 1},
        },
        "wants": {
            "cat1": ["listResults", "mapResults"],
            "cat2": ["total"],
        },
        "requestId": 10,
        "isDebugRequest": False,
    }

    # Add custom region ID if provided
    if bounds.get("custom_region_id"):
        input_data["searchQueryState"]["customRegionId"] = bounds["custom_region_id"]

    # Use a session to maintain cookies
    with Session(impersonate="chrome") as session:
        # First, visit the original Zillow page to get cookies
        original_url = bounds.get("original_url", "https://www.zillow.com/homes/")

        try:
            # Initial page visit to get cookies
            session.get(
                original_url,
                timeout=30,
            )
        except Exception as e:
            logger.warning(f"Initial page visit failed: {e}")

        # Now make the API request with the session cookies
        headers = {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "Origin": "https://www.zillow.com",
            "Referer": original_url,
        }

        response = session.put(
            url=ZILLOW_SEARCH_URL,
            json=input_data,
            headers=headers,
            timeout=60,
        )

        response.raise_for_status()
        data = response.json()

        return data.get("cat1", {}).get("searchResults", {})


# Async wrapper for FastAPI
async def search_properties_async(
    bounds: dict[str, float],
    filters: dict[str, Any],
    search_type: str = "sale",
) -> dict[str, Any]:
    """Async wrapper that runs the sync search in a thread pool."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: search_properties(bounds, filters, search_type)
    )
