"""
Time Series Analysis for OSM Geometrical Complexity

This module provides functions to analyze how OSM mapping quality evolves over time
by generating time series of geometrical complexity metrics at different intervals.
"""

import os
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from utils.api_helpers import logger, save_processing_status, load_processing_status
from core.geometry_analysis import get_poly_coords, get_poly_coords_chunked
from utils.chunking_utils import bbox_area_km2


# ============================================================================
# Time Interval Generation
# ============================================================================

def generate_time_intervals(start_year=2008, end_year=2025, interval='yearly'):
    """
    Generate list of ISO-8601 timestamp strings for time series analysis.

    Args:
        start_year: Starting year (default: 2008, OSM founding year)
        end_year: Ending year (default: 2025)
        interval: Time interval - 'yearly', 'quarterly', or 'monthly'

    Returns:
        List of ISO-8601 date strings (YYYY-MM-DD format)

    Example:
        >>> intervals = generate_time_intervals(2020, 2022, 'yearly')
        >>> intervals
        ['2020-01-01', '2021-01-01', '2022-01-01']

        >>> intervals = generate_time_intervals(2024, 2025, 'quarterly')
        >>> intervals
        ['2024-01-01', '2024-04-01', '2024-07-01', '2024-10-01', '2025-01-01']
    """
    intervals = []
    current_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 12, 31)

    if interval == 'yearly':
        while current_date <= end_date:
            intervals.append(current_date.strftime('%Y-%m-%d'))
            current_date += relativedelta(years=1)

    elif interval == 'quarterly':
        while current_date <= end_date:
            intervals.append(current_date.strftime('%Y-%m-%d'))
            current_date += relativedelta(months=3)

    elif interval == 'monthly':
        while current_date <= end_date:
            intervals.append(current_date.strftime('%Y-%m-%d'))
            current_date += relativedelta(months=1)

    else:
        raise ValueError(f"Invalid interval: {interval}. Must be 'yearly', 'quarterly', or 'monthly'")

    logger.info(f"Generated {len(intervals)} time intervals ({interval}) from {start_year} to {end_year}")
    return intervals


def generate_ohsome_time_param(timestamps):
    """
    Convert list of timestamps to Ohsome API time parameter format.

    Ohsome API accepts multiple timestamps as comma-separated list or
    as interval format: "start/end/period"

    Args:
        timestamps: List of ISO-8601 timestamp strings

    Returns:
        String in Ohsome time parameter format

    Example:
        >>> timestamps = ['2020-01-01', '2021-01-01', '2022-01-01']
        >>> generate_ohsome_time_param(timestamps)
        '2020-01-01,2021-01-01,2022-01-01'
    """
    if not timestamps:
        raise ValueError("No timestamps provided")

    # For now, use comma-separated format (simpler, more explicit)
    # Alternative: could use interval format like "2020-01-01/2022-01-01/P1Y"
    time_param = ','.join(timestamps)
    logger.debug(f"Ohsome time parameter: {time_param}")
    return time_param


# ============================================================================
# Time Series Analysis Functions
# ============================================================================

