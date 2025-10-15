"""
OSM Geometrical Complexity Analysis Functions

This module provides functions to extract and analyze OpenStreetMap data
using the Ohsome API, focusing on geometrical complexity metrics.
"""

import os
import json
import logging
import requests
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
from shapely.geometry import MultiPoint, Polygon, MultiPolygon
from shapely.ops import transform
import pyproj
from math import radians, sin, cos, sqrt, atan2
import time
import geopandas as gpd


# ============================================================================
# Logging Configuration
# ============================================================================

def setup_logging(log_file='geometrical_complexity_analysis.log', log_level=logging.DEBUG,
                  console_level=logging.INFO):
    """
    Configure logging for the analysis module.

    Args:
        log_file: Path to log file
        log_level: File logging level (default: DEBUG)
        console_level: Console logging level (default: INFO)
    """
    # Create logger
    logger = logging.getLogger('geometrical_complexity_analysis')
    logger.setLevel(logging.DEBUG)  # Capture all levels

    # Prevent duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    # File handler - detailed logging
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # Console handler - less verbose
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    console_handler.setFormatter(console_formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Initialize logger
logger = setup_logging()


# ============================================================================
# Core API Functions
# ============================================================================

def _call_ohsome_api(endpoint, bounds, filter_query, time_param, return_type='dataframe'):
    """
    Base function for calling Ohsome API endpoints.

    Args:
        endpoint: API endpoint path (e.g., 'count', 'length', 'area', 'geometry')
        bounds: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        filter_query: OSM filter query
        time_param: ISO-8601 timestamp or interval
        return_type: 'dataframe' or 'json'

    Returns:
        DataFrame or dict depending on return_type, None on error
    """
    start_time = time.time()
    url = f"https://api.ohsome.org/v1/elements/{endpoint}"

    params = {
        "bboxes": bounds,
        "time": time_param,
        "filter": filter_query
    }

    logger.debug(f"Calling Ohsome API endpoint: {endpoint}")
    logger.debug(f"Parameters: bounds={bounds}, filter={filter_query}, time={time_param}")

    try:
        response = requests.get(url, params=params, timeout=300)
        api_time = time.time() - start_time

        if response.status_code == 200:
            parse_start = time.time()
            data = response.json()
            parse_time = time.time() - parse_start

            logger.debug(f"API call ({endpoint}): {api_time:.2f}s (network: {api_time:.2f}s, parse: {parse_time:.3f}s)")
            logger.info(f"Successfully retrieved data from {endpoint} endpoint")

            if return_type == 'dataframe':
                return pd.json_normalize(data['result']) if 'result' in data else data
            return data
        else:
            logger.error(f"API request failed with status {response.status_code}: {response.text}")
            return None

    except requests.exceptions.Timeout:
        logger.error(f"API request timed out for endpoint {endpoint} (>300s)")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed for endpoint {endpoint}: {str(e)}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response from {endpoint}: {str(e)}")
        return None


def _save_to_file(data, path, filename, data_format='json'):
    """
    Save data to file with directory creation.

    Args:
        data: Data to save (dict, DataFrame, etc.)
        path: Directory path
        filename: Filename
        data_format: 'json' or 'csv'
    """
    if not path or not filename:
        return

    try:
        os.makedirs(path, exist_ok=True)
        file_path = os.path.join(path, filename)

        if data_format == 'json':
            with open(file_path, 'a', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif data_format == 'csv':
            header = False
            if not os.path.exists(file_path):
                header=True # write header only if file doesn't exist
            data.to_csv(file_path, index=False, mode="a", header=header)

        else:
            logger.warning(f"Unknown data format: {data_format}, skipping save")
            return

        logger.info(f"Data saved to {file_path}")

    except OSError as e:
        logger.error(f"Failed to save file {file_path}: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error saving file {file_path}: {str(e)}")


# ============================================================================
# Statistical Processing Functions
# ============================================================================

def _calculate_node_statistics(node_counts, bounds):
    """
    Calculate statistical measures for node count distribution.

    Args:
        node_counts: Array of node counts per way
        bounds: Bounding box string for reference

    Returns:
        DataFrame with statistical measures
    """
    return pd.DataFrame({
        'bbox': [bounds],
        'sum': [node_counts.sum()],
        'mean': [node_counts.mean()],
        'median': [np.median(node_counts)],
        'mode': [stats.mode(node_counts, keepdims=False)],
        'std': [node_counts.std()]
    })


def _extract_node_counts(features):
    """
    Extract node counts from GeoJSON features.

    Args:
        features: List of GeoJSON features from Ohsome API

    Returns:
        NumPy array of node counts
    """
    if not features:
        logger.warning("Ohsome API returned no elements")
        return np.array([0], dtype=int)

    logger.debug(f"Extracting node counts from {len(features)} features")

    node_counts = []
    geometry_types = {}

    for f in features:
        geom_type = f['geometry']['type']
        coords = f['geometry']['coordinates']

        # Track geometry type distribution
        geometry_types[geom_type] = geometry_types.get(geom_type, 0) + 1

        if geom_type == 'LineString':
            node_counts.append(len(coords))
        elif geom_type == 'MultiLineString':
            node_counts.append(sum(len(line) for line in coords))
        elif geom_type == 'Polygon':
            node_counts.append(sum(len(ring) for ring in coords))
        elif geom_type == 'MultiPolygon':
            node_counts.append(sum(len(ring) for polygon in coords for ring in polygon))

    logger.debug(f"Geometry type distribution: {geometry_types}")
    logger.info(f"Successfully extracted {len(node_counts)} node count values")

    return np.array(node_counts, dtype=int)


def _calculate_linestring_length(coords):
    """
    Calculate length of a LineString in meters using Haversine formula.

    Args:
        coords: List of [lon, lat] coordinate pairs

    Returns:
        Length in meters
    """

    total_length = 0.0
    R = 6371000  # Earth radius in meters

    for i in range(len(coords) - 1):
        lon1, lat1 = radians(coords[i][0]), radians(coords[i][1])
        lon2, lat2 = radians(coords[i + 1][0]), radians(coords[i + 1][1])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        total_length += R * c

    return total_length


def _extract_comprehensive_metrics(features, bounds):
    """
    Extract all metrics from geometry features in a single pass.

    Args:
        features: List of GeoJSON LineString/MultiLineString/Polygon features
        bounds: Bounding box string for reference

    Returns:
        Dictionary with node counts, feature count, and total length
    """
    start_time = time.time()

    if not features:
        logger.warning("No features returned for comprehensive metrics extraction")
        return {
            'node_counts': np.array([0], dtype=int),
            'road_count': 0,
            'cumulative_road_length': 0.0
        }

    logger.info(f"Extracting comprehensive metrics from {len(features)} features")

    node_counts = []
    total_length = 0.0

    geometry_count_time = 0
    length_calc_time = 0

    for feature in features:
        geom_type = feature['geometry']['type']
        coords = feature['geometry']['coordinates']

        count_start = time.time()

        if geom_type == 'LineString':
            node_counts.append(len(coords))
            geometry_count_time += time.time() - count_start

            length_start = time.time()
            total_length += _calculate_linestring_length(coords)
            length_calc_time += time.time() - length_start

        elif geom_type == 'MultiLineString':
            total_nodes = sum(len(line) for line in coords)
            node_counts.append(total_nodes)
            geometry_count_time += time.time() - count_start

            length_start = time.time()
            for line in coords:
                total_length += _calculate_linestring_length(line)
            length_calc_time += time.time() - length_start

        elif geom_type == 'Polygon':
            # For Polygon, count all nodes and calculate perimeter
            total_nodes = sum(len(ring) for ring in coords)
            node_counts.append(total_nodes)
            geometry_count_time += time.time() - count_start

            length_start = time.time()
            # Calculate perimeter (outer ring only for length calculation)
            total_length += _calculate_linestring_length(coords[0])
            length_calc_time += time.time() - length_start

        elif geom_type == 'MultiPolygon':
            # For MultiPolygon, count all nodes and calculate total perimeter
            total_nodes = sum(len(ring) for polygon in coords for ring in polygon)
            node_counts.append(total_nodes)
            geometry_count_time += time.time() - count_start

            length_start = time.time()
            # Calculate perimeter of all outer rings
            for polygon in coords:
                total_length += _calculate_linestring_length(polygon[0])
            length_calc_time += time.time() - length_start

    total_time = time.time() - start_time
    num_features = len(node_counts)
    features_per_sec = num_features / total_time if total_time > 0 else 0

    logger.debug(f"Metrics extraction: {total_time:.2f}s [{num_features:,} features @ {features_per_sec:.1f} feat/s]")
    logger.debug(f"  - Node counting: {geometry_count_time:.3f}s")
    if length_calc_time > 0:
        logger.debug(f"  - Length calculation: {length_calc_time:.2f}s ({num_features/length_calc_time:.1f} feat/s)")
    else:
        logger.debug(f"  - Length calculation: {length_calc_time:.2f}s")

    logger.info(f"Metrics extraction complete: {num_features} features processed in {total_time:.2f}s")

    return {
        'node_counts': np.array(node_counts, dtype=int),
        'road_count': len(features),
        'cumulative_road_length': total_length
    }


def _calculate_convex_hull_metrics_vectorized(features, bounds):
    """
    Calculate convex hull metrics using vectorized geopandas operations.

    Args:
        features: List of GeoJSON polygon features
        bounds: Bounding box string

    Returns:
        DataFrame with area and convex hull metrics
    """
    start_time = time.time()

    if not features:
        logger.warning("No polygon features returned for convex hull calculation")
        return None

    logger.info(f"Calculating convex hull metrics for {len(features)} polygon features (vectorized)")

    # Calculate UTM projection parameters
    min_lon, min_lat, max_lon, max_lat = map(float, bounds.split(','))
    center_lon = (min_lon + max_lon) / 2
    utm_zone = int((center_lon + 180) / 6) + 1
    utm_crs = f"+proj=utm +zone={utm_zone} +datum=WGS84"

    # Extract metadata and create exterior-ring-only geometries
    prep_start = time.time()
    geometries = []
    way_ids = []
    is_multipolygons = []
    inner_ring_counts = []

    for feature in features:
        coords = feature["geometry"]["coordinates"]
        geom_type = feature["geometry"]["type"]

        if geom_type == "Polygon":
            # Use only exterior ring
            geom = Polygon(coords[0])
            inner_ring_counts.append(len(coords) - 1)
            is_multipolygons.append(False)
        elif geom_type == "MultiPolygon":
            # Use exterior rings from all polygons
            geom = MultiPolygon([Polygon(poly[0]) for poly in coords])
            inner_ring_counts.append(sum(len(poly) - 1 for poly in coords))
            is_multipolygons.append(True)
        else:
            continue

        geometries.append(geom)
        way_ids.append(feature["properties"].get("osmID", feature.get("id")))

    prep_time = time.time() - prep_start

    # Create GeoDataFrame
    gdf_start = time.time()
    gdf = gpd.GeoDataFrame({
        'way_id': way_ids,
        'is_multipolygon': is_multipolygons,
        'inner_ring_count': inner_ring_counts
    }, geometry=geometries, crs="EPSG:4326")
    gdf_time = time.time() - gdf_start

    # Vectorized coordinate transformation (BEFORE convex hull to avoid CRS issues)
    transform_start = time.time()
    gdf_utm = gdf.to_crs(utm_crs)
    transform_time = time.time() - transform_start

    # Vectorized convex hull computation (in UTM projection)
    hull_start = time.time()
    gdf_utm['convex_hull_geom'] = gdf_utm.geometry.convex_hull
    hull_time = time.time() - hull_start

    # Vectorized area calculations
    area_start = time.time()
    gdf_utm['area_m2'] = gdf_utm.geometry.area
    gdf_utm['convex_hull_m2'] = gdf_utm['convex_hull_geom'].area
    gdf_utm['ratio'] = 1 - (gdf_utm['area_m2'] / gdf_utm['convex_hull_m2'])
    gdf_utm['ratio'] = gdf_utm['ratio'].fillna(0)  # Handle division by zero
    area_time = time.time() - area_start

    # Extract results
    result = gdf_utm[['way_id', 'area_m2', 'convex_hull_m2', 'ratio', 'is_multipolygon', 'inner_ring_count']].copy()

    total_time = time.time() - start_time
    features_per_sec = len(geometries) / total_time if total_time > 0 else 0

    logger.debug(f"Convex hull calculation (VECTORIZED): {total_time:.2f}s [{len(geometries):,} features @ {features_per_sec:.1f} feat/s]")
    if prep_time > 0:
        logger.debug(f"  - Data preparation: {prep_time:.3f}s ({len(geometries)/prep_time:.1f} feat/s)")
    else:
        logger.debug(f"  - Data preparation: {prep_time:.3f}s")
    logger.debug(f"  - GeoDataFrame creation: {gdf_time:.3f}s")
    logger.debug(f"  - Coordinate transformation: {transform_time:.3f}s")
    if hull_time > 0:
        logger.debug(f"  - Convex hull computation: {hull_time:.3f}s ({len(geometries)/hull_time:.1f} feat/s)")
    else:
        logger.debug(f"  - Convex hull computation: {hull_time:.3f}s")
    logger.debug(f"  - Area calculation: {area_time:.3f}s")

    logger.info(f"Convex hull metrics calculated for {len(geometries)} features in {total_time:.2f}s")

    return result


def _calculate_convex_hull_metrics(features, bounds, use_vectorized=True):
    """
    Calculate convex hull metrics for polygon features.

    Args:
        features: List of GeoJSON polygon features
        bounds: Bounding box string
        use_vectorized: If True, use geopandas vectorized operations (faster)

    Returns:
        DataFrame with area and convex hull metrics
    """
    if use_vectorized:
        return _calculate_convex_hull_metrics_vectorized(features, bounds)

    # Fall back to loop-based implementation
    start_time = time.time()

    if not features:
        logger.warning("No polygon features returned for convex hull calculation")
        return None

    logger.info(f"Calculating convex hull metrics for {len(features)} polygon features (loop-based)")

    # Calculate UTM projection parameters from bounding box center
    min_lon, min_lat, max_lon, max_lat = map(float, bounds.split(','))
    center_lon = (min_lon + max_lon) / 2
    center_lat = (min_lat + max_lat) / 2
    utm_zone = int((center_lon + 180) / 6) + 1

    proj_start = time.time()
    proj = pyproj.Transformer.from_crs(
        "epsg:4326",
        f"+proj=utm +zone={utm_zone} +datum=WGS84",
        always_xy=True
    ).transform
    proj_time = time.time() - proj_start

    rows = []

    # Granular timing metrics
    point_extraction_time = 0
    convex_hull_time = 0
    transformation_time = 0
    area_calc_time = 0

    for feature in features:
        coords = feature["geometry"]["coordinates"]
        geom_type = feature["geometry"]["type"]

        # Extract only exterior ring points for convex hull (performance optimization)
        # Also track polygon complexity indicators
        extract_start = time.time()
        if geom_type == "Polygon":
            points = coords[0]  # Only exterior ring
            inner_ring_count = len(coords) - 1  # Number of holes
            is_multipolygon = False
        elif geom_type == "MultiPolygon":
            # For MultiPolygon, use all exterior rings (complexity indicator)
            points = [pt for polygon in coords for pt in polygon[0]]
            inner_ring_count = sum(len(polygon) - 1 for polygon in coords)
            is_multipolygon = True
        else:
            continue
        point_extraction_time += time.time() - extract_start

        hull_start = time.time()
        geom = MultiPoint(points).convex_hull
        convex_hull_time += time.time() - hull_start

        transform_start = time.time()
        geom_m = transform(proj, geom)
        transformation_time += time.time() - transform_start

        # geom_m is already a convex hull, no need to compute it again
        area_start = time.time()
        convex_hull_area = geom_m.area
        area_calc_time += time.time() - area_start

        rows.append({
            "way_id": feature["properties"].get("osmID", feature.get("id")),
            "area_m2": geom_m.area,
            "convex_hull_m2": convex_hull_area,
            'ratio': 1 - (geom_m.area / convex_hull_area) if convex_hull_area > 0 else 0,
            'is_multipolygon': is_multipolygon,
            'inner_ring_count': inner_ring_count
        })

    total_time = time.time() - start_time
    geometry_total = point_extraction_time + convex_hull_time + transformation_time + area_calc_time
    num_features = len(rows)
    features_per_sec = num_features / total_time if total_time > 0 else 0

    logger.debug(f"Convex hull calculation (LOOP): {total_time:.2f}s [{num_features:,} features @ {features_per_sec:.1f} feat/s]")
    logger.debug(f"  - Projection setup: {proj_time:.3f}s")
    logger.debug(f"  - Point extraction: {point_extraction_time:.3f}s")
    if convex_hull_time > 0:
        logger.debug(f"  - Convex hull computation: {convex_hull_time:.2f}s ({num_features/convex_hull_time:.1f} feat/s)")
    else:
        logger.debug(f"  - Convex hull computation: {convex_hull_time:.2f}s")
    logger.debug(f"  - Coordinate transformation: {transformation_time:.2f}s")
    logger.debug(f"  - Area calculation: {area_calc_time:.3f}s")
    logger.debug(f"  - Other overhead: {(total_time - proj_time - geometry_total):.3f}s")

    logger.info(f"Convex hull metrics calculated for {num_features} features in {total_time:.2f}s")

    return pd.DataFrame(rows)


# ============================================================================
# Public API Functions
# ============================================================================

def get_count(bounds, filter="type:way and highway=*", time="2008-01-01/2025-01-01/P1M",
              path=None, filename=None):
    """
    Extract cumulative number of OSM features using Ohsome API.

    Args:
        bounds: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        filter: OSM filter query (default: highway tags)
        time: ISO-8601 timestamp or interval (default: monthly 2008-2025)
        path: Optional directory path to save results
        filename: Optional filename for saved results

    Returns:
        DataFrame with count results, None on error
    """
    logger.info(f"Fetching feature counts for bounds: {bounds}")
    result = _call_ohsome_api('count', bounds, filter, time)

    if result is not None:
        logger.info("Count data successfully retrieved")

        # Save raw JSON if requested
        if path and filename:
            response = _call_ohsome_api('count', bounds, filter, time, return_type='json')
            _save_to_file(response, path, filename, data_format='json')
    else:
        logger.error("Failed to retrieve count data")

    return result

def get_len(bounds, filter="type:way and highway=*", time="2008-01-01/2025-01-01/P1M",
            path=None, filename=None):
    """
    Extract aggregated length of OSM features using Ohsome API.

    Args:
        bounds: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        filter: OSM filter query (default: highway tags)
        time: ISO-8601 timestamp or interval (default: monthly 2008-2025)
        path: Optional directory path to save results
        filename: Optional filename for saved results

    Returns:
        DataFrame with length results, None on error
    """
    logger.info(f"Fetching feature lengths for bounds: {bounds}")
    result = _call_ohsome_api('length', bounds, filter, time)

    if result is not None:
        logger.info("Length data successfully retrieved")

        # Save raw JSON if requested
        if path and filename:
            response = _call_ohsome_api('length', bounds, filter, time, return_type='json')
            _save_to_file(response, path, filename, data_format='json')
    else:
        logger.error("Failed to retrieve length data")

    return result


def get_area(bounds, filter="type:way and building=*", time="2008-01-01/2025-01-01/P1M",
             path=None, filename=None):
    """
    Extract aggregated area of OSM features using Ohsome API.

    Args:
        bounds: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        filter: OSM filter query (default: building tags)
        time: ISO-8601 timestamp or interval (default: monthly 2008-2025)
        path: Optional directory path to save results
        filename: Optional filename for saved results

    Returns:
        DataFrame with area results, None on error
    """
    logger.info(f"Fetching feature areas for bounds: {bounds}")
    result = _call_ohsome_api('area', bounds, filter, time)

    if result is not None:
        logger.info("Area data successfully retrieved")

        # Save raw JSON if requested
        if path and filename:
            response = _call_ohsome_api('area', bounds, filter, time, return_type='json')
            _save_to_file(response, path, filename, data_format='json')
    else:
        logger.error("Failed to retrieve area data")

    return result


def get_vertices(bounds, filter="type:way and highway=*", time="2025-01-01",
                 path=None, filename=None, distribution=False):
    """
    Extract node counts per way and calculate statistical measures.

    Args:
        bounds: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        filter: OSM filter query (default: highway tags)
        time: ISO-8601 timestamp (default: 2025-01-01)
        path: Optional directory path to save raw data
        filename: Optional filename for saved raw data
        distribution: If True, return raw node counts array instead of statistics

    Returns:
        DataFrame with statistics or NumPy array if distribution=True, None on error
    """
    data = _call_ohsome_api('geometry', bounds, filter, time, return_type='json')

    if data is None:
        return None

    features = data.get("features", [])
    node_counts = _extract_node_counts(features)

    # Save raw data if requested
    if path and filename and features:
        way_ids = np.fromiter(
            (f['properties']['osmID'] for f in features),
            dtype=int
        )
        raw_data = pd.DataFrame({'way_id': way_ids, 'node_count': node_counts})
        _save_to_file(raw_data.to_dict('records'), path, filename, data_format='json')

    # Return raw distribution if requested
    if distribution:
        return node_counts

    # Return statistical summary
    return _calculate_node_statistics(node_counts, bounds)


def get_poly_coords(region_name, bounds, filter="type:way and building=*", time_param="2025-01-01",
                    path=None, filename=None, distribution=False, use_vectorized=True):
    """
    Extract polygon coordinates and calculate convex hull metrics.

    Args:
        bounds: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        filter: OSM filter query (default: building tags)
        time_param: ISO-8601 timestamp (default: 2025-01-01)
        path: Optional directory path to save results
        filename: Optional filename for saved results
        distribution: If True, return full DataFrame instead of summary statistics
        use_vectorized: If True, use geopandas vectorized operations (default, much faster)

    Returns:
        DataFrame with convex hull metrics or summary statistics
        :param region_name:
    """
    start_time = time.time()

    data = _call_ohsome_api('geometry', bounds, filter, time_param, return_type='json')

    if data is None:
        return None

    features = data.get("features", [])
    df = _calculate_convex_hull_metrics(features, bounds, use_vectorized=use_vectorized)
    cols = df.columns.tolist()
    df["region_name"] = region_name
    df["bbox"] = bounds
    df = df[["region_name", "bbox"] + cols]

    if df is None:
        return None



    # Return full distribution if requested
    if distribution:
        print(f"Total get_poly_coords time: {time.time() - start_time:.2f}s\n")
        return df

    # Return summary statistics
    summary_statistics = pd.DataFrame({
        'region': region_name,
        'bbox': [bounds],
        'sum_chull_area': [df['convex_hull_m2'].sum()],
        'mean_chull_area': [df['convex_hull_m2'].mean()],
        'median_chull_area': [np.median(df['convex_hull_m2'])],
        'sum_area': [df['area_m2'].sum()],
        'mean_area': [df['area_m2'].mean()],
        'median_area': [np.median(df['area_m2'])],
        'sum_ratio': [df['ratio'].sum()],
        'mean_ratio': [df['ratio'].mean()],
        'median_ratio': [np.median(df['ratio'])],
        'multipolygon_count': [df['is_multipolygon'].sum()],
        'multipolygon_ratio': [df['is_multipolygon'].mean()],
        'total_inner_rings': [df['inner_ring_count'].sum()],
        'mean_inner_rings': [df['inner_ring_count'].mean()]
    })

    print(f"Summary statistics:")
    # Save raw data if requested
    if path and filename:
        _save_to_file(df, path, filename, data_format='csv')
        _save_to_file(summary_statistics, path, os.path.basename(filename)+"_summary.csv", data_format='csv')
    
    print(f"Total get_poly_coords time: {time.time() - start_time:.2f}s\n")

    return summary_statistics


# ============================================================================
# Analysis Functions
# ============================================================================

def analyze_region(region_name, bbox, timestamp="2025-01-01", filter="type:way and highway=*"):
    """
    Perform comprehensive geometrical complexity analysis for a region.
    Optimized to use a single API call instead of separate calls.

    Args:
        region_name: Name of the region for display
        bbox: Bounding box string
        timestamp: ISO-8601 timestamp for analysis
        filter: OSM filter query (default: highway tags)

    Returns:
        DataFrame with combined metrics
    """
    total_start = time.time()

    logger.info(f"=" * 60)
    logger.info(f"Starting analysis for region: {region_name}")
    logger.info(f"Bounding box: {bbox}")
    logger.info(f"=" * 60)

    # Single API call to get geometry data
    data = _call_ohsome_api('geometry', bbox, filter, timestamp, return_type='json')

    if data is None:
        logger.error(f"Failed to extract data for region: {region_name}")
        return None

    features = data.get("features", [])

    # Extract all metrics from features in one pass
    metrics = _extract_comprehensive_metrics(features, bbox)
    node_counts = metrics['node_counts']

    # Build result DataFrame with node statistics
    stats_start = time.time()
    result = _calculate_node_statistics(node_counts, bbox)
    stats_time = time.time() - stats_start

    # Add count and length metrics
    result['road_count'] = metrics['road_count']
    result['cumulative_road_length'] = metrics['cumulative_road_length']

    # Calculate derived metrics
    derived_start = time.time()
    if metrics['road_count'] > 0:
        result['mean_road_length'] = result['cumulative_road_length'] / result['road_count']
        result['mean_distance_between_nodes_total'] = result['cumulative_road_length'] / result['sum']
        result['mean_distance_between_nodes_means'] = result['mean_road_length'] / result['mean']
        result['mean_distance_between_nodes_medians'] = result['mean_road_length'] / result['median']
        result['nodes_per_unit'] = result['sum'] / result['road_count']
    else:
        result['mean_road_length'] = 0
        result['mean_distance_between_nodes_total'] = 0
        result['mean_distance_between_nodes_means'] = 0
        result['mean_distance_between_nodes_medians'] = 0
        result['nodes_per_unit'] = 0
    derived_time = time.time() - derived_start

    total_time = time.time() - total_start
    features_per_sec = metrics['road_count'] / total_time if total_time > 0 else 0

    logger.debug(f"Statistics calculation: {stats_time:.3f}s")
    logger.debug(f"Derived metrics: {derived_time:.3f}s")
    logger.info(f"TOTAL ANALYSIS TIME: {total_time:.2f}s [{metrics['road_count']:,} features @ {features_per_sec:.1f} feat/s]")
    logger.info(f"Analysis complete for region: {region_name}")
    logger.info("=" * 60)

    return result


def plot_node_distribution(bbox, region_name, bins=100, xlim=(0, 70)):
    """
    Plot histogram of node count distribution for a region.

    Args:
        bbox: Bounding box string
        region_name: Name of the region for plot title
        bins: Number of histogram bins
        xlim: X-axis limits tuple
    """
    logger.info(f"Generating node distribution plot for {region_name}")

    node_distribution = get_vertices(bbox, distribution=True)

    if node_distribution is None or len(node_distribution) == 0:
        logger.warning(f"No data available for plotting {region_name}")
        return

    plt.figure(figsize=(10, 6))
    plt.hist(node_distribution, bins=bins)
    plt.xlabel('Number of nodes', weight='bold')
    plt.ylabel('Frequency', weight='bold')
    plt.xlim(xlim)
    plt.title(region_name, fontsize=12)
    plt.suptitle('Nodes per Way Distribution', fontsize=15, weight='bold')
    plt.tight_layout()
    plt.show()


def compare_regions(regions_dict, timestamp="2025-01-01"):
    """
    Compare geometrical complexity metrics across multiple regions.

    Args:
        regions_dict: Dictionary mapping region names to bounding boxes
        timestamp: ISO-8601 timestamp for analysis

    Returns:
        DataFrame with comparison metrics for all regions
    """
    results = []

    for region_name, bbox in regions_dict.items():
        result = analyze_region(region_name, bbox, timestamp)
        if result is not None:  
            result.insert(0, 'region', region_name)
            results.append(result)

    if not results:
        logger.error("No results to compare - all regions failed")
        return None

    logger.info(f"Comparison complete for {len(results)} regions")
    comparison = pd.concat(results, ignore_index=True)
    return comparison


