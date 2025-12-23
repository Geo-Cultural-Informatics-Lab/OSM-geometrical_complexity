"""
Bounding Box Utilities for OSM Analysis

This module provides functions to generate bounding boxes from city names or coordinates
using the Nominatim geocoding API.
"""

import requests
import pandas as pd
import json
from math import cos, radians
from pathlib import Path
from utils.api_helpers import logger
from utils.chunking_utils import bbox_area_km2


# ============================================================================
# Geocoding and Bounding Box Functions
# ============================================================================

def get_bbox_by_city(city_name, radius_km=10):
    """
    Get bounding box for a city by name using Nominatim geocoding.

    Args:
        city_name: Name of the city (e.g., "Paris", "New York", "Tokyo")
        radius_km: Radius in kilometers to expand around city center (default: 10)

    Returns:
        Bounding box string in format "min_lon,min_lat,max_lon,max_lat" or None on error

    Example:
        >>> bbox = get_bbox_by_city("Paris", radius_km=15)
        >>> print(bbox)
        "2.255031,48.813564,2.426418,48.904637"
    """
    logger.info(f"Geocoding city: {city_name}")

    # Use Nominatim API to geocode city name
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": city_name,
        "format": "json",
        "limit": 1,
        "addressdetails": 1
    }
    headers = {
        "User-Agent": "OSM-Geometrical-Complexity-Analysis/1.0"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            results = response.json()

            if not results:
                logger.error(f"City not found: {city_name}")
                return None

            # Get the first result
            location = results[0]
            lat = float(location["lat"])
            lon = float(location["lon"])

            logger.info(f"City '{city_name}' found at coordinates: {lat}, {lon}")
            logger.info(f"Address: {location.get('display_name', 'N/A')}")

            # Generate bounding box around the coordinates
            bbox = bbox_by_location(lat, lon, radius_km)
            return bbox

        else:
            logger.error(f"Geocoding request failed with status {response.status_code}")
            return None

    except requests.exceptions.Timeout:
        logger.error("Geocoding request timed out")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Geocoding request failed: {str(e)}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"Error parsing geocoding response: {str(e)}")
        return None


def bbox_by_location(lat, lon, radius_km=10):
    """
    Generate bounding box around a given coordinate point.

    This function calculates a bounding box by converting the radius from kilometers
    to degrees, accounting for latitude-dependent longitude spacing.

    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        radius_km: Radius in kilometers to expand in all directions (default: 10)

    Returns:
        Bounding box string in format "min_lon,min_lat,max_lon,max_lat"

    Example:
        >>> bbox = bbox_by_location(48.8566, 2.3522, radius_km=15)
        >>> print(bbox)
        "2.255031,48.813564,2.426418,48.904637"

    Note:
        Uses approximation: 1 degree latitude ≈ 111 km
        Longitude spacing varies by latitude: 1 degree longitude ≈ 111 * cos(latitude) km
    """
    logger.info(f"Generating bounding box for coordinates: ({lat}, {lon}) with radius {radius_km} km")

    # Approximate conversion: 1 degree latitude ≈ 111 km
    # 1 degree longitude ≈ 111 * cos(latitude) km
    lat_degree_km = 111.0
    lon_degree_km = 111.0 * cos(radians(lat))

    # Calculate degree offsets
    lat_offset = radius_km / lat_degree_km
    lon_offset = radius_km / lon_degree_km

    # Calculate bounding box
    min_lat = lat - lat_offset
    max_lat = lat + lat_offset
    min_lon = lon - lon_offset
    max_lon = lon + lon_offset

    # Format as string (OSM bboxes format: "min_lon,min_lat,max_lon,max_lat")
    bbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"

    logger.info(f"Generated bounding box: {bbox}")
    logger.debug(f"  Approximate coverage: {radius_km*2} km × {radius_km*2} km")
    logger.debug(f"  Latitude range: {min_lat:.6f} to {max_lat:.6f}")
    logger.debug(f"  Longitude range: {min_lon:.6f} to {max_lon:.6f}")

    return bbox


