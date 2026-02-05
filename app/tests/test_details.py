"""
Test script for property details fetcher.
Run with: python test_details.py
"""
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

from details import get_property_details_by_zpid

# Test zpids provided by user
TEST_ZPIDS = [19822606, 124744775, 19828734]


def test_property_with_schools(zpid: int) -> dict | None:
    """Test fetching property details by zpid, focusing on school data."""
    print(f"\n{'='*60}")
    print(f"Fetching details for zpid: {zpid}")
    print("=" * 60)

    try:
        details = get_property_details_by_zpid(zpid)

        if not details:
            print("No data returned")
            return None

        print(f"Success! Retrieved {len(details)} fields")

        # Extract address
        address = details.get("address", {})
        full_address = f"{address.get('streetAddress', '')}, {address.get('city', '')}, {address.get('state', '')} {address.get('zipcode', '')}"

        print(f"\nAddress: {full_address}")
        price = details.get("price")
        print(f"Price: ${price:,}" if price else "Price: N/A")
        print(f"Beds: {details.get('bedrooms', 'N/A')}, Baths: {details.get('bathrooms', 'N/A')}")
        print(f"Year Built: {details.get('yearBuilt', 'N/A')}")

        # School information - this is key!
        schools = details.get("schools", [])
        print(f"\n--- Schools ({len(schools)} found) ---")

        if schools:
            for school in schools:
                name = school.get("name", "Unknown")
                rating = school.get("rating", "N/A")
                level = school.get("level", "Unknown")
                grades = school.get("grades", "")
                distance = school.get("distance", "N/A")
                link = school.get("link", "")
                print(f"  [{rating}/10] {name}")
                print(f"          Level: {level}, Grades: {grades}, Distance: {distance} mi")
        else:
            print("  No school data found in response")
            # Check if schools might be under a different key
            print("\n  Checking for school-related keys in response...")
            for key in details.keys():
                if "school" in key.lower():
                    print(f"    Found key: {key} = {details[key]}")

        return details

    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("\n" + "=" * 60)
    print("Property Details Fetcher - School Ratings Test")
    print("=" * 60)

    results = []

    for zpid in TEST_ZPIDS:
        details = test_property_with_schools(zpid)
        results.append((zpid, details is not None))

    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    for zpid, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  zpid {zpid}: {status}")

    all_passed = all(r[1] for r in results)
    print(f"\nOverall: {'All tests passed!' if all_passed else 'Some tests failed'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
