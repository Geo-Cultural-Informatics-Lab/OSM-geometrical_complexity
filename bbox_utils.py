"""
Bounding Box Utilities for OSM Analysis

This module provides functions to generate bounding boxes from city names or coordinates
using the Nominatim geocoding API.
"""

import requests
from math import cos, radians
from api_helpers import logger


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
