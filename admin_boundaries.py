"""
Administrative Boundaries Module for OSM Analysis

This module provides functions to query and retrieve administrative boundaries
from OpenStreetMap using the Overpass API, enabling automatic subdivision of
countries into provinces, districts, or other administrative levels.
"""

import requests
import json
import time
from pathlib import Path
from api_helpers import logger


# Administrative level mapping for reference
ADMIN_LEVELS = {
    2: "Country",
    3: "First-level (varies by country)",
    4: "Province/State/Region",
    5: "Second-level subdivision",
    6: "District/County",
    7: "Third-level subdivision",
    8: "Municipality/Sub-district",
    9: "Fourth-level subdivision",
    10: "Neighborhood/Village"
}


def get_admin_boundaries(country_iso=None, country_name=None, admin_level=6,
                         timeout=120, cache_file=None):
    """
    Get administrative boundaries for a country from Overpass API.

    This function queries OpenStreetMap for administrative divisions at a specified
    level within a country, returning their names and bounding boxes.

    Args:
        country_iso: ISO 3166-1 alpha-2 country code (e.g., 'TH', 'DE', 'US')
        country_name: Country name as fallback if ISO not available
        admin_level: Administrative level to query (default: 6 for districts)
                    Common levels:
                    - 4: Provinces/States
                    - 6: Districts/Counties
                    - 8: Sub-districts/Municipalities
        timeout: Query timeout in seconds (default: 120)
        cache_file: Optional path to cache results as JSON

    Returns:
        List of dicts with boundary information:
        [{
            'osm_id': int,
            'name': str,
            'name_en': str,
            'name_local': str,
            'bbox': str (format: "min_lon,min_lat,max_lon,max_lat"),
            'center_lat': float,
            'center_lon': float,
            'admin_level': int,
            'ref': str (optional administrative code)
        }, ...]

    Example:
        >>> # Get all districts in Thailand
        >>> districts = get_admin_boundaries(country_iso='TH', admin_level=6)
        >>> print(f"Found {len(districts)} districts")
        >>> for district in districts[:5]:
        ...     print(f"{district['name']}: {district['bbox']}")
    """
    # Check cache first
    if cache_file and Path(cache_file).exists():
        logger.info(f"Loading cached admin boundaries from {cache_file}")
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                logger.info(f"Loaded {len(cached_data)} boundaries from cache")
                return cached_data
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}, fetching fresh data")

    logger.info(f"Querying Overpass API for admin_level={admin_level}")
    if country_iso:
        logger.info(f"Country: {country_iso} (ISO code)")
    elif country_name:
        logger.info(f"Country: {country_name}")
    else:
        logger.error("Must provide either country_iso or country_name")
        return None

    # Build Overpass query
    # We request bbox output ('bb') which gives us the bounding box for each relation
    if country_iso:
        area_filter = f'["ISO3166-1"="{country_iso}"][admin_level=2]'
    else:
        # Fallback to name-based search (less reliable)
        area_filter = f'["name:en"="{country_name}"][admin_level=2]'

    overpass_query = f"""
    [out:json][timeout:{timeout}];
    area{area_filter};
    (
      relation["admin_level"="{admin_level}"](area);
    );
    out center tags bb;
    """

    url = "https://overpass-api.de/api/interpreter"

    try:
        logger.debug(f"Overpass query: {overpass_query.strip()}")
        start_time = time.time()

        response = requests.post(
            url,
            data={'data': overpass_query},
            timeout=timeout + 10
        )

        query_time = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            elements = data.get('elements', [])

            logger.info(f"Found {len(elements)} administrative regions (query took {query_time:.1f}s)")

            if not elements:
                logger.warning(f"No administrative boundaries found for admin_level={admin_level}")
                return []

            boundaries = []
            for el in elements:
                tags = el.get('tags', {})
                center = el.get('center', {})
                bounds = el.get('bounds', {})

                # Extract names (prefer English, fall back to local name)
                name_en = tags.get('name:en', '')
                name_local = tags.get('name', '')
                name = name_en or name_local

                if not name:
                    logger.warning(f"Skipping boundary with OSM ID {el.get('id')} - no name found")
                    continue

                # Get bounding box in ohsome API format: "min_lon,min_lat,max_lon,max_lat"
                if bounds:
                    bbox = f"{bounds['minlon']},{bounds['minlat']},{bounds['maxlon']},{bounds['maxlat']}"
                else:
                    # If no bbox provided, create small area from center
                    lat = center.get('lat', 0)
                    lon = center.get('lon', 0)
                    if lat == 0 and lon == 0:
                        logger.warning(f"Skipping {name} - no coordinates available")
                        continue
                    buffer = 0.1  # ~11km buffer as fallback
                    bbox = f"{lon-buffer},{lat-buffer},{lon+buffer},{lat+buffer}"
                    logger.debug(f"{name}: Using center-based bbox (no bounds in OSM data)")

                boundary_info = {
                    'osm_id': el.get('id'),
                    'name': name,
                    'name_en': name_en,
                    'name_local': name_local,
                    'bbox': bbox,
                    'center_lat': center.get('lat', 0),
                    'center_lon': center.get('lon', 0),
                    'admin_level': admin_level,
                    'type': tags.get('type', ''),
                    'ref': tags.get('ref', ''),  # Administrative code
                    'wikidata': tags.get('wikidata', ''),  # Wikidata ID for reference
                    'iso_code': tags.get('ISO3166-2', '')  # ISO code if available
                }

                boundaries.append(boundary_info)

            # Sort by name for consistency
            boundaries.sort(key=lambda x: x['name'])

            logger.info(f"Successfully extracted {len(boundaries)} boundaries")

            # Cache results if requested
            if cache_file:
                try:
                    cache_path = Path(cache_file)
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(boundaries, f, indent=2, ensure_ascii=False)
                    logger.info(f"Cached boundaries to {cache_file}")
                except Exception as e:
                    logger.warning(f"Failed to cache results: {e}")

            return boundaries

        else:
            logger.error(f"Overpass API request failed with status {response.status_code}")
            logger.error(f"Response: {response.text[:500]}")
            return None

    except requests.exceptions.Timeout:
        logger.error(f"Overpass API request timed out after {timeout}s")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Overpass API request failed: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error processing Overpass API response: {str(e)}")
        return None


