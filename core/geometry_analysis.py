"""
Geometry Analysis Functions for OSM Geometrical Complexity

This module provides backward-compatible wrapper functions that delegate to
the new modular architecture (metrics.py, ohsome_client.py, analyzer.py).
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from utils.api_helpers import logger

# Import from new modules
from core.metrics import (
    calculate_convex_hull_metrics,
    calculate_node_statistics,
    extract_comprehensive_metrics,
    extract_node_counts
)
from core.ohsome_client import OhsomeClient
from core.analyzer import (
    analyze_region_buildings as _analyze_region_buildings,
    analyze_region_buildings_chunked as _analyze_region_buildings_chunked,
    analyze_region_roads as _analyze_region_roads,
    compare_regions as _compare_regions
)


# ============================================================================
# Backward Compatibility Layer
# These functions maintain the original API for existing code
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
    client = OhsomeClient()
    result = client.query_count_timeseries(bounds, filter, time)

    if result is not None:
        logger.info("Count data successfully retrieved")
        if path and filename:
            from utils.api_helpers import save_to_file
            data = client._call_endpoint('count', bounds, filter, time, return_type='json')
            if data:
                save_to_file(data, path, filename, data_format='json')
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
    client = OhsomeClient()
    result = client.query_length(bounds, filter, time)

    if result is not None:
        logger.info("Length data successfully retrieved")
        if path and filename:
            from utils.api_helpers import save_to_file
            data = client._call_endpoint('length', bounds, filter, time, return_type='json')
            if data:
                save_to_file(data, path, filename, data_format='json')
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
    client = OhsomeClient()
    result = client.query_area(bounds, filter, time)

    if result is not None:
        logger.info("Area data successfully retrieved")
        if path and filename:
            from utils.api_helpers import save_to_file
            data = client._call_endpoint('area', bounds, filter, time, return_type='json')
            if data:
                save_to_file(data, path, filename, data_format='json')
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
    client = OhsomeClient()
    data = client.query_geometry(bounds, filter, time)

    if data is None:
        return None

    features = data.get("features", [])
    node_counts = extract_node_counts(features)

    # Save raw data if requested
    if path and filename and features:
        from utils.api_helpers import save_to_file
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
                    include_counts=True, include_user_count=True, resume=True):
    """
    Extract polygon coordinates and calculate convex hull metrics.

    DEPRECATED: This function is a backward compatibility wrapper.
    Use analyzer.analyze_region_buildings() for new code.

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
        resume: If True, load existing summary data if available (default: True)

    Returns:
        DataFrame with convex hull metrics or summary statistics
    """
    return _analyze_region_buildings(
        region_name=region_name,
        bounds=bounds,
        filter=filter,
        timestamp=time_param,
        path=path,
        filename=filename,
        distribution=distribution,
        use_vectorized=use_vectorized,
        include_counts=include_counts,
        include_user_count=include_user_count,
        resume=resume
    )


def get_poly_coords_chunked(region_name, bounds, filter="type:way and building=*",
                            time_param="2025-01-01", path=None, filename=None,
                            chunk_size_km=50, use_adaptive_chunking=True,
                            max_features_per_chunk=50000, building_density=2000,
                            resume=True, cleanup_after=True):
    """
    Extract polygon coordinates using spatial chunking for large regions.

    DEPRECATED: This function is a backward compatibility wrapper.
    Use analyzer.analyze_region_buildings_chunked() for new code.

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
    """
    return _analyze_region_buildings_chunked(
        region_name=region_name,
        bounds=bounds,
        filter=filter,
        timestamp=time_param,
        path=path,
        filename=filename,
        chunk_size_km=chunk_size_km,
        use_adaptive_chunking=use_adaptive_chunking,
        max_features_per_chunk=max_features_per_chunk,
        building_density=building_density,
        resume=resume,
        cleanup_after=cleanup_after
    )


def analyze_region(region_name, bbox, timestamp="2025-01-01", filter="type:way and highway=*"):
    """
    Perform comprehensive geometrical complexity analysis for a region.

    DEPRECATED: This function is a backward compatibility wrapper.
    Use analyzer.analyze_region_roads() for new code.

    Args:
        region_name: Name of the region for display
        bbox: Bounding box string
        timestamp: ISO-8601 timestamp for analysis
        filter: OSM filter query (default: highway tags)

    Returns:
        DataFrame with combined metrics
    """
    return _analyze_region_roads(region_name, bbox, timestamp, filter)


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

    DEPRECATED: This function is a backward compatibility wrapper.
    Use analyzer.compare_regions() for new code.

    Args:
        regions_dict: Dictionary mapping region names to bounding boxes
        timestamp: ISO-8601 timestamp for analysis

    Returns:
        DataFrame with comparison metrics for all regions
    """
    return _compare_regions(regions_dict, timestamp)


# ============================================================================
# Compatibility Imports
# Export these for backward compatibility
# ============================================================================
__all__ = [
    'calculate_convex_hull_metrics',
    'calculate_node_statistics',
    'extract_comprehensive_metrics',
    'extract_node_counts',
    'get_count',
    'get_len',
    'get_area',
    'get_vertices',
    'get_poly_coords',
    'get_poly_coords_chunked',
    'analyze_region',
    'plot_node_distribution',
    'compare_regions',
]
