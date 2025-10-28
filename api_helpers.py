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

def call_ohsome_api(endpoint, bounds, filter_query, time_param, return_type='dataframe'):
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


def save_processing_status(status_file, completed_chunks, total_chunks, metadata=None):
    """
    Save processing status for resume capability.

    Args:
        status_file: Path to status JSON file
        completed_chunks: List of completed chunk IDs
        total_chunks: Total number of chunks
        metadata: Optional dict with additional metadata
    """
    try:
        status = {
            'completed_chunks': completed_chunks,
            'total_chunks': total_chunks,
            'progress': len(completed_chunks) / total_chunks if total_chunks > 0 else 0,
            'timestamp': pd.Timestamp.now().isoformat()
        }

        if metadata:
            status['metadata'] = metadata

        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(status, f, indent=2)

        logger.debug(f"Processing status saved: {len(completed_chunks)}/{total_chunks} chunks complete")

    except Exception as e:
        logger.error(f"Failed to save processing status: {str(e)}")


def load_processing_status(status_file):
    """
    Load processing status from JSON file.

    Args:
        status_file: Path to status JSON file

    Returns:
        Dict with status information or None if file doesn't exist
    """
    if not os.path.exists(status_file):
        return None

    try:
        with open(status_file, 'r', encoding='utf-8') as f:
            status = json.load(f)

        logger.info(f"Loaded processing status: {len(status.get('completed_chunks', []))}/{status.get('total_chunks', 0)} chunks complete")
        return status

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
