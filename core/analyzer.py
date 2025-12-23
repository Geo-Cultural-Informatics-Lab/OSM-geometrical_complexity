"""
Analyzer - Main Orchestration Logic

This module orchestrates the analysis workflow, combining API calls,
metrics calculations, chunking, and file operations.
"""

import os
import numpy as np
import pandas as pd
import time
import logging

from core.ohsome_client import OhsomeClient
from core.metrics import (
    calculate_convex_hull_metrics,
    extract_comprehensive_metrics,
    calculate_node_statistics
)
from utils.resume_manager import ResumeManager

logger = logging.getLogger('geometrical_complexity_analysis')


def analyze_region_buildings(region_name, bounds, filter="type:way and building=*",
                             timestamp="2025-01-01", path=None, filename=None,
                             distribution=False, use_vectorized=True,
                             include_counts=True, include_user_count=True, resume=True):
    """
    Analyze building geometries for a region.

    Args:
        region_name: Name of the region for reference
        bounds: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        filter: OSM filter query (default: building tags)
        timestamp: ISO-8601 timestamp (default: 2025-01-01)
        path: Optional directory path to save results
        filename: Optional filename for saved results
        distribution: If True, return full DataFrame instead of summary
        use_vectorized: If True, use geopandas vectorized operations (faster)
        include_counts: If True, include actual building count from API
        include_user_count: If True, include contributor count from API
        resume: If True, load existing summary data if available

    Returns:
        DataFrame with convex hull metrics or summary statistics
    """
    start_time = time.time()

    # Check if summary file already exists (for resume capability)
    # Use region_name to ensure each chunk/region has unique summary file
    if resume and path and filename and not distribution:
        # Create summary filename based on region_name to avoid conflicts between chunks
        summary_filename = f"{region_name}_summary.csv"
        summary_file = os.path.join(path, summary_filename)
        if os.path.exists(summary_file):
            logger.info(f"Loading existing summary data from {summary_filename}")
            try:
                existing_summary = pd.read_csv(summary_file)
                logger.info(f"Loaded cached data - skipping API calls")
                return existing_summary
            except Exception as e:
                logger.warning(f"Failed to load existing summary: {e}, will re-query API")

    # Query Ohsome API for geometry data
    client = OhsomeClient()
    data = client.query_geometry(bounds, filter, timestamp)

    if data is None:
        return None

    features = data.get("features", [])

    # Handle empty chunks (no buildings found)
    if not features:
        logger.info(f"No features found in {region_name} - creating empty summary")

        # Return empty summary with zero counts
        empty_summary = pd.DataFrame({
            'region': [region_name],
            'bbox': [bounds],
            'building_count': [0],
            'user_count': [0],
            'sum_chull_area': [0.0],
            'mean_chull_area': [0.0],
            'median_chull_area': [0.0],
            'sum_area': [0.0],
            'mean_area': [0.0],
            'median_area': [0.0],
            'sum_ratio': [0.0],
            'mean_ratio': [0.0],
            'median_ratio': [0.0],
            'multipolygon_count': [0],
            'multipolygon_ratio': [0.0],
            'total_inner_rings': [0],
            'mean_inner_rings': [0.0]
        })

        # Save the empty summary
        if path and filename:
            os.makedirs(path, exist_ok=True)
            summary_filename = f"{region_name}_summary.csv"
            summary_path = os.path.join(path, summary_filename)
            empty_summary.to_csv(summary_path, index=False)
            logger.info(f"Saved empty summary to {summary_filename}")

        return empty_summary

    df, geom_gdf = calculate_convex_hull_metrics(features, bounds, use_vectorized=use_vectorized)

    if df is None:
        # This should not happen if features exist, but handle it
        logger.error(f"Failed to calculate metrics for {region_name}")
        return None

    # Add region metadata
    cols = df.columns.tolist()
    df["region_name"] = region_name
    df["bbox"] = bounds
    df = df[["region_name", "bbox"] + cols]

    # Return full distribution if requested
    if distribution:
        print(f"Total analysis time: {time.time() - start_time:.2f}s\n")
        return df

    # Get building and user counts from API
    building_count = None
    user_count = None

    if include_counts:
        logger.info("Fetching building count from API...")
        building_count = client.query_element_count(bounds, filter, timestamp)

    if include_user_count:
        logger.info("Fetching user/contributor count from API...")
        user_count = client.query_user_count(bounds, filter, timestamp)

    # Calculate summary statistics
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

    # Save raw data if requested
    if path and filename:
        os.makedirs(path, exist_ok=True)
        file_path = os.path.join(path, filename)
        df.to_csv(file_path, index=False)
        logger.info(f"Saved raw data to {filename}")

        # Save summary using region_name to ensure unique file per chunk/region
        summary_filename = f"{region_name}_summary.csv"
        summary_path = os.path.join(path, summary_filename)
        summary_statistics.to_csv(summary_path, index=False)
        logger.info(f"Saved summary to {summary_filename}")

        # Save geometry file for qualitative sampling (as GeoJSON)
        if geom_gdf is not None and len(geom_gdf) > 0:
            geom_filename = os.path.basename(filename).replace('.csv', '_geom.geojson')
            geom_path = os.path.join(path, geom_filename)
            geom_gdf.to_file(geom_path, driver='GeoJSON')
            logger.info(f"Saved geometry file: {geom_filename}")

    print(f"Total analysis time: {time.time() - start_time:.2f}s\n")
    return summary_statistics


