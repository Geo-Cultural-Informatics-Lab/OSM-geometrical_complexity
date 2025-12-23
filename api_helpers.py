"""
API Helper Functions for OSM Geometrical Complexity Analysis

This module provides utility functions for API calls, logging, and file operations.
"""

import os
import json
import logging
import requests
import pandas as pd
import time


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

    # Remove existing handlers to allow reconfiguration with new log file
    if logger.handlers:
        for handler in logger.handlers[:]:  # Use slice to avoid modifying list during iteration
            handler.close()
            logger.removeHandler(handler)

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
# API Functions
# ============================================================================

# ============================================================================
# Ohsome API Functions (DEPRECATED - use ohsome_client.py)
# ============================================================================

def call_ohsome_api(endpoint, bounds, filter_query, time_param, return_type='dataframe',
                    api_version='elements'):
    """
    DEPRECATED: Use ohsome_client.OhsomeClient instead.

    Base function for calling Ohsome API endpoints.

    Args:
        endpoint: API endpoint path (e.g., 'count', 'length', 'area', 'geometry')
        bounds: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        filter_query: OSM filter query
        time_param: ISO-8601 timestamp or interval
        return_type: 'dataframe' or 'json'
        api_version: API category ('elements' or 'users')

    Returns:
        DataFrame or dict depending on return_type, None on error
    """
    from ohsome_client import OhsomeClient

    client = OhsomeClient()
    return client._call_endpoint(endpoint, bounds, filter_query, time_param, return_type, api_version)


def get_element_count(bounds, filter_query, time_param):
    """
    DEPRECATED: Use ohsome_client.OhsomeClient().query_element_count() instead.

    Get count of OSM elements matching the filter.
    """
    from ohsome_client import OhsomeClient

    client = OhsomeClient()
    return client.query_element_count(bounds, filter_query, time_param)


def get_user_count(bounds, filter_query, time_param):
    """
    DEPRECATED: Use ohsome_client.OhsomeClient().query_user_count() instead.

    Get count of unique users/contributors who edited elements matching the filter.
    """
    from ohsome_client import OhsomeClient

    client = OhsomeClient()
    return client.query_user_count(bounds, filter_query, time_param)


def get_period_user_count(bounds, filter_query, start_time, end_time):
    """
    Get count of unique users who contributed during a specific time period.

    This is period-specific (not cumulative) - counts only users active in the given interval.

    Args:
        bounds: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        filter_query: OSM filter query (e.g., "type:way and building=*")
        start_time: Period start as ISO-8601 timestamp (e.g., "2020-01-01")
        end_time: Period end as ISO-8601 timestamp (e.g., "2021-01-01")

    Returns:
        Integer count of unique users active in period, or None on error

    Example:
        >>> # Users active in 2020
        >>> count = get_period_user_count(bbox, "type:way and building=*", "2020-01-01", "2021-01-01")
    """
    time_interval = f"{start_time}/{end_time}"
    logger.debug(f"Getting period-specific user count for interval: {time_interval}")

    result = call_ohsome_api('count', bounds, filter_query, time_interval,
                            return_type='json', api_version='users')

    if result and 'result' in result:
        results = result['result']
        if results and len(results) > 0:
            count = results[0].get('value', 0)
            logger.info(f"Active users in period {time_interval}: {count:,}")
            return count

    logger.warning(f"Could not get period user count for {time_interval}")
    return None


def get_contributions_count(bounds, filter_query, start_time, end_time):
    """
    Get total count of contributions (edits) during a specific time period.

    Args:
        bounds: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        filter_query: OSM filter query (e.g., "type:way and building=*")
        start_time: Period start as ISO-8601 timestamp
        end_time: Period end as ISO-8601 timestamp

    Returns:
        Integer count of total contributions, or None on error

    Example:
        >>> count = get_contributions_count(bbox, "type:way and building=*", "2020-01-01", "2021-01-01")
    """
    time_interval = f"{start_time}/{end_time}"
    logger.debug(f"Getting contributions count for interval: {time_interval}")

    result = call_ohsome_api('count', bounds, filter_query, time_interval,
                            return_type='json', api_version='contributions')

    if result and 'result' in result:
        results = result['result']
        if results and len(results) > 0:
            count = results[0].get('value', 0)
            logger.info(f"Total contributions in period {time_interval}: {count:,}")
            return count

    logger.warning(f"Could not get contributions count for {time_interval}")
    return None


# ============================================================================
# File Operations
# ============================================================================

def save_to_file(data, path, filename, data_format='json'):
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
                header = True  # write header only if file doesn't exist
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
# User Contribution Analysis
# ============================================================================

