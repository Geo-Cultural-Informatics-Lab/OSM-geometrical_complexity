"""
Chunking Utilities for Large-Scale OSM Analysis

This module provides functions to split large bounding boxes into manageable chunks
for processing with the Ohsome API, preventing timeouts and connection failures.
"""

import math
from math import cos, radians
from typing import List, Tuple, Dict
from api_helpers import logger


# ============================================================================
# Bounding Box Utilities
# ============================================================================

def bbox_to_coords(bbox: str) -> Tuple[float, float, float, float]:
    """
    Convert bbox string to coordinate tuple.

    Args:
        bbox: Bounding box string "min_lon,min_lat,max_lon,max_lat"

    Returns:
        Tuple of (min_lon, min_lat, max_lon, max_lat)
    """
    coords = bbox.split(',')
    return float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3])


def coords_to_bbox(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> str:
    """
    Convert coordinates to bbox string.

    Args:
        min_lon, min_lat, max_lon, max_lat: Bounding box coordinates

    Returns:
        Bounding box string "min_lon,min_lat,max_lon,max_lat"
    """
    return f"{min_lon},{min_lat},{max_lon},{max_lat}"


def bbox_dimensions_km(bbox: str) -> Tuple[float, float]:
    """
    Calculate bounding box dimensions in kilometers.

    Args:
        bbox: Bounding box string "min_lon,min_lat,max_lon,max_lat"

    Returns:
        Tuple of (width_km, height_km)
    """
    min_lon, min_lat, max_lon, max_lat = bbox_to_coords(bbox)

    # Calculate center latitude for longitude correction
    center_lat = (min_lat + max_lat) / 2

    # Approximate conversion: 1 degree latitude ≈ 111 km
    # 1 degree longitude ≈ 111 * cos(latitude) km
    lat_degree_km = 111.0
    lon_degree_km = 111.0 * cos(radians(center_lat))

    height_km = (max_lat - min_lat) * lat_degree_km
    width_km = (max_lon - min_lon) * lon_degree_km

    return width_km, height_km


def bbox_area_km2(bbox: str) -> float:
    """
    Calculate bounding box area in square kilometers.

    Args:
        bbox: Bounding box string

    Returns:
        Area in km²
    """
    width_km, height_km = bbox_dimensions_km(bbox)
    return width_km * height_km


# ============================================================================
# Chunking Functions
# ============================================================================

def split_bbox_into_grid(bbox: str, chunk_size_km: float = 50) -> List[Dict[str, any]]:
    """
    Split a large bounding box into grid chunks of specified size.

    This function divides a bbox into smaller rectangular chunks to enable
    processing of large regions that would otherwise timeout or fail with
    the Ohsome API.

    Args:
        bbox: Bounding box string "min_lon,min_lat,max_lon,max_lat"
        chunk_size_km: Target size of each chunk in kilometers (default: 50km)

    Returns:
        List of chunk dictionaries with keys:
            - 'bbox': chunk bounding box string
            - 'chunk_id': unique identifier (row_col format, e.g., "0_0", "0_1")
            - 'row': row index
            - 'col': column index
            - 'center_lat': center latitude of chunk
            - 'center_lon': center longitude of chunk

    Example:
        >>> chunks = split_bbox_into_grid("8.0,49.0,9.0,50.0", chunk_size_km=25)
        >>> len(chunks)
        16  # 4x4 grid for ~111km x 111km area
        >>> chunks[0]['bbox']
        "8.0,49.0,8.25,49.25"
    """
    min_lon, min_lat, max_lon, max_lat = bbox_to_coords(bbox)

    # Calculate center latitude for accurate longitude spacing
    center_lat = (min_lat + max_lat) / 2

    # Conversion factors
    lat_degree_km = 111.0
    lon_degree_km = 111.0 * cos(radians(center_lat))

    # Calculate degree offsets for chunk size
    lat_chunk_degrees = chunk_size_km / lat_degree_km
    lon_chunk_degrees = chunk_size_km / lon_degree_km

    # Calculate number of chunks needed in each direction
    lat_range = max_lat - min_lat
    lon_range = max_lon - min_lon

    num_rows = math.ceil(lat_range / lat_chunk_degrees)
    num_cols = math.ceil(lon_range / lon_chunk_degrees)

    total_chunks = num_rows * num_cols
    width_km, height_km = bbox_dimensions_km(bbox)

    logger.info(f"Splitting bbox into grid chunks:")
    logger.info(f"  Original bbox: {bbox}")
    logger.info(f"  Dimensions: {width_km:.1f} km × {height_km:.1f} km ({bbox_area_km2(bbox):.0f} km²)")
    logger.info(f"  Chunk size: {chunk_size_km} km")
    logger.info(f"  Grid: {num_rows} rows × {num_cols} cols = {total_chunks} chunks")

    # Generate chunks
    chunks = []
    for row in range(num_rows):
        for col in range(num_cols):
            # Calculate chunk boundaries
            chunk_min_lat = min_lat + (row * lat_chunk_degrees)
            chunk_max_lat = min(min_lat + ((row + 1) * lat_chunk_degrees), max_lat)

            chunk_min_lon = min_lon + (col * lon_chunk_degrees)
            chunk_max_lon = min(min_lon + ((col + 1) * lon_chunk_degrees), max_lon)

            # Create chunk bbox string
            chunk_bbox = coords_to_bbox(chunk_min_lon, chunk_min_lat, chunk_max_lon, chunk_max_lat)

            # Calculate chunk center for reference
            chunk_center_lat = (chunk_min_lat + chunk_max_lat) / 2
            chunk_center_lon = (chunk_min_lon + chunk_max_lon) / 2

            chunks.append({
                'bbox': chunk_bbox,
                'chunk_id': f"{row}_{col}",
                'row': row,
                'col': col,
                'center_lat': chunk_center_lat,
                'center_lon': chunk_center_lon
            })

    logger.debug(f"Generated {len(chunks)} chunks")
    return chunks


def estimate_chunk_size(bbox: str, max_features_per_chunk: int = 50000,
                       building_density_per_km2: int = 1000) -> float:
    """
    Estimate optimal chunk size based on expected feature density.

    This function calculates the chunk size needed to keep the number of
    features per chunk below a specified maximum, based on building density.

    Args:
        bbox: Bounding box string
        max_features_per_chunk: Maximum features to process per chunk (default: 50,000)
        building_density_per_km2: Expected buildings per km² (default: 1,000)
            - Rural areas: 100-500
            - Suburban: 500-2,000
            - Urban: 2,000-10,000
            - Dense urban: 10,000-50,000

    Returns:
        Recommended chunk size in kilometers

    Example:
        >>> # For dense urban area (10k buildings/km²), get chunk size for 50k features max
        >>> chunk_size = estimate_chunk_size("8.0,49.0,9.0,50.0",
        ...                                   max_features_per_chunk=50000,
        ...                                   building_density_per_km2=10000)
        >>> chunk_size
        22.36  # Approximately sqrt(50000 / 10000) * sqrt(km²)
    """
    # Calculate area needed for max_features
    area_km2_per_chunk = max_features_per_chunk / building_density_per_km2

    # Chunk size is sqrt of area (for square chunks)
    chunk_size_km = math.sqrt(area_km2_per_chunk)

    # Ensure reasonable bounds (10km minimum, 200km maximum)
    chunk_size_km = max(10, min(chunk_size_km, 200))

    bbox_area = bbox_area_km2(bbox)
    num_chunks = math.ceil(bbox_area / area_km2_per_chunk)

    logger.info(f"Chunk size estimation:")
    logger.info(f"  Bbox area: {bbox_area:.0f} km²")
    logger.info(f"  Building density: {building_density_per_km2} buildings/km²")
    logger.info(f"  Max features/chunk: {max_features_per_chunk:,}")
    logger.info(f"  Recommended chunk size: {chunk_size_km:.1f} km")
    logger.info(f"  Estimated chunks needed: {num_chunks}")

    return chunk_size_km


def adaptive_chunk_split(bbox: str, max_features_per_chunk: int = 50000,
                        min_chunk_size_km: float = 10,
                        max_chunk_size_km: float = 100,
                        default_density: int = 2000) -> List[Dict[str, any]]:
    """
    Split bbox with adaptive chunk sizing based on estimated feature density.

    This is a convenience function that estimates optimal chunk size and
    splits the bbox accordingly.

    Args:
        bbox: Bounding box string
        max_features_per_chunk: Maximum features per chunk (default: 50,000)
        min_chunk_size_km: Minimum chunk size (default: 10km)
        max_chunk_size_km: Maximum chunk size (default: 100km)
        default_density: Default building density estimate (default: 2,000 buildings/km²)

    Returns:
        List of chunk dictionaries (same format as split_bbox_into_grid)

    Example:
        >>> # Automatically determine optimal chunking
        >>> chunks = adaptive_chunk_split("8.0,49.0,10.0,51.0")
        >>> # Processes with chunk size optimized for ~50k features each
    """
    # Estimate optimal chunk size
    estimated_size = estimate_chunk_size(bbox, max_features_per_chunk, default_density)

    # Clamp to reasonable bounds
    chunk_size = max(min_chunk_size_km, min(estimated_size, max_chunk_size_km))

    logger.info(f"Using adaptive chunk size: {chunk_size:.1f} km")

    # Split with estimated size
    return split_bbox_into_grid(bbox, chunk_size)


def get_chunk_status_filename(region_name: str, timestamp: str = None) -> str:
    """
    Generate standardized filename for chunk processing status.

    Args:
        region_name: Name of region being processed
        timestamp: Optional timestamp (default: None for current processing)

    Returns:
        Status filename
    """
    if timestamp:
        return f".chunk_status_{region_name}_{timestamp}.json"
    return f".chunk_status_{region_name}.json"


# ============================================================================
# Chunk Metadata and Utilities
# ============================================================================

def calculate_total_area_km2(chunks: List[Dict[str, any]]) -> float:
    """
    Calculate total area covered by all chunks.

    Args:
        chunks: List of chunk dictionaries

    Returns:
        Total area in km²
    """
    total_area = sum(bbox_area_km2(chunk['bbox']) for chunk in chunks)
    return total_area


def get_chunk_grid_dimensions(chunks: List[Dict[str, any]]) -> Tuple[int, int]:
    """
    Get grid dimensions from chunk list.

    Args:
        chunks: List of chunk dictionaries

    Returns:
        Tuple of (num_rows, num_cols)
    """
    if not chunks:
        return 0, 0

    max_row = max(chunk['row'] for chunk in chunks)
    max_col = max(chunk['col'] for chunk in chunks)

    return max_row + 1, max_col + 1


def print_chunk_summary(chunks: List[Dict[str, any]]):
    """
    Print summary information about chunks.

    Args:
        chunks: List of chunk dictionaries
    """
    if not chunks:
        print("No chunks generated")
        return

    num_rows, num_cols = get_chunk_grid_dimensions(chunks)
    total_area = calculate_total_area_km2(chunks)
    avg_chunk_area = total_area / len(chunks)

    print(f"\nChunk Summary:")
    print(f"  Total chunks: {len(chunks)}")
    print(f"  Grid dimensions: {num_rows} rows × {num_cols} cols")
    print(f"  Total area: {total_area:.0f} km²")
    print(f"  Avg chunk area: {avg_chunk_area:.1f} km²")
    print(f"  Chunk size: ~{math.sqrt(avg_chunk_area):.1f} km")