def analyze_region_buildings_chunked(region_name, bounds, filter="type:way and building=*",
                                     timestamp="2025-01-01", path=None, filename=None,
                                     chunk_size_km=50, use_adaptive_chunking=True,
                                     max_features_per_chunk=50000, building_density=2000,
                                     resume=True, cleanup_after=True):
    """
    Analyze building geometries using spatial chunking for large regions.

    This function automatically splits large bounding boxes into smaller chunks
    to prevent API timeouts and memory issues. Results are saved incrementally.

    Args:
        region_name: Name of the region for reference
        bounds: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        filter: OSM filter query (default: building tags)
        timestamp: ISO-8601 timestamp (default: 2025-01-01)
        path: Directory path to save results (required)
        filename: Filename for final results (required)
        chunk_size_km: Fixed chunk size in km (used if not adaptive)
        use_adaptive_chunking: If True, estimate optimal chunk size
        max_features_per_chunk: Target max features per chunk for adaptive sizing
        building_density: Estimated buildings per km² for adaptive sizing
        resume: If True, resume from previous incomplete run
        cleanup_after: If True, remove chunk files after aggregation

    Returns:
        DataFrame with summary statistics
    """
    from utils.chunking_utils import (
        split_bbox_into_grid, adaptive_chunk_split,
        bbox_area_km2, print_chunk_summary
    )
    from utils.api_helpers import save_chunk_data, load_and_aggregate_chunks, cleanup_chunks

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

    # Initialize resume manager
    resume_mgr = ResumeManager(path, f"chunk_{region_name}")
    resume_mgr.set_total(len(chunks))

    # Process each chunk
    logger.info(f"\nProcessing {len(chunks)} chunks...")
    failed_chunks = []

    for i, chunk in enumerate(chunks):
        chunk_id = chunk['chunk_id']

        # Skip if already completed
        if resume_mgr.is_completed(chunk_id):
            logger.debug(f"Skipping chunk {chunk_id} (already completed)")
            continue

        logger.info(f"\n[{i+1}/{len(chunks)}] Processing chunk {chunk_id} (row={chunk['row']}, col={chunk['col']})")
        logger.debug(f"  Bbox: {chunk['bbox']}")

        try:
            # Analyze this chunk
            chunk_result = analyze_region_buildings(
                region_name=f"{region_name}_chunk_{chunk_id}",
                bounds=chunk['bbox'],
                filter=filter,
                timestamp=timestamp,
                path=path,
                filename=filename,
                distribution=False,
                use_vectorized=True
            )

            if chunk_result is not None:
                # Add chunk metadata
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

                resume_mgr.mark_completed(chunk_id)
                logger.info(f"  ✓ Chunk {chunk_id} completed successfully")
            else:
                logger.warning(f"  ✗ Chunk {chunk_id} returned no data")
                resume_mgr.mark_failed(chunk_id, "No data returned")
                failed_chunks.append(chunk_id)

        except Exception as e:
            logger.error(f"  ✗ Chunk {chunk_id} failed: {str(e)}")
            resume_mgr.mark_failed(chunk_id, str(e))
            failed_chunks.append(chunk_id)
            continue

    # Report results
    logger.info(f"\n" + "=" * 80)
    logger.info(f"Chunk processing complete:")
    logger.info(f"  Successful: {resume_mgr.get_completed_count()}/{len(chunks)}")
    logger.info(f"  Failed: {len(failed_chunks)}/{len(chunks)}")
    if failed_chunks:
        logger.warning(f"  Failed chunk IDs: {', '.join(failed_chunks)}")
    logger.info(f"=" * 80)

    # Check if final summary already exists (for resume capability)
    summary_path = os.path.join(path, os.path.splitext(filename)[0] + "_final_summary.csv")
    if resume and os.path.exists(summary_path):
        logger.info(f"Loading existing final summary from {os.path.basename(summary_path)}")
        try:
            existing_summary = pd.read_csv(summary_path)
            logger.info(f"Loaded cached data - skipping aggregation")
            logger.info(f"Total processing time: {time.time() - start_time:.2f}s")
            return existing_summary
        except Exception as e:
            logger.warning(f"Failed to load existing summary: {e}, will re-aggregate")

    # Aggregate chunk summaries
    logger.info("\nAggregating chunk summaries...")
    chunk_summaries = load_and_aggregate_chunks(path, filename + "_summary.csv")

    if chunk_summaries is None or len(chunk_summaries) == 0:
        logger.error("Failed to load chunk summaries for aggregation")
        return None

    # Calculate overall summary statistics
    final_summary = pd.DataFrame({
        'region': [region_name],
        'bbox': [bounds],
        'num_chunks': [resume_mgr.get_completed_count()],
        'failed_chunks': [len(failed_chunks)],
        'building_count': [chunk_summaries['building_count'].sum() if 'building_count' in chunk_summaries.columns else None],
        'user_count': [chunk_summaries['user_count'].sum() if 'user_count' in chunk_summaries.columns else None],
        'sum_chull_area': [chunk_summaries['sum_chull_area'].sum()],
        'sum_area': [chunk_summaries['sum_area'].sum()],
        'sum_ratio': [chunk_summaries['sum_ratio'].sum()],
        'total_inner_rings': [chunk_summaries['total_inner_rings'].sum()],
        'multipolygon_count': [chunk_summaries['multipolygon_count'].sum()],
        'mean_chull_area': [chunk_summaries['mean_chull_area'].mean()],
        'mean_area': [chunk_summaries['mean_area'].mean()],
        'mean_ratio': [chunk_summaries['mean_ratio'].mean()],
        'mean_inner_rings': [chunk_summaries['mean_inner_rings'].mean()],
        'multipolygon_ratio': [chunk_summaries['multipolygon_ratio'].mean()],
        'median_chull_area': [chunk_summaries['median_chull_area'].median()],
        'median_area': [chunk_summaries['median_area'].median()],
        'median_ratio': [chunk_summaries['median_ratio'].median()],
    })

    # Save final summary
    final_summary.to_csv(summary_path, index=False)
    logger.info(f"Final summary saved to {summary_path}")

    # Cleanup
    if cleanup_after:
        logger.info("Cleaning up chunk files...")
        cleanup_chunks(path, filename + "_summary.csv", keep_status=True)

    resume_mgr.cleanup()

    total_time = time.time() - start_time
    logger.info(f"\nTotal chunked analysis time: {total_time:.2f}s ({total_time/60:.1f} minutes)")
    logger.info(f"Average time per chunk: {total_time/resume_mgr.get_completed_count():.2f}s")

    return final_summary