def analyze_region_time_series(region_name, bbox, start_year=2008, end_year=2025,
                               interval='yearly', filter="type:way and building=*",
                               path=None, base_filename=None,
                               use_chunked_threshold_km2=5000,
                               resume=True):
    """
    Analyze geometrical complexity evolution over time for a region.

    This function processes a region at multiple time points to track how
    mapping quality (geometrical complexity) has evolved over time.

    Args:
        region_name: Name of the region
        bbox: Bounding box string
        start_year: Starting year (default: 2008)
        end_year: Ending year (default: 2025)
        interval: Time interval - 'yearly', 'quarterly', or 'monthly'
        filter: OSM filter query (default: buildings)
        path: Directory to save results (required)
        base_filename: Base filename for results (required)
        use_chunked_threshold_km2: Use chunked processing for areas above this size
        resume: Resume from previous run if available

    Returns:
        DataFrame with time series results (one row per timestamp)

    Example:
        >>> bbox = get_bbox_by_city("Jerusalem", radius_km=15)
        >>> ts_data = analyze_region_time_series(
        ...     "jerusalem",
        ...     bbox,
        ...     start_year=2015,
        ...     end_year=2025,
        ...     interval='yearly',
        ...     path="./data"
        ... )
    """
    if not path or not base_filename:
        logger.error("path and base_filename are required for time series analysis")
        return None

    logger.info(f"=" * 80)
    logger.info(f"Starting time series analysis for region: {region_name}")
    logger.info(f"Period: {start_year}-{end_year}, Interval: {interval}")
    logger.info(f"Bounding box: {bbox}")
    logger.info(f"=" * 80)

    # Generate time intervals
    timestamps = generate_time_intervals(start_year, end_year, interval)
    logger.info(f"Will process {len(timestamps)} time points")

    # Check if we need chunked processing
    area_km2 = bbox_area_km2(bbox)
    use_chunked = area_km2 > use_chunked_threshold_km2

    if use_chunked:
        logger.info(f"Large region ({area_km2:.0f} km²) - will use chunked processing for each time point")
    else:
        logger.info(f"Small region ({area_km2:.0f} km²) - will use direct processing for each time point")

    # Setup resume capability
    status_file = os.path.join(path, f".time_series_status_{region_name}.json")
    completed_timestamps = []
    results = []

    if resume:
        status = load_processing_status(status_file)
        if status:
            completed_timestamps = status.get('completed_chunks', [])  # Reusing 'completed_chunks' field
            logger.info(f"Resuming: {len(completed_timestamps)}/{len(timestamps)} time points already processed")

            # Load previously completed results
            partial_results_file = os.path.join(path, f"{region_name}_time_series_partial.csv")
            if os.path.exists(partial_results_file):
                results_df = pd.read_csv(partial_results_file)
                results = results_df.to_dict('records')

    # Process each timestamp
    for i, timestamp in enumerate(timestamps):
        # Skip if already completed
        if timestamp in completed_timestamps:
            logger.debug(f"Skipping timestamp {timestamp} (already completed)")
            continue

        logger.info(f"\n[{i+1}/{len(timestamps)}] Processing timestamp: {timestamp}")
        logger.info(f"-" * 80)

        try:
            # Create timestamped filename
            filename_ts = f"{base_filename}_{timestamp.replace('-', '')}"

            if use_chunked:
                summary = get_poly_coords_chunked(
                    region_name=f"{region_name}_{timestamp}",
                    bounds=bbox,
                    filter=filter,
                    time_param=timestamp,
                    path=path,
                    filename=filename_ts,
                    resume=True,
                    cleanup_after=True  # Clean up chunks after aggregation
                )
            else:
                summary = get_poly_coords(
                    region_name=f"{region_name}_{timestamp}",
                    bounds=bbox,
                    filter=filter,
                    time_param=timestamp,
                    path=path,
                    filename=filename_ts
                )

            if summary is not None:
                # Add timestamp to results
                result_row = summary.to_dict('records')[0]
                result_row['timestamp'] = timestamp
                result_row['year'] = int(timestamp[:4])
                results.append(result_row)

                completed_timestamps.append(timestamp)
                logger.info(f"  ✓ Timestamp {timestamp} completed successfully")

                # Save partial results incrementally
                partial_results_df = pd.DataFrame(results)
                partial_results_file = os.path.join(path, f"{region_name}_time_series_partial.csv")
                partial_results_df.to_csv(partial_results_file, index=False)

            else:
                logger.warning(f"  ✗ Timestamp {timestamp} returned no data")

        except Exception as e:
            logger.error(f"  ✗ Timestamp {timestamp} failed: {str(e)}")
            continue

        # Save progress after each timestamp
        save_processing_status(
            status_file,
            completed_timestamps,
            len(timestamps),
            metadata={
                'region_name': region_name,
                'bbox': bbox,
                'start_year': start_year,
                'end_year': end_year,
                'interval': interval
            }
        )

    # Create final time series DataFrame
    if not results:
        # Check if analysis was already completed - load existing final file
        final_file = os.path.join(path, f"{region_name}_time_series_{interval}.csv")
        if os.path.exists(final_file):
            logger.info(f"All time points already processed - loading existing results from {final_file}")
            ts_df = pd.read_csv(final_file)
            return ts_df
        else:
            logger.error("No time series data collected")
            return None

    ts_df = pd.DataFrame(results)

    # Sort by timestamp
    ts_df = ts_df.sort_values('timestamp').reset_index(drop=True)

    # Save final time series
    final_file = os.path.join(path, f"{region_name}_time_series_{interval}.csv")
    ts_df.to_csv(final_file, index=False)
    logger.info(f"\n✓ Time series analysis complete: {len(ts_df)} time points")
    logger.info(f"  Saved to: {final_file}")

    # Clean up partial results file
    partial_results_file = os.path.join(path, f"{region_name}_time_series_partial.csv")
    if os.path.exists(partial_results_file):
        os.remove(partial_results_file)
        logger.debug("Cleaned up partial results file")

    return ts_df