def analyze_user_contributions(bounds, filter_query, start_time, end_time, cache_path=None):
    """
    Analyze user contribution distribution by downloading geometry data with user metadata.

    This provides detailed per-user statistics including:
    - Per-user contribution counts
    - User categorization (casual/regular/active/power mappers)
    - Distribution statistics

    Args:
        bounds: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        filter_query: OSM filter query
        start_time: Period start timestamp
        end_time: Period end timestamp
        cache_path: Optional path to cache results

    Returns:
        Dict with user statistics:
        {
            'casual_mappers_count': int,  # 2-10 contributions
            'regular_mappers_count': int,  # 11-50 contributions
            'active_mappers_count': int,   # 51-200 contributions
            'power_mappers_count': int,    # 200+ contributions
            'contributions_per_user_mean': float,
            'user_contributions': dict  # {user_id: contribution_count}
        }
    """
    import pandas as pd
    from collections import Counter

    # Check cache first
    if cache_path and os.path.exists(cache_path):
        logger.info(f"Loading cached user contribution data from {cache_path}")
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}, fetching fresh data")

    time_interval = f"{start_time}/{end_time}"
    logger.info(f"Fetching geometry data with user metadata for period {time_interval}")
    logger.info("This may take a while for large regions...")

    # Fetch geometry data with user information
    # Note: This can be large, so we're downloading full data
    data = call_ohsome_api('geometry', bounds, filter_query, time_interval, return_type='json')

    if not data or 'features' not in data:
        logger.error("Failed to fetch geometry data for user analysis")
        return None

    features = data['features']
    logger.info(f"Processing {len(features)} features for user contribution analysis")

    # Extract user IDs from each feature
    # Each feature has properties.@lastEdit.user or similar
    user_contributions = Counter()

    for feature in features:
        props = feature.get('properties', {})
        # Check various possible user ID fields
        user_id = (props.get('@user') or
                  props.get('@lastEdit', {}).get('user') if isinstance(props.get('@lastEdit'), dict) else None or
                  props.get('user'))

        if user_id:
            user_contributions[user_id] += 1

    if not user_contributions:
        logger.warning("No user information found in geometry data")
        return None

    # Calculate statistics
    contribution_counts = list(user_contributions.values())
    total_users = len(user_contributions)
    total_contributions = sum(contribution_counts)

    # Categorize users
    casual_mappers = sum(1 for count in contribution_counts if 2 <= count <= 10)
    regular_mappers = sum(1 for count in contribution_counts if 11 <= count <= 50)
    active_mappers = sum(1 for count in contribution_counts if 51 <= count <= 200)
    power_mappers = sum(1 for count in contribution_counts if count > 200)

    stats = {
        'casual_mappers_count': casual_mappers,
        'regular_mappers_count': regular_mappers,
        'active_mappers_count': active_mappers,
        'power_mappers_count': power_mappers,
        'contributions_per_user_mean': total_contributions / total_users if total_users > 0 else 0,
        'total_users_analyzed': total_users,
        'user_contributions': dict(user_contributions)  # Store for distribution plot
    }

    logger.info(f"User categorization: Casual={casual_mappers}, Regular={regular_mappers}, "
               f"Active={active_mappers}, Power={power_mappers}")

    # Cache results
    if cache_path:
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, 'w') as f:
                json.dump(stats, f, indent=2)
            logger.info(f"Cached user contribution data to {cache_path}")
        except Exception as e:
            logger.warning(f"Failed to cache results: {e}")

    return stats


# ============================================================================
# Chunk Processing and Aggregation
# ============================================================================

def save_chunk_data(data, region_name, chunk_id, path, base_filename):
    """
    Save chunk data with metadata for later aggregation.

    Args:
        data: DataFrame or dict to save
        region_name: Name of the region
        chunk_id: Unique chunk identifier
        path: Directory path for chunks
        base_filename: Base filename (chunk_id will be appended)

    Returns:
        Path to saved chunk file
    """
    if not path or not base_filename:
        return None

    try:
        # Create chunks subdirectory
        chunk_dir = os.path.join(path, "chunks")
        os.makedirs(chunk_dir, exist_ok=True)

        # Generate chunk filename
        name_without_ext = os.path.splitext(base_filename)[0]
        chunk_filename = f"{name_without_ext}_chunk_{chunk_id}.csv"
        chunk_path = os.path.join(chunk_dir, chunk_filename)

        # Save chunk data
        if hasattr(data, 'to_csv'):
            data.to_csv(chunk_path, index=False)
        else:
            pd.DataFrame(data).to_csv(chunk_path, index=False)

        logger.debug(f"Chunk {chunk_id} saved to {chunk_path}")
        return chunk_path

    except Exception as e:
        logger.error(f"Failed to save chunk {chunk_id}: {str(e)}")
        return None


