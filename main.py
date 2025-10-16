"""
Main script for OSM Geometrical Complexity Analysis

This script demonstrates usage of the refactored API functions to analyze
OSM road network complexity and building geometry completeness for different regions.
"""

import logging
from pathlib import Path

# Import from refactored modules
from api_helpers import setup_logging
from geometry_analysis import (
    get_count, get_len, get_area, get_vertices, get_poly_coords,
    analyze_region, plot_node_distribution, compare_regions
)
from bbox_utils import BBOXES, get_bbox_by_city, bbox_by_location
from visualization import (
    plot_completeness_metrics, plot_area_comparison,
    plot_summary_dashboard, print_completeness_summary
)


def main():

    # Initialize logging
    log_file = 'geometrical_complexity_analysis.log'
    logger = setup_logging(log_file=log_file, log_level=logging.DEBUG, console_level=logging.INFO)

    print(f"\n{'='*80}")
    print(f"OSM GEOMETRICAL COMPLEXITY ANALYSIS")
    print(f"Log file: {log_file}")
    print(f"{'='*80}\n")

    # Define regions for analysis
    comparison_regions = {
        #'heidelberg': BBOXES['heidelberg'],
        #'paris': BBOXES['paris'],
        #'beit_shemesh': BBOXES['beit_shemesh'],
        'london_15km': get_bbox_by_city("London", radius_km=15),
        'jerusalem_15km': get_bbox_by_city("Jerusalem", radius_km=15),
        'london_30km': get_bbox_by_city("London", radius_km=30),
        'jerusalem_30km': get_bbox_by_city("Jerusalem", radius_km=30)
    }

    # Output directory
    output_dir = Path(__file__).parent
    output_file = "convex-hull-analysis.csv"

    # ========================================================================
    # Building Convex Hull Analysis
    # ========================================================================
    print("\nBuilding Convex Hull Analysis")
    print("="*80)

    summary_list = []

    for location in comparison_regions.keys():
        logger.info(f"Analyzing {location}: {comparison_regions[location]}")
        print(f"\nProcessing: {location.upper()}")
        print("-"*80)

        building_metrics = get_poly_coords(
            location,
            comparison_regions[location],
            filter="type:way and building=*",
            time_param="2025-10-01",
            path=str(output_dir),
            filename=output_file
        )

        if building_metrics is not None:
            print("\nBuilding Convex Hull Metrics:")
            print(building_metrics.to_string())
            summary_list.append(building_metrics)
        else:
            logger.error(f"Failed to retrieve metrics for {location}")

    # ========================================================================
    # Visualization
    # ========================================================================
    if summary_list:
        print("\n" + "="*80)
        print("GENERATING COMPLETENESS VISUALIZATIONS")
        print("="*80 + "\n")

        # Print text summary
        print_completeness_summary(summary_list[0] if len(summary_list) == 1 else
                                  __import__('pandas').concat(summary_list, ignore_index=True))

        # Generate plots
        plot_summary_dashboard(summary_list, save_path=str(output_dir / "completeness_dashboard.png"))

    # ========================================================================
    # Optional: Road Network Analysis
    # ========================================================================
    # Uncomment to run road network analysis
    # print("\n" + "="*80)
    # print("ROAD NETWORK ANALYSIS")
    # print("="*80 + "\n")
    #
    # comparison = compare_regions(comparison_regions)
    # if comparison is not None:
    #     print("\nRoad Network Comparison Results:")
    #     print(comparison.to_string())
    #     comparison.to_csv(output_dir / "road_network_analysis.csv", index=False)

    # ========================================================================
    # Optional: Dynamic Bounding Box Generation
    # ========================================================================
    # Example: Generate bbox for a new city
    # print("\n" + "="*80)
    # print("DYNAMIC BBOX GENERATION EXAMPLE")
    # print("="*80 + "\n")
    #
    # new_city_bbox = get_bbox_by_city("London", radius_km=15)
    # if new_city_bbox:
    #     print(f"London bbox: {new_city_bbox}")
    #
    # custom_bbox = bbox_by_location(51.5074, -0.1278, radius_km=10)
    # print(f"Custom location bbox: {custom_bbox}")

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