def get_country_iso_code(country_name, timeout=10):
    """
    Get ISO 3166-1 alpha-2 code for a country by name using Overpass API.

    Args:
        country_name: Country name (e.g., "Thailand", "Germany")
        timeout: Query timeout in seconds

    Returns:
        ISO code string (e.g., "TH", "DE") or None if not found

    Example:
        >>> iso = get_country_iso_code("Thailand")
        >>> print(iso)  # "TH"
    """
    logger.info(f"Looking up ISO code for country: {country_name}")

    overpass_query = f"""
    [out:json][timeout:{timeout}];
    (
      relation["admin_level"="2"]["name:en"="{country_name}"];
      relation["admin_level"="2"]["name"="{country_name}"];
    );
    out tags;
    """

    url = "https://overpass-api.de/api/interpreter"

    try:
        response = requests.post(
            url,
            data={'data': overpass_query},
            timeout=timeout + 5
        )

        if response.status_code == 200:
            data = response.json()
            elements = data.get('elements', [])

            if elements:
                iso_code = elements[0].get('tags', {}).get('ISO3166-1')
                if iso_code:
                    logger.info(f"Found ISO code for {country_name}: {iso_code}")
                    return iso_code

        logger.warning(f"Could not find ISO code for {country_name}")
        return None

    except Exception as e:
        logger.error(f"Error looking up ISO code: {str(e)}")
        return None


def save_boundaries_to_csv(boundaries, output_file):
    """
    Save administrative boundaries to CSV file.

    Args:
        boundaries: List of boundary dicts from get_admin_boundaries()
        output_file: Path to output CSV file

    Returns:
        pandas DataFrame

    Example:
        >>> boundaries = get_admin_boundaries(country_iso='TH', admin_level=6)
        >>> df = save_boundaries_to_csv(boundaries, 'thailand_districts.csv')
    """
    import pandas as pd

    df = pd.DataFrame(boundaries)

    # Reorder columns for better readability
    column_order = ['name', 'name_en', 'name_local', 'bbox', 'center_lat', 'center_lon',
                   'osm_id', 'admin_level', 'ref', 'iso_code', 'wikidata', 'type']
    df = df[[col for col in column_order if col in df.columns]]

    # Create output directory if needed
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save to CSV
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    logger.info(f"Saved {len(boundaries)} boundaries to {output_file}")

    return df


def validate_admin_level(country_iso, admin_level, timeout=10):
    """
    Check if a country has data at the specified administrative level.

    Args:
        country_iso: ISO 3166-1 alpha-2 country code
        admin_level: Administrative level to check
        timeout: Query timeout in seconds

    Returns:
        Tuple (bool, int): (has_data, count_of_boundaries)

    Example:
        >>> has_data, count = validate_admin_level('TH', 6)
        >>> if has_data:
        ...     print(f"Thailand has {count} districts")
    """
    logger.info(f"Validating admin_level={admin_level} for {country_iso}")

    overpass_query = f"""
    [out:json][timeout:{timeout}];
    area["ISO3166-1"="{country_iso}"][admin_level=2];
    (
      relation["admin_level"="{admin_level}"](area);
    );
    out count;
    """

    url = "https://overpass-api.de/api/interpreter"

    try:
        response = requests.post(
            url,
            data={'data': overpass_query},
            timeout=timeout + 5
        )

        if response.status_code == 200:
            data = response.json()
            elements = data.get('elements', [])

            if elements and 'tags' in elements[0]:
                count = elements[0]['tags'].get('total', 0)
                has_data = count > 0
                logger.info(f"Found {count} boundaries at admin_level={admin_level}")
                return has_data, count

        return False, 0

    except Exception as e:
        logger.error(f"Error validating admin_level: {str(e)}")
        return False, 0


def get_recommended_admin_level(country_iso):
    """
    Recommend an appropriate administrative level for a country.

    This checks common admin levels and suggests the most suitable one
    for subdivision analysis (typically districts/counties).

    Args:
        country_iso: ISO 3166-1 alpha-2 country code

    Returns:
        Tuple (int, int, str): (recommended_level, count, description)

    Example:
        >>> level, count, desc = get_recommended_admin_level('TH')
        >>> print(f"Recommended: {desc} (level {level}) with {count} regions")
    """
    logger.info(f"Finding recommended admin level for {country_iso}")

    # Check common levels in order of preference
    levels_to_check = [6, 4, 5, 7, 8]

    for level in levels_to_check:
        has_data, count = validate_admin_level(country_iso, level, timeout=10)

        if has_data and count > 0:
            description = ADMIN_LEVELS.get(level, f"Level {level}")
            logger.info(f"Recommended admin_level={level} ({description}) with {count} regions")
            return level, count, description

    logger.warning(f"No suitable admin level found for {country_iso}")
    return None, 0, "None found"
