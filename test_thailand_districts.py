"""
Test script to demonstrate getting Thailand districts with names and bboxes.

This script shows how to:
1. Query all Thailand districts from Overpass API
2. Extract district names and bounding boxes
3. Generate a CSV file with district information for batch analysis
"""

import requests
import json
import pandas as pd
from pathlib import Path


def get_thailand_districts(admin_level=6, timeout=60):
    """
    Get all districts in Thailand from Overpass API.

    Args:
        admin_level: Administrative level to query
                     6 = Districts (Amphoe) - ~928 districts
                     4 = Provinces (Changwat) - 77 provinces
                     8 = Sub-districts (Tambon) - thousands
        timeout: Query timeout in seconds

    Returns:
        List of dicts with district information
    """
    print(f"Querying Overpass API for Thailand admin_level={admin_level}...")

    # Overpass query to get all districts in Thailand
    # We request bbox output which gives us the bounding box
    overpass_query = f"""
    [out:json][timeout:{timeout}];
    area["ISO3166-1"="TH"][admin_level=2];
    (
      relation["admin_level"="{admin_level}"](area);
    );
    out center tags bb;
    """

    url = "https://overpass-api.de/api/interpreter"

    try:
        response = requests.post(
            url,
            data={'data': overpass_query},
            timeout=timeout + 10
        )

        if response.status_code == 200:
            data = response.json()
            elements = data.get('elements', [])

            print(f"Found {len(elements)} administrative regions")

            districts = []
            for el in elements:
                tags = el.get('tags', {})
                center = el.get('center', {})
                bounds = el.get('bounds', {})

                # Extract names (prefer English, fall back to local name)
                name_en = tags.get('name:en', '')
                name_local = tags.get('name', '')
                name = name_en or name_local

                # Get bounding box in ohsome API format: "min_lon,min_lat,max_lon,max_lat"
                if bounds:
                    bbox = f"{bounds['minlon']},{bounds['minlat']},{bounds['maxlon']},{bounds['maxlat']}"
                else:
                    # If no bbox, create one from center (not ideal but better than nothing)
                    lat = center.get('lat', 0)
                    lon = center.get('lon', 0)
                    buffer = 0.1  # ~11km buffer
                    bbox = f"{lon-buffer},{lat-buffer},{lon+buffer},{lat+buffer}"

                district_info = {
                    'osm_id': el.get('id'),
                    'name': name,
                    'name_en': name_en,
                    'name_local': name_local,
                    'bbox': bbox,
                    'center_lat': center.get('lat', 0),
                    'center_lon': center.get('lon', 0),
                    'admin_level': admin_level,
                    'type': tags.get('type', ''),
                    'ref': tags.get('ref', '')  # Often contains district code
                }

                districts.append(district_info)

            return districts

        else:
            print(f"ERROR: Overpass API request failed with status {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return None

    except Exception as e:
        print(f"ERROR: Error querying Overpass API: {str(e)}")
        return None


def save_districts_to_csv(districts, output_file):
    """
    Save districts data to CSV file.

    Args:
        districts: List of district dicts
        output_file: Path to output CSV file
    """
    df = pd.DataFrame(districts)

    # Reorder columns for better readability
    column_order = ['name', 'name_en', 'name_local', 'bbox', 'center_lat', 'center_lon',
                   'osm_id', 'admin_level', 'ref', 'type']
    df = df[[col for col in column_order if col in df.columns]]

    # Create output directory if it doesn't exist
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save to CSV
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\nSaved {len(districts)} districts to: {output_file}")

    return df


def demonstrate_usage():
    """
    Demonstrate how to get Thailand districts and save to CSV.
    """
    print("=" * 80)
    print("THAILAND DISTRICTS - OVERPASS API DEMO")
    print("=" * 80)

    # Get districts (admin_level=6)
    print("\n1. Fetching all Thailand districts (admin_level=6)...")
    districts = get_thailand_districts(admin_level=6)

    if districts:
        print(f"\n2. Retrieved {len(districts)} districts")

        # Show first 5 examples
        print("\nFirst 5 districts:")
        for i, district in enumerate(districts[:5], 1):
            print(f"{i}. {district['name']}")
            print(f"   Bbox: {district['bbox']}")
            print(f"   Center: {district['center_lat']}, {district['center_lon']}")

        # Save to CSV
        print("\n3. Saving to CSV...")
        output_file = "countries_polygons/thailand_districts.csv"
        df = save_districts_to_csv(districts, output_file)

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total districts: {len(districts)}")
        print(f"Output file: {output_file}")
        print("\nYou can now use this CSV for batch analysis!")
        print("\nExample usage in your config:")
        print("  countries:")
        print("    source: csv")
        print("    csv_path: countries_polygons/thailand_districts.csv")
        print("    name_column: name")
        print("    bbox_column: bbox")

        return df
    else:
        print("\nERROR: Failed to retrieve districts")
        return None


def get_country_bbox():
    """
    Get the full Thailand country bounding box for comparison.
    """
    print("\nGetting full Thailand country bbox...")
    overpass_query = """
    [out:json][timeout:25];
    area["ISO3166-1"="TH"][admin_level=2];
    relation(area);
    out bb;
    """

    url = "https://overpass-api.de/api/interpreter"

    try:
        response = requests.post(url, data={'data': overpass_query}, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data['elements']:
                bounds = data['elements'][0].get('bounds', {})
                bbox = f"{bounds['minlon']},{bounds['minlat']},{bounds['maxlon']},{bounds['maxlat']}"
                print(f"Thailand country bbox: {bbox}")
                return bbox
    except Exception as e:
        print(f"Error getting country bbox: {e}")

    return None


if __name__ == "__main__":
    # Demonstrate getting districts
    df = demonstrate_usage()

    # Also get full country bbox
    country_bbox = get_country_bbox()

    print("\n" + "=" * 80)
    print("ADMINISTRATIVE LEVELS IN THAILAND")
    print("=" * 80)
    print("admin_level=2: Country (Thailand)")
    print("admin_level=4: Provinces (Changwat) - 77 provinces")
    print("admin_level=6: Districts (Amphoe) - ~928 districts")
    print("admin_level=8: Sub-districts (Tambon) - thousands")
    print("\nTo get provinces instead, use: get_thailand_districts(admin_level=4)")