def load_and_aggregate_chunks(path, base_filename, aggregation_func=None):
    """
    Load all chunk files and aggregate them.

    Args:
        path: Directory path where chunks are stored
        base_filename: Base filename to match chunk files
        aggregation_func: Optional custom aggregation function.
                         If None, concatenates all chunks.
                         Function signature: func(list_of_dataframes) -> aggregated_dataframe

    Returns:
        Aggregated DataFrame or None if no chunks found
    """
    chunk_dir = os.path.join(path, "chunks")

    if not os.path.exists(chunk_dir):
        logger.warning(f"Chunk directory not found: {chunk_dir}")
        return None

    try:
        # Find all chunk files matching the base filename
        name_without_ext = os.path.splitext(base_filename)[0]
        chunk_pattern = f"{name_without_ext}_chunk_*.csv"

        import glob
        chunk_files = glob.glob(os.path.join(chunk_dir, chunk_pattern))

        if not chunk_files:
            logger.warning(f"No chunk files found matching {chunk_pattern}")
            return None

        logger.info(f"Loading {len(chunk_files)} chunk files for aggregation")

        # Load all chunks
        chunks = []
        for chunk_file in sorted(chunk_files):
            try:
                chunk_df = pd.read_csv(chunk_file)
                chunks.append(chunk_df)
                logger.debug(f"Loaded chunk: {os.path.basename(chunk_file)} ({len(chunk_df)} rows)")
            except Exception as e:
                logger.error(f"Failed to load chunk {chunk_file}: {str(e)}")
                continue

        if not chunks:
            logger.error("No chunks successfully loaded")
            return None

        # Aggregate chunks
        if aggregation_func:
            result = aggregation_func(chunks)
        else:
            # Default: concatenate all chunks
            result = pd.concat(chunks, ignore_index=True)

        logger.info(f"Aggregated {len(chunks)} chunks into {len(result)} total rows")
        return result

    except Exception as e:
        logger.error(f"Error during chunk aggregation: {str(e)}")
        return None


# ============================================================================
# Resume/Status Management (DEPRECATED - use resume_manager.py)
# ============================================================================

def save_processing_status(status_file, completed_chunks, total_chunks, metadata=None):
    """
    DEPRECATED: Use resume_manager.ResumeManager instead.

    Save processing status for resume capability.
    """
    from resume_manager import ResumeManager

    # Extract task ID from status file name
    task_id = os.path.basename(status_file).replace('.status_', '').replace('.json', '')
    output_dir = os.path.dirname(status_file)

    mgr = ResumeManager(output_dir, task_id)
    mgr.set_total(total_chunks)

    for chunk_id in completed_chunks:
        mgr.mark_completed(chunk_id)


def load_processing_status(status_file):
    """
    DEPRECATED: Use resume_manager.ResumeManager instead.

    Load processing status from JSON file.
    """
    if not os.path.exists(status_file):
        return None

    try:
        with open(status_file, 'r', encoding='utf-8') as f:
            status = json.load(f)

        logger.info(f"Loaded processing status: {len(status.get('completed', []))}/{status.get('total', 0)} complete")

        # Convert to old format for backward compatibility
        return {
            'completed_chunks': status.get('completed', []),
            'total_chunks': status.get('total', 0),
            'progress': status.get('progress', 0),
            'metadata': status.get('metadata', {})
        }

    except Exception as e:
        logger.error(f"Failed to load processing status: {str(e)}")
        return None


def cleanup_chunks(path, base_filename, keep_status=False):
    """
    Clean up chunk files after successful aggregation.

    Args:
        path: Directory path where chunks are stored
        base_filename: Base filename to match chunk files
        keep_status: If True, keep status file (default: False)
    """
    chunk_dir = os.path.join(path, "chunks")

    if not os.path.exists(chunk_dir):
        return

    try:
        import glob

        # Remove chunk files
        name_without_ext = os.path.splitext(base_filename)[0]
        chunk_pattern = f"{name_without_ext}_chunk_*.csv"
        chunk_files = glob.glob(os.path.join(chunk_dir, chunk_pattern))

        for chunk_file in chunk_files:
            os.remove(chunk_file)
            logger.debug(f"Removed chunk file: {os.path.basename(chunk_file)}")

        logger.info(f"Cleaned up {len(chunk_files)} chunk files")

        # Remove status file if requested
        if not keep_status:
            status_files = glob.glob(os.path.join(path, f".chunk_status_{name_without_ext}*.json"))
            for status_file in status_files:
                os.remove(status_file)
                logger.debug(f"Removed status file: {os.path.basename(status_file)}")

    except Exception as e:
        logger.error(f"Error during chunk cleanup: {str(e)}")
