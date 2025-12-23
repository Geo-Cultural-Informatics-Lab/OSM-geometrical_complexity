"""
Ohsome Client - API Wrapper

This module provides a clean interface to the Ohsome API for querying OSM data.
"""

import requests
import json
import pandas as pd
import time
import logging

logger = logging.getLogger('geometrical_complexity_analysis')


class OhsomeClient:
    """Client for Ohsome API interactions."""

    def __init__(self, base_url="https://api.ohsome.org/v1", timeout=300):
        """
        Initialize Ohsome API client.

        Args:
            base_url: Base URL for Ohsome API
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.timeout = timeout

    def _call_endpoint(self, endpoint, bounds, filter_query, time_param,
                       return_type='dataframe', api_version='elements'):
        """
        Base method for calling Ohsome API endpoints.

        Args:
            endpoint: API endpoint path (e.g., 'count', 'length', 'area', 'geometry')
            bounds: Bounding box as "min_lon,min_lat,max_lon,max_lat"
            filter_query: OSM filter query
            time_param: ISO-8601 timestamp or interval
            return_type: 'dataframe' or 'json'
            api_version: API category ('elements', 'users', 'contributions')

        Returns:
            DataFrame or dict depending on return_type, None on error
        """
        start_time = time.time()
        url = f"{self.base_url}/{api_version}/{endpoint}"

        params = {
            "bboxes": bounds,
            "time": time_param,
            "filter": filter_query
        }

        logger.debug(f"Calling Ohsome API endpoint: {api_version}/{endpoint}")
        logger.debug(f"Parameters: bounds={bounds}, filter={filter_query}, time={time_param}")

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            api_time = time.time() - start_time

            if response.status_code == 200:
                parse_start = time.time()
                data = response.json()
                parse_time = time.time() - parse_start

                logger.debug(f"API call ({api_version}/{endpoint}): {api_time:.2f}s")
                logger.info(f"Successfully retrieved data from {api_version}/{endpoint} endpoint")

                if return_type == 'dataframe':
                    return pd.json_normalize(data['result']) if 'result' in data else data
                return data
            else:
                logger.error(f"API request failed with status {response.status_code}: {response.text}")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"API request timed out for endpoint {endpoint} (>{self.timeout}s)")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for endpoint {endpoint}: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from {endpoint}: {str(e)}")
            return None

    def query_geometry(self, bounds, filter_query, timestamp):
        """
        Query OSM element geometries.

        Args:
            bounds: Bounding box as "min_lon,min_lat,max_lon,max_lat"
            filter_query: OSM filter query
            timestamp: ISO-8601 timestamp

        Returns:
            Dict with GeoJSON features or None on error
        """
        return self._call_endpoint('geometry', bounds, filter_query, timestamp,
                                  return_type='json', api_version='elements')

    def query_element_count(self, bounds, filter_query, timestamp):
        """
        Query count of OSM elements.

        Args:
            bounds: Bounding box
            filter_query: OSM filter
            timestamp: ISO-8601 timestamp

        Returns:
            Integer count or None on error
        """
        result = self._call_endpoint('count', bounds, filter_query, timestamp,
                                     return_type='json', api_version='elements')

        if result and 'result' in result:
            results = result['result']
            if results and len(results) > 0:
                count = results[0].get('value', 0)
                logger.info(f"Element count: {count:,}")
                return count

        logger.warning("Could not extract element count from API response")
        return None

    def query_user_count(self, bounds, filter_query, timestamp):
        """
        Query count of unique users/contributors.

        Note: Users API requires time interval. Single timestamp is converted
        to interval from OSM start (2007-10-08).

        Args:
            bounds: Bounding box
            filter_query: OSM filter
            timestamp: ISO-8601 timestamp or interval

        Returns:
            Integer user count or None on error
        """
        # Convert single timestamp to interval if needed
        if '/' not in timestamp:
            osm_start = "2007-10-08"
            time_interval = f"{osm_start}/{timestamp}"
            logger.debug(f"Converting timestamp to interval for user count: {time_interval}")
        else:
            time_interval = timestamp

        result = self._call_endpoint('count', bounds, filter_query, time_interval,
                                     return_type='json', api_version='users')

        if result and 'result' in result:
            results = result['result']
            if results and len(results) > 0:
                count = results[-1].get('value', 0)
                logger.info(f"User count: {count:,}")
                return count

        logger.warning("Could not extract user count from API response")
        return None

    def query_area(self, bounds, filter_query, time_param):
        """
        Query aggregated area of OSM features.

        Args:
            bounds: Bounding box
            filter_query: OSM filter
            time_param: ISO-8601 timestamp or interval

        Returns:
            DataFrame with area results or None on error
        """
        logger.info(f"Fetching feature areas for bounds: {bounds}")
        result = self._call_endpoint('area', bounds, filter_query, time_param,
                                     return_type='dataframe', api_version='elements')

        if result is not None:
            logger.info("Area data successfully retrieved")
        else:
            logger.error("Failed to retrieve area data")

        return result

    def query_length(self, bounds, filter_query, time_param):
        """
        Query aggregated length of OSM features.

        Args:
            bounds: Bounding box
            filter_query: OSM filter
            time_param: ISO-8601 timestamp or interval

        Returns:
            DataFrame with length results or None on error
        """
        logger.info(f"Fetching feature lengths for bounds: {bounds}")
        result = self._call_endpoint('length', bounds, filter_query, time_param,
                                     return_type='dataframe', api_version='elements')

        if result is not None:
            logger.info("Length data successfully retrieved")
        else:
            logger.error("Failed to retrieve length data")

        return result

    def query_count_timeseries(self, bounds, filter_query, time_param):
        """
        Query feature count over time.

        Args:
            bounds: Bounding box
            filter_query: OSM filter
            time_param: ISO-8601 time interval (e.g., "2008-01-01/2025-01-01/P1M")

        Returns:
            DataFrame with count results or None on error
        """
        logger.info(f"Fetching feature counts for bounds: {bounds}")
        result = self._call_endpoint('count', bounds, filter_query, time_param,
                                     return_type='dataframe', api_version='elements')

        if result is not None:
            logger.info("Count data successfully retrieved")
        else:
            logger.error("Failed to retrieve count data")

        return result