def analyze_region_roads(region_name, bbox, timestamp="2025-01-01", filter="type:way and highway=*"):
    """
    Perform comprehensive geometrical complexity analysis for roads in a region.

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

    # Query Ohsome API
    client = OhsomeClient()
    data = client.query_geometry(bbox, filter, timestamp)

    if data is None:
        logger.error(f"Failed to extract data for region: {region_name}")
        return None

    features = data.get("features", [])

    # Extract all metrics
    metrics = extract_comprehensive_metrics(features, bbox)
    node_counts = metrics['node_counts']

    # Build result DataFrame
    result = calculate_node_statistics(node_counts, bbox)

    # Add count and length metrics
    result['road_count'] = metrics['road_count']
    result['cumulative_road_length'] = metrics['cumulative_road_length']

    # Calculate derived metrics
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

    total_time = time.time() - total_start
    features_per_sec = metrics['road_count'] / total_time if total_time > 0 else 0

    logger.info(f"TOTAL ANALYSIS TIME: {total_time:.2f}s [{metrics['road_count']:,} features @ {features_per_sec:.1f} feat/s]")
    logger.info(f"Analysis complete for region: {region_name}")
    logger.info("=" * 60)

    return result


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
        result = analyze_region_roads(region_name, bbox, timestamp)
        if result is not None:
            result.insert(0, 'region', region_name)
            results.append(result)

    if not results:
        logger.error("No results to compare - all regions failed")
        return None

    logger.info(f"Comparison complete for {len(results)} regions")
    comparison = pd.concat(results, ignore_index=True)
    return comparison
