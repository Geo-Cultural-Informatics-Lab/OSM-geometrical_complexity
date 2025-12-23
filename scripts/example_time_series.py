"""
Example script for Time Series Analysis

This script demonstrates how to use the time series analysis module
to track OSM mapping quality evolution over time.
"""

import logging
from pathlib import Path
from utils.bbox_utils import get_bbox_by_city, BBOXES
from time_series_analysis import (
    analyze_region_time_series,
    compare_regions_time_series,
    generate_time_intervals
)
from visualization.visualization import (
    plot_time_series_complexity,
    plot_time_series_dashboard,
    plot_growth_comparison
)
from api_helpers import setup_logging


def example_single_region_time_series():
    """
    Example: Analyze a single region's evolution over time.
    """
    print("\n" + "="*80)
    print("EXAMPLE 1: Single Region Time Series Analysis")
    print("="*80)

    # Setup logging
    log_file = 'logs/time_series_example.log'
    logger = setup_logging(log_file=log_file, log_level=logging.DEBUG, console_level=logging.INFO)

    # Define region
    region_name = "heidelberg"
    bbox = BBOXES['heidelberg']  # Or use: get_bbox_by_city("Heidelberg", radius_km=15)

    # Output directory
    output_dir = Path(__file__).parent / "data" / "time_series"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run time series analysis
    print("\nAnalyzing Heidelberg from 2015-2025 (yearly snapshots)...")
    ts_data = analyze_region_time_series(
        region_name=region_name,
        bbox=bbox,
        start_year=2015,
        end_year=2025,
        interval='yearly',  # Options: 'yearly', 'quarterly', 'monthly'
        filter="type:way and building=*",
        path=str(output_dir),
        base_filename="heidelberg_buildings",
        resume=True  # Resume if interrupted
    )

    if ts_data is not None:
        print("\n✓ Time series data collected:")
        print(ts_data[['timestamp', 'mean_ratio', 'median_ratio', 'mean_area']].to_string())

        # Create visualizations
        print("\nGenerating visualizations...")
        plot_time_series_complexity(
            ts_data,
            save_path=str(output_dir / "heidelberg_complexity_evolution.png")
        )
        plot_time_series_dashboard(
            ts_data,
            save_path=str(output_dir / "heidelberg_dashboard.png")
        )
        print("✓ Visualizations saved")


def example_multi_region_comparison():
    """
    Example: Compare multiple regions' evolution over time.
    """
    print("\n" + "="*80)
    print("EXAMPLE 2: Multi-Region Time Series Comparison")
    print("="*80)

    # Setup logging
    log_file = 'logs/time_series_comparison.log'
    logger = setup_logging(log_file=log_file, log_level=logging.DEBUG, console_level=logging.INFO)

    # Define regions to compare
    regions = {
        'heidelberg': BBOXES['heidelberg'],
        'paris': BBOXES['paris'],
        'beit_shemesh': BBOXES['beit_shemesh']
    }

    # Output directory
    output_dir = Path(__file__).parent / "data" / "time_series_comparison"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run comparison
    print(f"\nComparing {len(regions)} regions from 2018-2025 (yearly)...")
    comparison_data = compare_regions_time_series(
        regions_dict=regions,
        start_year=2018,
        end_year=2025,
        interval='yearly',
        filter="type:way and building=*",
        path=str(output_dir),
        resume=True
    )

    if comparison_data is not None:
        print("\n✓ Comparison data collected:")
        print(comparison_data.groupby('region')['mean_ratio'].describe())

        # Create comparison visualizations
        print("\nGenerating comparison visualizations...")

        plot_time_series_complexity(
            comparison_data,
            save_path=str(output_dir / "multi_region_comparison.png"),
            title="OSM Mapping Quality Comparison"
        )

        plot_growth_comparison(
            comparison_data,
            save_path=str(output_dir / "growth_comparison.png")
        )

        plot_time_series_dashboard(
            comparison_data,
            save_path=str(output_dir / "comparison_dashboard.png")
        )

        print("✓ Comparison visualizations saved")


def example_quarterly_analysis():
    """
    Example: Higher resolution quarterly analysis.
    """
    print("\n" + "="*80)
    print("EXAMPLE 3: Quarterly Time Series (High Resolution)")
    print("="*80)

    # Setup logging
    log_file = 'logs/time_series_quarterly.log'
    logger = setup_logging(log_file=log_file, log_level=logging.DEBUG, console_level=logging.INFO)

    # Use smaller region for quarterly analysis (more data points)
    region_name = "beit_shemesh"
    bbox = BBOXES['beit_shemesh']

    # Output directory
    output_dir = Path(__file__).parent / "data" / "time_series_quarterly"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run quarterly analysis for recent years
    print("\nAnalyzing recent years with quarterly resolution...")
    ts_data = analyze_region_time_series(
        region_name=region_name,
        bbox=bbox,
        start_year=2022,
        end_year=2025,
        interval='quarterly',  # Quarterly snapshots
        filter="type:way and building=*",
        path=str(output_dir),
        base_filename="beit_shemesh_buildings",
        resume=True
    )

    if ts_data is not None:
        print("\n✓ Quarterly time series data collected:")
        print(ts_data[['timestamp', 'mean_ratio']].to_string())

        # Create visualization
        plot_time_series_complexity(
            ts_data,
            save_path=str(output_dir / "quarterly_evolution.png"),
            title="Quarterly Mapping Quality Evolution"
        )
        print("✓ Quarterly visualization saved")


def example_time_intervals():
    """
    Example: Generate and inspect time intervals.
    """
    print("\n" + "="*80)
    print("EXAMPLE 4: Time Interval Generation")
    print("="*80)

    # Generate yearly intervals
    yearly = generate_time_intervals(2015, 2025, 'yearly')
    print(f"\nYearly intervals (2015-2025): {len(yearly)} points")
    print(yearly)

    # Generate quarterly intervals
    quarterly = generate_time_intervals(2023, 2025, 'quarterly')
    print(f"\nQuarterly intervals (2023-2025): {len(quarterly)} points")
    print(quarterly)

    # Generate monthly intervals (warning: lots of data!)
    monthly = generate_time_intervals(2024, 2025, 'monthly')
    print(f"\nMonthly intervals (2024-2025): {len(monthly)} points")
    print(monthly[:6], "...", monthly[-3:])


if __name__ == "__main__":
    print("\n" + "#"*80)
    print("# OSM GEOMETRICAL COMPLEXITY - TIME SERIES ANALYSIS EXAMPLES")
    print("#"*80)

    # Create output directories
    Path("logs").mkdir(exist_ok=True)
    Path("data/time_series").mkdir(parents=True, exist_ok=True)

    # Run examples
    # Uncomment the examples you want to run:

    # Example 1: Single region over time
    # example_single_region_time_series()

    # Example 2: Compare multiple regions
    # example_multi_region_comparison()

    # Example 3: Quarterly high-resolution analysis
    # example_quarterly_analysis()

    # Example 4: Just show time interval generation
    example_time_intervals()

    print("\n" + "#"*80)
    print("# EXAMPLES COMPLETE")
    print("#"*80 + "\n")

    print("\nTo run other examples, uncomment them in the __main__ section.")
    print("\nUsage tips:")
    print("  - Start with yearly intervals to get overview")
    print("  - Use quarterly/monthly for detailed recent trends")
    print("  - Large regions will use automatic chunking")
    print("  - All analyses support resume capability")
