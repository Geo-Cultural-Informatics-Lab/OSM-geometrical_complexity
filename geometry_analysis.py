"""
Geometry Analysis Functions for OSM Geometrical Complexity

This module provides functions to extract and analyze OpenStreetMap data
focusing on geometrical complexity metrics.
"""

import os
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt
from shapely.geometry import MultiPoint, Polygon, MultiPolygon
from shapely.ops import transform
import pyproj
from math import radians, sin, cos, sqrt, atan2
import time
import geopandas as gpd

from api_helpers import call_ohsome_api, save_to_file, get_element_count, get_user_count, logger


# ============================================================================
# Statistical Processing Functions
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
            total_length += calculate_linestring_length(coords)
            length_calc_time += time.time() - length_start

        elif geom_type == 'MultiLineString':
            total_nodes = sum(len(line) for line in coords)
            node_counts.append(total_nodes)
            geometry_count_time += time.time() - count_start

            length_start = time.time()
            for line in coords:
                total_length += calculate_linestring_length(line)
            length_calc_time += time.time() - length_start

        elif geom_type == 'Polygon':
            # For Polygon, count all nodes and calculate perimeter
            total_nodes = sum(len(ring) for ring in coords)
            node_counts.append(total_nodes)
            geometry_count_time += time.time() - count_start

            length_start = time.time()
            # Calculate perimeter (outer ring only for length calculation)
            total_length += calculate_linestring_length(coords[0])
            length_calc_time += time.time() - length_start

        elif geom_type == 'MultiPolygon':
            # For MultiPolygon, count all nodes and calculate total perimeter
            total_nodes = sum(len(ring) for polygon in coords for ring in polygon)
            node_counts.append(total_nodes)
            geometry_count_time += time.time() - count_start

            length_start = time.time()
            # Calculate perimeter of all outer rings
            for polygon in coords:
                total_length += calculate_linestring_length(polygon[0])
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


def calculate_convex_hull_metrics_vectorized(features, bounds):
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
        return None, None

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

    for idx, feature in enumerate(features):
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
        # Use OSM ID if available, otherwise use feature index
        osm_id = feature["properties"].get("@osmId") or feature["properties"].get("osmID") or feature.get("id")
        way_ids.append(osm_id if osm_id is not None else idx)

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

    # Extract results (metrics only, no geometry to keep CSV small)
    result = gdf_utm[['way_id', 'area_m2', 'convex_hull_m2', 'ratio', 'is_multipolygon', 'inner_ring_count']].copy()

    # Also return original geometries in WGS84 for optional geometry file export
    # This is kept separate so CSV files remain small
    result_geom = gdf[['way_id', 'geometry']].copy()  # gdf is still in WGS84

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

    return result, result_geom


