"""
Metrics - Pure Geometry Calculations

This module contains pure functions for calculating geometrical complexity metrics.
No API calls, no file I/O - just calculations.
"""

import numpy as np
import pandas as pd
import geopandas as gpd
from scipy import stats
from shapely.geometry import MultiPoint, Polygon, MultiPolygon
from shapely.ops import transform
import pyproj
from math import radians, sin, cos, sqrt, atan2
import time
import logging

logger = logging.getLogger('geometrical_complexity_analysis')


# ============================================================================
# Node Statistics
# ============================================================================

def calculate_node_statistics(node_counts, bounds):
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


def extract_node_counts(features):
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


# ============================================================================
# Length Calculations
# ============================================================================

def calculate_linestring_length(coords):
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


def extract_comprehensive_metrics(features, bounds):
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

    for feature in features:
        geom_type = feature['geometry']['type']
        coords = feature['geometry']['coordinates']

        if geom_type == 'LineString':
            node_counts.append(len(coords))
            total_length += calculate_linestring_length(coords)

        elif geom_type == 'MultiLineString':
            total_nodes = sum(len(line) for line in coords)
            node_counts.append(total_nodes)
            for line in coords:
                total_length += calculate_linestring_length(line)

        elif geom_type == 'Polygon':
            total_nodes = sum(len(ring) for ring in coords)
            node_counts.append(total_nodes)
            total_length += calculate_linestring_length(coords[0])

        elif geom_type == 'MultiPolygon':
            total_nodes = sum(len(ring) for polygon in coords for ring in polygon)
            node_counts.append(total_nodes)
            for polygon in coords:
                total_length += calculate_linestring_length(polygon[0])

    total_time = time.time() - start_time
    num_features = len(node_counts)
    features_per_sec = num_features / total_time if total_time > 0 else 0

    logger.debug(f"Metrics extraction: {total_time:.2f}s [{num_features:,} features @ {features_per_sec:.1f} feat/s]")
    logger.info(f"Metrics extraction complete: {num_features} features processed in {total_time:.2f}s")

    return {
        'node_counts': np.array(node_counts, dtype=int),
        'road_count': len(features),
        'cumulative_road_length': total_length
    }


# ============================================================================
# Convex Hull Calculations
# ============================================================================

def calculate_convex_hull_metrics_vectorized(features, bounds):
    """
    Calculate convex hull metrics using vectorized geopandas operations.

    Args:
        features: List of GeoJSON polygon features
        bounds: Bounding box string

    Returns:
        Tuple of (metrics_df, geometry_gdf)
    """
    start_time = time.time()

    if not features:
        logger.warning("No polygon features returned for convex hull calculation")
        return None, None

    logger.info(f"Calculating convex hull metrics for {len(features)} polygon features (vectorized)")

    # Calculate UTM projection parameters
    min_lon, min_lat, max_lon, max_lat = map(float, bounds.split(','))
    center_lon = (min_lon + max_lon) / 2
    utm_zone = int((center_lon + 180) / 6) + 1
    utm_crs = f"+proj=utm +zone={utm_zone} +datum=WGS84"

    # Extract metadata and create exterior-ring-only geometries
    geometries = []
    way_ids = []
    is_multipolygons = []
    inner_ring_counts = []

    for idx, feature in enumerate(features):
        coords = feature["geometry"]["coordinates"]
        geom_type = feature["geometry"]["type"]

        if geom_type == "Polygon":
            geom = Polygon(coords[0])
            inner_ring_counts.append(len(coords) - 1)
            is_multipolygons.append(False)
        elif geom_type == "MultiPolygon":
            geom = MultiPolygon([Polygon(poly[0]) for poly in coords])
            inner_ring_counts.append(sum(len(poly) - 1 for poly in coords))
            is_multipolygons.append(True)
        else:
            continue

        geometries.append(geom)
        osm_id = feature["properties"].get("@osmId") or feature["properties"].get("osmID") or feature.get("id")
        way_ids.append(osm_id if osm_id is not None else idx)

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame({
        'way_id': way_ids,
        'is_multipolygon': is_multipolygons,
        'inner_ring_count': inner_ring_counts
    }, geometry=geometries, crs="EPSG:4326")

    # Vectorized coordinate transformation
    gdf_utm = gdf.to_crs(utm_crs)

    # Vectorized convex hull computation
    gdf_utm['convex_hull_geom'] = gdf_utm.geometry.convex_hull

    # Vectorized area calculations
    gdf_utm['area_m2'] = gdf_utm.geometry.area
    gdf_utm['convex_hull_m2'] = gdf_utm['convex_hull_geom'].area
    gdf_utm['ratio'] = 1 - (gdf_utm['area_m2'] / gdf_utm['convex_hull_m2'])
    gdf_utm['ratio'] = gdf_utm['ratio'].fillna(0)

    # Extract results
    result = gdf_utm[['way_id', 'area_m2', 'convex_hull_m2', 'ratio', 'is_multipolygon', 'inner_ring_count']].copy()
    result_geom = gdf[['way_id', 'geometry']].copy()

    total_time = time.time() - start_time
    features_per_sec = len(geometries) / total_time if total_time > 0 else 0

    logger.debug(f"Convex hull calculation (VECTORIZED): {total_time:.2f}s [{len(geometries):,} features @ {features_per_sec:.1f} feat/s]")
    logger.info(f"Convex hull metrics calculated for {len(geometries)} features in {total_time:.2f}s")

    return result, result_geom


