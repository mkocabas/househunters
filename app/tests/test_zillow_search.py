"""
Test script for Zillow search API.
Run with: python test_zillow_search.py <zillow_url>
"""
import json
import sys

sys.path.insert(0, "..")
from zillow import parse_bounds_from_url, search_properties


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_zillow_search.py <zillow_url>")
        print("Example: python test_zillow_search.py 'https://www.zillow.com/san-francisco-ca/?searchQueryState=...'")
        sys.exit(1)

    zillow_url = sys.argv[1]

    # Parse bounds from URL
    bounds = parse_bounds_from_url(zillow_url)
    if not bounds:
        print("Error: Could not parse bounds from URL")
        sys.exit(1)

    # Determine search type from URL
    search_type = "rent" if "/rentals" in zillow_url or "isForRent" in zillow_url or "for_rent" in zillow_url else "sale"
    print(f"Search type: {search_type}")
    # Search with no filters to get raw results
    results = search_properties(bounds, filters={"min_beds": 4, "min_baths": 2}, search_type=search_type)
    mapResults = results['mapResults']
    listResults = results['listResults']

    # Output raw JSON
    # print(json.dumps(results, indent=2))
    print(f'Number of map results={len(mapResults)}')
    print(f'Number of list results={len(listResults)}')
    # print(f'Number of listings found: {len(results)}')

    print("======== detail urls ========")
    for n, lr in enumerate(listResults):
        print(f'{n}\t{lr["detailUrl"]}')
    print("=============================")
    print("")

    import ipdb; ipdb.set_trace()


if __name__ == "__main__":
    main()
