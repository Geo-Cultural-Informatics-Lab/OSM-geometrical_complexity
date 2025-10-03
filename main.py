"""
Main script for OSM Geometrical Complexity Analysis

This script demonstrates usage of the refactored API functions to analyze
OSM road network complexity for different geographical regions.
"""

import logging
from functions import (get_count, get_len, get_area, get_vertices, get_poly_coords,
                       analyze_region, plot_node_distribution, compare_regions, setup_logging)


# ============================================================================
# Sample Bounding Boxes
# ============================================================================

BBOXES = {
    'heidelberg': "8.1543,49.1757,9.1351,49.6884",
    'paris': "2.255031,48.813564,2.426418,48.904637",
    'hainan': "108.4078,18.0357,111.1148,20.1493",
    'thailand': "99.6253,9.3452,100.201,10.1602",
    'beit_shemesh': "34.938188,31.689471,35.035005,31.786876"
}


def main():
    """Main execution function."""

    # Initialize logging
    log_file = 'geometrical_complexity_analysis.log'
    setup_logging(log_file=log_file, log_level=logging.DEBUG, console_level=logging.INFO)
    print(f"\n{'='*60}")
    print(f"OSM Geometrical Complexity Analysis")
    print(f"Log file: {log_file}")
    print(f"{'='*60}\n")

    heidelberg_analysis = analyze_region('Heidelberg', BBOXES['heidelberg'])
    if heidelberg_analysis is not None:
        print("\nHeidelberg Analysis Results:")
        print(heidelberg_analysis.to_string())

    # plot_node_distribution(BBOXES['heidelberg'], 'Heidelberg')

    # Compare subset of regions (uncomment to run full comparison)
    # comparison_regions = {
    #     'heidelberg': BBOXES['heidelberg'],
    #     'paris': BBOXES['paris'],
    #     'beit_shemesh': BBOXES['beit_shemesh']
    # }
    # comparison = compare_regions(comparison_regions)
    # if comparison is not None:
    #    print("\nComparison Results:")
    #     print(comparison.to_string())

    # Uncomment to save data:
    # vertices_with_save = get_vertices(
    #     BBOXES['heidelberg'],
    #     time="2025-01-01",
    #     path="./output",
    #     filename="heidelberg_vertices.json"
    # )

    print("Building Convex Hull Analysis")
    print("\n" + "="*60)
    print("="*60)
    building_metrics = get_poly_coords(
        BBOXES['heidelberg'],
        filter="type:way and building=*",
        time_param="2025-01-01"
    )
    if building_metrics is not None:
        print("\nBuilding Convex Hull Metrics:")
        print(building_metrics.to_string())

if __name__ == "__main__":
    main()