def get_country_bbox(country_name, buffer_km=0):
    """
    Get bounding box for an entire country using Nominatim geocoding.

    Args:
        country_name: Country name (e.g., "Israel", "Germany", "France")
        buffer_km: Optional buffer to expand bbox in kilometers (default: 0)

    Returns:
        Bounding box string in format "min_lon,min_lat,max_lon,max_lat" or None on error

    Example:
        >>> bbox = get_country_bbox("Israel")
        >>> print(bbox)
        "34.2654,29.4968,35.8966,33.3356"
    """
    logger.info(f"Fetching country bounding box: {country_name}")

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "country": country_name,
        "format": "json",
        "limit": 1,
        "polygon_geojson": 0
    }
    headers = {
        "User-Agent": "OSM-Geometrical-Complexity-Analysis/1.0"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            results = response.json()

            if not results:
                logger.error(f"Country not found: {country_name}")
                return None

            # Get bounding box from result
            result = results[0]
            boundingbox = result.get("boundingbox")

            if not boundingbox:
                logger.error(f"No bounding box returned for {country_name}")
                return None

            # Nominatim returns [min_lat, max_lat, min_lon, max_lon]
            min_lat, max_lat, min_lon, max_lon = map(float, boundingbox)

            # Apply buffer if specified
            if buffer_km > 0:
                lat_buffer = buffer_km / 111.0
                center_lat = (min_lat + max_lat) / 2
                lon_buffer = buffer_km / (111.0 * cos(radians(center_lat)))

                min_lat -= lat_buffer
                max_lat += lat_buffer
                min_lon -= lon_buffer
                max_lon += lon_buffer

            # Convert to standard format
            bbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"

            logger.info(f"Country '{country_name}' bbox: {bbox}")
            area_km2 = bbox_area_km2(bbox)
            logger.info(f"  Area: {area_km2:,.0f} km²")

            return bbox

        else:
            logger.error(f"Geocoding request failed with status {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Error fetching country bbox: {str(e)}")
        return None


# ============================================================================
# CSV/JSON Country File Loading
# ============================================================================

def load_countries_from_csv(csv_path):
    """
    Load country definitions from CSV file.

    Expected CSV format:
        country_name,bbox,notes (optional columns)
        Israel,"34.27,29.50,35.90,33.34",Main analysis region
        Jordan,"34.88,29.18,39.30,33.38",Full country

    Alternative formats supported:
        - country_name,min_lon,min_lat,max_lon,max_lat
        - country_name,polygon_wkt (for more complex shapes)

    Args:
        csv_path: Path to CSV file

    Returns:
        List of dicts with keys: 'name', 'bbox', additional metadata
        Returns None on error

    Example:
        >>> countries = load_countries_from_csv("countries_polygons/middle_east.csv")
        >>> for country in countries:
        ...     print(f"{country['name']}: {country['bbox']}")
    """
    csv_path = Path(csv_path)

    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return None

    logger.info(f"Loading countries from CSV: {csv_path}")

    try:
        df = pd.read_csv(csv_path)

        # Validate required columns
        if 'country_name' not in df.columns:
            logger.error("CSV must have 'country_name' column")
            return None

        countries = []

        # Check if bbox is provided as single column
        if 'bbox' in df.columns:
            for idx, row in df.iterrows():
                country_data = {
                    'name': row['country_name'],
                    'bbox': row['bbox']
                }
                # Add any additional columns as metadata
                for col in df.columns:
                    if col not in ['country_name', 'bbox']:
                        country_data[col] = row[col]

                countries.append(country_data)

        # Check if bbox is provided as 4 separate columns
        elif all(col in df.columns for col in ['min_lon', 'min_lat', 'max_lon', 'max_lat']):
            for idx, row in df.iterrows():
                bbox = f"{row['min_lon']},{row['min_lat']},{row['max_lon']},{row['max_lat']}"
                country_data = {
                    'name': row['country_name'],
                    'bbox': bbox
                }
                # Add any additional columns as metadata
                for col in df.columns:
                    if col not in ['country_name', 'min_lon', 'min_lat', 'max_lon', 'max_lat']:
                        country_data[col] = row[col]

                countries.append(country_data)

        else:
            logger.error("CSV must have either 'bbox' column or 'min_lon,min_lat,max_lon,max_lat' columns")
            return None

        logger.info(f"Loaded {len(countries)} countries from CSV")
        for country in countries:
            bbox_area = bbox_area_km2(country['bbox'])
            logger.debug(f"  {country['name']}: {country['bbox']} ({bbox_area:,.0f} km²)")

        return countries

    except Exception as e:
        logger.error(f"Error loading CSV file: {str(e)}")
        return None


def load_countries_from_json(json_path):
    """
    Load country definitions from JSON file.

    Expected JSON format:
    {
      "dataset_name": "middle_east",
      "countries": [
        {"name": "Israel", "bbox": "34.27,29.50,35.90,33.34"},
        {"name": "Jordan", "bbox": "34.88,29.18,39.30,33.38"}
      ]
    }

    Args:
        json_path: Path to JSON file

    Returns:
        List of dicts with keys: 'name', 'bbox', additional metadata
        Returns None on error

    Example:
        >>> countries = load_countries_from_json("countries_polygons/middle_east.json")
        >>> for country in countries:
        ...     print(f"{country['name']}: {country['bbox']}")
    """
    json_path = Path(json_path)

    if not json_path.exists():
        logger.error(f"JSON file not found: {json_path}")
        return None

    logger.info(f"Loading countries from JSON: {json_path}")

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Handle different JSON structures
        if 'countries' in data:
            countries = data['countries']
        elif isinstance(data, list):
            countries = data
        else:
            logger.error("JSON must contain 'countries' key or be a list of countries")
            return None

        # Validate each country has required fields
        validated_countries = []
        for country in countries:
            if 'name' not in country or 'bbox' not in country:
                logger.warning(f"Skipping country without 'name' or 'bbox': {country}")
                continue

            validated_countries.append(country)

        logger.info(f"Loaded {len(validated_countries)} countries from JSON")
        for country in validated_countries:
            bbox_area = bbox_area_km2(country['bbox'])
            logger.debug(f"  {country['name']}: {country['bbox']} ({bbox_area:,.0f} km²)")

        return validated_countries

    except Exception as e:
        logger.error(f"Error loading JSON file: {str(e)}")
        return None


def load_countries_from_file(file_path):
    """
    Auto-detect file type and load countries from CSV or JSON.

    Args:
        file_path: Path to CSV or JSON file

    Returns:
        List of country dicts or None on error

    Example:
        >>> countries = load_countries_from_file("countries_polygons/regions.csv")
    """
    file_path = Path(file_path)

    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return None

    suffix = file_path.suffix.lower()

    if suffix == '.csv':
        return load_countries_from_csv(file_path)
    elif suffix == '.json':
        return load_countries_from_json(file_path)
    else:
        logger.error(f"Unsupported file format: {suffix}. Must be .csv or .json")
        return None


# ============================================================================
# Predefined Bounding Boxes (for backward compatibility)
# ============================================================================

BBOXES = {
    'heidelberg': "8.1543,49.1757,9.1351,49.6884",
    'paris': "2.255031,48.813564,2.426418,48.904637",
    'hainan': "108.4078,18.0357,111.1148,20.1493",
    'thailand': "99.6253,9.3452,100.201,10.1602",
    'beit_shemesh': "34.938188,31.689471,35.035005,31.786876"
}


def get_bbox(location_name):
    """
    Get predefined bounding box by location name.

    Args:
        location_name: Name of predefined location (lowercase)

    Returns:
        Bounding box string or None if not found

    Example:
        >>> bbox = get_bbox('paris')
        >>> print(bbox)
        "2.255031,48.813564,2.426418,48.904637"
    """
    return BBOXES.get(location_name.lower())


def add_bbox(location_name, bbox):
    """
    Add a new bounding box to the predefined dictionary.

    Args:
        location_name: Name to associate with the bbox
        bbox: Bounding box string in format "min_lon,min_lat,max_lon,max_lat"

    Example:
        >>> add_bbox('london', '0.0,51.0,1.0,52.0')
    """
    BBOXES[location_name.lower()] = bbox
    logger.info(f"Added bounding box for '{location_name}': {bbox}")


def list_bboxes():
    """
    List all predefined bounding boxes.

    Returns:
        Dictionary of location names to bounding boxes
    """
    return BBOXES.copy()
