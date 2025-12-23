"""
Core - Core Functionality

This package contains the core analysis functionality:
- metrics: Pure calculation functions (convex hull, node statistics, etc.)
- ohsome_client: API client for Ohsome API
- analyzer: Main orchestration logic for analysis workflows
- geometry_analysis: Backward compatibility wrapper (deprecated)
"""

from .metrics import (
    calculate_convex_hull_metrics,
    calculate_node_statistics,
    extract_comprehensive_metrics,
    extract_node_counts
)
from .ohsome_client import OhsomeClient
from .analyzer import (
    analyze_region_buildings,
    analyze_region_buildings_chunked,
    analyze_region_roads,
    compare_regions
)

__all__ = [
    # Metrics
    'calculate_convex_hull_metrics',
    'calculate_node_statistics',
    'extract_comprehensive_metrics',
    'extract_node_counts',
    # API Client
    'OhsomeClient',
    # Analyzer
    'analyze_region_buildings',
    'analyze_region_buildings_chunked',
    'analyze_region_roads',
    'compare_regions',
]