def calculate_convex_hull_metrics(features, bounds, use_vectorized=True):
    """
    Calculate convex hull metrics for polygon features.

    Args:
        features: List of GeoJSON polygon features
        bounds: Bounding box string
        use_vectorized: If True, use geopandas vectorized operations (faster)

    Returns:
        Tuple of (metrics_df, geometry_gdf):
            - metrics_df: DataFrame with area and convex hull metrics
            - geometry_gdf: GeoDataFrame with original geometries (for qualitative sampling)
    """
    if use_vectorized:
        return calculate_convex_hull_metrics_vectorized(features, bounds)

    # Fall back to loop-based implementation
    start_time = time.time()

    if not features:
        logger.warning("No polygon features returned for convex hull calculation")
        return None, None

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
    geom_rows = []  # For storing original geometries

    # Granular timing metrics
    point_extraction_time = 0
    convex_hull_time = 0
    transformation_time = 0
    area_calc_time = 0

    for idx, feature in enumerate(features):
        coords = feature["geometry"]["coordinates"]
        geom_type = feature["geometry"]["type"]

        # Use OSM ID if available, otherwise use feature index
        osm_id = feature["properties"].get("@osmId") or feature["properties"].get("osmID") or feature.get("id")
        way_id = osm_id if osm_id is not None else idx

        # Extract only exterior ring points for convex hull (performance optimization)
        # Also track polygon complexity indicators
        extract_start = time.time()
        if geom_type == "Polygon":
            points = coords[0]  # Only exterior ring
            inner_ring_count = len(coords) - 1  # Number of holes
            is_multipolygon = False
            # Store original geometry
            original_geom = Polygon(coords[0])
        elif geom_type == "MultiPolygon":
            # For MultiPolygon, use all exterior rings (complexity indicator)
            points = [pt for polygon in coords for pt in polygon[0]]
            inner_ring_count = sum(len(polygon) - 1 for polygon in coords)
            is_multipolygon = True
            # Store original geometry
            original_geom = MultiPolygon([Polygon(poly[0]) for poly in coords])
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
            "way_id": way_id,
            "area_m2": geom_m.area,
            "convex_hull_m2": convex_hull_area,
            'ratio': 1 - (geom_m.area / convex_hull_area) if convex_hull_area > 0 else 0,
            'is_multipolygon': is_multipolygon,
            'inner_ring_count': inner_ring_count
        })

        # Store original geometry in WGS84
        geom_rows.append({
            "way_id": way_id,
            "geometry": original_geom
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

    # Return metrics DataFrame and geometry GeoDataFrame
    result = pd.DataFrame(rows)
    result_geom = gpd.GeoDataFrame(geom_rows, geometry='geometry', crs="EPSG:4326")

    return result, result_geom


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
    result = call_ohsome_api('count', bounds, filter, time)

    if result is not None:
        logger.info("Count data successfully retrieved")

        # Save raw JSON if requested
        if path and filename:
            response = call_ohsome_api('count', bounds, filter, time, return_type='json')
            save_to_file(response, path, filename, data_format='json')
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
    result = call_ohsome_api('length', bounds, filter, time)

    if result is not None:
        logger.info("Length data successfully retrieved")

        # Save raw JSON if requested
        if path and filename:
            response = call_ohsome_api('length', bounds, filter, time, return_type='json')
            save_to_file(response, path, filename, data_format='json')
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
    result = call_ohsome_api('area', bounds, filter, time)

    if result is not None:
        logger.info("Area data successfully retrieved")

        # Save raw JSON if requested
        if path and filename:
            response = call_ohsome_api('area', bounds, filter, time, return_type='json')
            save_to_file(response, path, filename, data_format='json')
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
    data = call_ohsome_api('geometry', bounds, filter, time, return_type='json')

    if data is None:
        return None

    features = data.get("features", [])
    node_counts = extract_node_counts(features)

    # Save raw data if requested
    if path and filename and features:
        way_ids = np.fromiter(
            (f['properties']['osmID'] for f in features),
            dtype=int
        )
        raw_data = pd.DataFrame({'way_id': way_ids, 'node_count': node_counts})
        save_to_file(raw_data.to_dict('records'), path, filename, data_format='json')

    # Return raw distribution if requested
    if distribution:
        return node_counts

    # Return statistical summary
    return calculate_node_statistics(node_counts, bounds)


def get_poly_coords(region_name, bounds, filter="type:way and building=*", time_param="2025-01-01",
                    path=None, filename=None, distribution=False, use_vectorized=True,
                    include_counts=True, include_user_count=True):
    """
    Extract polygon coordinates and calculate convex hull metrics.

    Args:
        region_name: Name of the region for reference
        bounds: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        filter: OSM filter query (default: building tags)
        time_param: ISO-8601 timestamp (default: 2025-01-01)
        path: Optional directory path to save results
        filename: Optional filename for saved results
        distribution: If True, return full DataFrame instead of summary statistics
        use_vectorized: If True, use geopandas vectorized operations (default, much faster)
        include_counts: If True, include actual building count from API (default: True)
        include_user_count: If True, include contributor count from API (default: True)

    Returns:
        DataFrame with convex hull metrics or summary statistics
    """
    start_time = time.time()

    data = call_ohsome_api('geometry', bounds, filter, time_param, return_type='json')

    if data is None:
        return None

    features = data.get("features", [])
    df, geom_gdf = calculate_convex_hull_metrics(features, bounds, use_vectorized=use_vectorized)

    if df is None:
        return None

    cols = df.columns.tolist()
    df["region_name"] = region_name
    df["bbox"] = bounds
    df = df[["region_name", "bbox"] + cols]

    # Return full distribution if requested
    if distribution:
        print(f"Total get_poly_coords time: {time.time() - start_time:.2f}s\n")
        return df

    # Get building and user counts from API
    building_count = None
    user_count = None

    if include_counts:
        logger.info("Fetching building count from API...")
        building_count = get_element_count(bounds, filter, time_param)

    if include_user_count:
        logger.info("Fetching user/contributor count from API...")
        user_count = get_user_count(bounds, filter, time_param)

    # Return summary statistics
    summary_statistics = pd.DataFrame({
        'region': region_name,
        'bbox': [bounds],
        'building_count': [building_count if building_count is not None else len(df)],
        'user_count': [user_count],
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
        save_to_file(df, path, filename, data_format='csv')
        save_to_file(summary_statistics, path, os.path.basename(filename) + "_summary.csv", data_format='csv')

        # Save geometry file for qualitative sampling (as GeoJSON)
        if geom_gdf is not None and len(geom_gdf) > 0:
            geom_filename = os.path.basename(filename).replace('.csv', '_geom.geojson')
            geom_path = os.path.join(path, geom_filename)
            geom_gdf.to_file(geom_path, driver='GeoJSON')
            logger.info(f"Saved geometry file: {geom_filename}")

    print(f"Total get_poly_coords time: {time.time() - start_time:.2f}s\n")

    return summary_statistics


def get_poly_coords_chunked(region_name, bounds, filter="type:way and building=*",
                            time_param="2025-01-01", path=None, filename=None,
                            chunk_size_km=50, use_adaptive_chunking=True,
                            max_features_per_chunk=50000, building_density=2000,
                            resume=True, cleanup_after=True):
    """
    Extract polygon coordinates using spatial chunking for large regions.

    This function automatically splits large bounding boxes into smaller chunks
    to prevent API timeouts and memory issues. Results are saved incrementally
    to disk and aggregated at the end.

    Args:
        region_name: Name of the region for reference
        bounds: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        filter: OSM filter query (default: building tags)
        time_param: ISO-8601 timestamp (default: 2025-01-01)
        path: Directory path to save results (required for chunked processing)
        filename: Filename for final results (required for chunked processing)
        chunk_size_km: Fixed chunk size in km (default: 50, used if not adaptive)
        use_adaptive_chunking: If True, estimate optimal chunk size (default: True)
        max_features_per_chunk: Target max features per chunk for adaptive sizing
        building_density: Estimated buildings per km² for adaptive sizing
        resume: If True, resume from previous incomplete run (default: True)
        cleanup_after: If True, remove chunk files after aggregation (default: True)

    Returns:
        DataFrame with summary statistics (same format as get_poly_coords)

    Example:
        >>> # Analyze entire UK with automatic chunking
        >>> uk_bbox = get_bbox_by_city("London", radius_km=500)
        >>> summary = get_poly_coords_chunked(
        ...     "uk", uk_bbox,
        ...     path="./data",
        ...     filename="uk_buildings.csv"
        ... )
    """
    import os
    from chunking_utils import (
        split_bbox_into_grid, adaptive_chunk_split,
        bbox_area_km2, print_chunk_summary
    )
    from api_helpers import (
        save_chunk_data, load_and_aggregate_chunks,
        save_processing_status, load_processing_status, cleanup_chunks
    )

    start_time = time.time()

    # Validate required parameters
    if not path or not filename:
        logger.error("path and filename are required for chunked processing")
        return None

    logger.info(f"=" * 80)
    logger.info(f"Starting chunked analysis for region: {region_name}")
    logger.info(f"Bounding box: {bounds}")
    logger.info(f"Area: {bbox_area_km2(bounds):.0f} km²")
    logger.info(f"=" * 80)

    # Generate chunks
    if use_adaptive_chunking:
        logger.info("Using adaptive chunking based on building density estimate")
        chunks = adaptive_chunk_split(
            bounds,
            max_features_per_chunk=max_features_per_chunk,
            default_density=building_density
        )
    else:
        logger.info(f"Using fixed chunk size: {chunk_size_km} km")
        chunks = split_bbox_into_grid(bounds, chunk_size_km=chunk_size_km)

    print_chunk_summary(chunks)

    # Check for existing progress
    status_file = os.path.join(path, f".chunk_status_{region_name}.json")
    completed_chunks = []

    if resume:
        status = load_processing_status(status_file)
        if status:
            completed_chunks = status.get('completed_chunks', [])
            logger.info(f"Resuming from previous run: {len(completed_chunks)}/{len(chunks)} chunks already completed")

    # Process each chunk
    logger.info(f"\nProcessing {len(chunks)} chunks...")
    failed_chunks = []

    for i, chunk in enumerate(chunks):
        chunk_id = chunk['chunk_id']

        # Skip if already completed
        if chunk_id in completed_chunks:
            logger.debug(f"Skipping chunk {chunk_id} (already completed)")
            continue

        logger.info(f"\n[{i+1}/{len(chunks)}] Processing chunk {chunk_id} (row={chunk['row']}, col={chunk['col']})")
        logger.debug(f"  Bbox: {chunk['bbox']}")
        logger.debug(f"  Center: ({chunk['center_lat']:.4f}, {chunk['center_lon']:.4f})")

        try:
            # Call get_poly_coords for this chunk (returns summary statistics)
            chunk_result = get_poly_coords(
                region_name=f"{region_name}_chunk_{chunk_id}",
                bounds=chunk['bbox'],
                filter=filter,
                time_param=time_param,
                path=path,  # This will save the raw data
                filename=filename,  # Raw data will be appended
                distribution=False,  # We want summary stats per chunk
                use_vectorized=True
            )

            if chunk_result is not None:
                # Save chunk summary with metadata
                chunk_result['chunk_id'] = chunk_id
                chunk_result['chunk_row'] = chunk['row']
                chunk_result['chunk_col'] = chunk['col']

                save_chunk_data(
                    chunk_result,
                    region_name,
                    chunk_id,
                    path,
                    filename + "_summary.csv"
                )

                completed_chunks.append(chunk_id)
                logger.info(f"  ✓ Chunk {chunk_id} completed successfully")
            else:
                logger.warning(f"  ✗ Chunk {chunk_id} returned no data")
                failed_chunks.append(chunk_id)

        except Exception as e:
            logger.error(f"  ✗ Chunk {chunk_id} failed: {str(e)}")
            failed_chunks.append(chunk_id)
            continue

        # Save progress after each chunk
        save_processing_status(
            status_file,
            completed_chunks,
            len(chunks),
            metadata={
                'region_name': region_name,
                'bounds': bounds,
                'failed_chunks': failed_chunks
            }
        )

    # Report results
    logger.info(f"\n" + "=" * 80)
    logger.info(f"Chunk processing complete:")
    logger.info(f"  Successful: {len(completed_chunks)}/{len(chunks)}")
    logger.info(f"  Failed: {len(failed_chunks)}/{len(chunks)}")
    if failed_chunks:
        logger.warning(f"  Failed chunk IDs: {', '.join(failed_chunks)}")
    logger.info(f"=" * 80)

    # Aggregate chunk summaries
    logger.info("\nAggregating chunk summaries...")
    chunk_summaries = load_and_aggregate_chunks(path, filename + "_summary.csv")

    if chunk_summaries is None or len(chunk_summaries) == 0:
        logger.error("Failed to load chunk summaries for aggregation")
        return None

    # Calculate overall summary statistics from chunk summaries
    # We need to properly aggregate the statistics (can't just average means)
    import numpy as np

    final_summary = pd.DataFrame({
        'region': [region_name],
        'bbox': [bounds],
        'num_chunks': [len(completed_chunks)],
        'failed_chunks': [len(failed_chunks)],
        # Building and user counts - sum across chunks
        'building_count': [chunk_summaries['building_count'].sum() if 'building_count' in chunk_summaries.columns else None],
        'user_count': [chunk_summaries['user_count'].sum() if 'user_count' in chunk_summaries.columns else None],
        # For sums, we sum across chunks
        'sum_chull_area': [chunk_summaries['sum_chull_area'].sum()],
        'sum_area': [chunk_summaries['sum_area'].sum()],
        'sum_ratio': [chunk_summaries['sum_ratio'].sum()],
        'total_inner_rings': [chunk_summaries['total_inner_rings'].sum()],
        'multipolygon_count': [chunk_summaries['multipolygon_count'].sum()],
        # For means, we take weighted average (weight by feature count if available)
        # For now, simple mean of chunk means (approximation)
        'mean_chull_area': [chunk_summaries['mean_chull_area'].mean()],
        'mean_area': [chunk_summaries['mean_area'].mean()],
        'mean_ratio': [chunk_summaries['mean_ratio'].mean()],
        'mean_inner_rings': [chunk_summaries['mean_inner_rings'].mean()],
        'multipolygon_ratio': [chunk_summaries['multipolygon_ratio'].mean()],
        # For medians, take median of chunk medians (approximation)
        'median_chull_area': [chunk_summaries['median_chull_area'].median()],
        'median_area': [chunk_summaries['median_area'].median()],
        'median_ratio': [chunk_summaries['median_ratio'].median()],
    })

    # Save final summary
    summary_path = os.path.join(path, os.path.splitext(filename)[0] + "_final_summary.csv")
    final_summary.to_csv(summary_path, index=False)
    logger.info(f"Final summary saved to {summary_path}")

    # Cleanup chunk files if requested
    if cleanup_after:
        logger.info("Cleaning up chunk files...")
        cleanup_chunks(path, filename + "_summary.csv", keep_status=True)

    total_time = time.time() - start_time
    logger.info(f"\nTotal chunked analysis time: {total_time:.2f}s ({total_time/60:.1f} minutes)")
    logger.info(f"Average time per chunk: {total_time/len(completed_chunks):.2f}s")

    return final_summary


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
    data = call_ohsome_api('geometry', bbox, filter, timestamp, return_type='json')

    if data is None:
        logger.error(f"Failed to extract data for region: {region_name}")
        return None

    features = data.get("features", [])

    # Extract all metrics from features in one pass
    metrics = extract_comprehensive_metrics(features, bbox)
    node_counts = metrics['node_counts']

    # Build result DataFrame with node statistics
    stats_start = time.time()
    result = calculate_node_statistics(node_counts, bbox)
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