def calculate_convex_hull_metrics_loop(features, bounds):
    """
    Calculate convex hull metrics using loop-based approach (fallback).

    Args:
        features: List of GeoJSON polygon features
        bounds: Bounding box string

    Returns:
        Tuple of (metrics_df, geometry_gdf)
    """
    start_time = time.time()

    if not features:
        logger.warning("No polygon features returned for convex hull calculation")
        return None, None

    logger.info(f"Calculating convex hull metrics for {len(features)} polygon features (loop-based)")

    # Calculate UTM projection parameters
    min_lon, min_lat, max_lon, max_lat = map(float, bounds.split(','))
    center_lon = (min_lon + max_lon) / 2
    utm_zone = int((center_lon + 180) / 6) + 1

    proj = pyproj.Transformer.from_crs(
        "epsg:4326",
        f"+proj=utm +zone={utm_zone} +datum=WGS84",
        always_xy=True
    ).transform

    rows = []
    geom_rows = []

    for idx, feature in enumerate(features):
        coords = feature["geometry"]["coordinates"]
        geom_type = feature["geometry"]["type"]

        osm_id = feature["properties"].get("@osmId") or feature["properties"].get("osmID") or feature.get("id")
        way_id = osm_id if osm_id is not None else idx

        if geom_type == "Polygon":
            points = coords[0]
            inner_ring_count = len(coords) - 1
            is_multipolygon = False
            original_geom = Polygon(coords[0])
        elif geom_type == "MultiPolygon":
            points = [pt for polygon in coords for pt in polygon[0]]
            inner_ring_count = sum(len(polygon) - 1 for polygon in coords)
            is_multipolygon = True
            original_geom = MultiPolygon([Polygon(poly[0]) for poly in coords])
        else:
            continue

        geom = MultiPoint(points).convex_hull
        geom_m = transform(proj, geom)
        convex_hull_area = geom_m.area

        rows.append({
            "way_id": way_id,
            "area_m2": geom_m.area,
            "convex_hull_m2": convex_hull_area,
            'ratio': 1 - (geom_m.area / convex_hull_area) if convex_hull_area > 0 else 0,
            'is_multipolygon': is_multipolygon,
            'inner_ring_count': inner_ring_count
        })

        geom_rows.append({
            "way_id": way_id,
            "geometry": original_geom
        })

    total_time = time.time() - start_time
    num_features = len(rows)
    features_per_sec = num_features / total_time if total_time > 0 else 0

    logger.debug(f"Convex hull calculation (LOOP): {total_time:.2f}s [{num_features:,} features @ {features_per_sec:.1f} feat/s]")
    logger.info(f"Convex hull metrics calculated for {num_features} features in {total_time:.2f}s")

    result = pd.DataFrame(rows)
    result_geom = gpd.GeoDataFrame(geom_rows, geometry='geometry', crs="EPSG:4326")

    return result, result_geom


def calculate_convex_hull_metrics(features, bounds, use_vectorized=True):
    """
    Calculate convex hull metrics for polygon features.

    Args:
        features: List of GeoJSON polygon features
        bounds: Bounding box string
        use_vectorized: If True, use geopandas vectorized operations (faster)

    Returns:
        Tuple of (metrics_df, geometry_gdf)
    """
    if use_vectorized:
        return calculate_convex_hull_metrics_vectorized(features, bounds)
    else:
        return calculate_convex_hull_metrics_loop(features, bounds)
