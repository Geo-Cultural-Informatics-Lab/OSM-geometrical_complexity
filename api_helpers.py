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