def compare_regions_time_series(regions_dict, start_year=2008, end_year=2025,
                                interval='yearly', filter="type:way and building=*",
                                path=None, resume=True):
    """
    Compare multiple regions' complexity evolution over time.

    Args:
        regions_dict: Dict mapping region names to bounding boxes
                     e.g., {'london': bbox1, 'paris': bbox2}
        start_year: Starting year (default: 2008)
        end_year: Ending year (default: 2025)
        interval: Time interval - 'yearly', 'quarterly', or 'monthly'
        filter: OSM filter query (default: buildings)
        path: Directory to save results (required)
        resume: Resume from previous run if available

    Returns:
        Combined DataFrame with all regions' time series

    Example:
        >>> regions = {
        ...     'london': get_bbox_by_city("London", radius_km=10),
        ...     'paris': get_bbox_by_city("Paris", radius_km=10)
        ... }
        >>> comparison = compare_regions_time_series(
        ...     regions,
        ...     start_year=2015,
        ...     end_year=2025,
        ...     interval='yearly',
        ...     path="./data"
        ... )
    """
    if not path:
        logger.error("path is required for time series comparison")
        return None

    logger.info(f"=" * 80)
    logger.info(f"Starting time series comparison for {len(regions_dict)} regions")
    logger.info(f"Period: {start_year}-{end_year}, Interval: {interval}")
    logger.info(f"=" * 80)

    all_results = []

    for region_name, bbox in regions_dict.items():
        logger.info(f"\n\nProcessing region: {region_name.upper()}")
        logger.info(f"=" * 80)

        ts_data = analyze_region_time_series(
            region_name=region_name,
            bbox=bbox,
            start_year=start_year,
            end_year=end_year,
            interval=interval,
            filter=filter,
            path=path,
            base_filename=f"{region_name}_buildings",
            resume=resume
        )

        if ts_data is not None:
            all_results.append(ts_data)
        else:
            logger.warning(f"No data collected for region: {region_name}")

    if not all_results:
        logger.error("No time series data collected for any region")
        return None

    # Combine all results
    combined_df = pd.concat(all_results, ignore_index=True)

    # Save combined results
    combined_file = os.path.join(path, f"time_series_comparison_{interval}.csv")
    combined_df.to_csv(combined_file, index=False)
    logger.info(f"\n✓ Time series comparison complete")
    logger.info(f"  Total data points: {len(combined_df)}")
    logger.info(f"  Saved to: {combined_file}")

    return combined_df


# ============================================================================
# Time Series Statistics and Utilities
# ============================================================================

def calculate_growth_metrics(ts_df, metric_column='mean_ratio'):
    """
    Calculate growth/change metrics from time series data.

    Args:
        ts_df: Time series DataFrame with 'timestamp' and metric columns
        metric_column: Column name to analyze (e.g., 'mean_ratio')

    Returns:
        DataFrame with growth metrics added
    """
    ts_df = ts_df.copy()

    # Sort by timestamp
    ts_df = ts_df.sort_values('timestamp').reset_index(drop=True)

    if len(ts_df) < 2:
        logger.warning("Need at least 2 time points to calculate growth metrics")
        return ts_df

    # Calculate absolute change
    ts_df[f'{metric_column}_change'] = ts_df[metric_column].diff()

    # Calculate percentage change
    ts_df[f'{metric_column}_pct_change'] = ts_df[metric_column].pct_change() * 100

    # Calculate cumulative change from start
    start_value = ts_df[metric_column].iloc[0]
    ts_df[f'{metric_column}_cumulative_change'] = ts_df[metric_column] - start_value

    logger.info(f"Growth metrics calculated for {metric_column}")
    return ts_df


def summarize_time_series(ts_df, region_column='region', metric_column='mean_ratio'):
    """
    Generate summary statistics for time series data.

    Args:
        ts_df: Time series DataFrame
        region_column: Column name containing region names
        metric_column: Column name to summarize

    Returns:
        DataFrame with summary statistics per region
    """
    summary = ts_df.groupby(region_column).agg({
        metric_column: ['min', 'max', 'mean', 'std'],
        'timestamp': ['min', 'max', 'count']
    }).reset_index()

    # Flatten column names
    summary.columns = [f'{col[0]}_{col[1]}' if col[1] else col[0] for col in summary.columns]

    # Calculate range
    summary[f'{metric_column}_range'] = summary[f'{metric_column}_max'] - summary[f'{metric_column}_min']

    logger.info(f"Time series summary generated for {len(summary)} regions")
    return summary
