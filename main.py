"""
Main script for OSM Geometrical Complexity Analysis

This script provides a comprehensive interface for analyzing OSM building geometry
completeness across regions, countries, and time periods using YAML configuration.

Usage:
    python main.py --config config.yaml
    python main.py --config config_templates/example_batch_countries.yaml
    python main.py --create-config batch
"""

import argparse
import logging
from pathlib import Path
import pandas as pd

# Core modules
from api_helpers import setup_logging
from geometry_analysis import get_poly_coords, get_poly_coords_chunked
from bbox_utils import get_bbox_by_city, BBOXES
from chunking_utils import bbox_area_km2
from time_series_analysis import analyze_region_time_series

# New modules
from config_loader import load_config, validate_config, merge_with_defaults, save_config_template
from batch_country_analysis import (
    load_countries_from_csv,
    analyze_countries_batch
)
from gis_export import export_summary_to_shapefile, export_buildings_to_shapefile
from visualization import (
    plot_summary_dashboard,
    print_completeness_summary,
    plot_time_series_complexity,
    plot_time_series_dashboard,
    plot_complexity_boxplots,
    plot_users_vs_complexity
)


# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='OSM Geometrical Complexity Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Run analysis with config file
  python main.py --config config.yaml
  python main.py --config config_templates/example_batch_countries.yaml

  # Create example configuration
  python main.py --create-config batch
  python main.py --create-config time_series
        '''
    )

    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to YAML configuration file (default: config.yaml)'
    )

    parser.add_argument(
        '--create-config',
        choices=['basic', 'time_series', 'batch', 'full'],
        help='Create example configuration file and exit'
    )

    return parser.parse_args()


# ============================================================================
# BATCH COUNTRY ANALYSIS
# ============================================================================

def run_batch_countries_analysis(config, output_dir, data_dir):
    """Run batch country analysis."""
    print("\n" + "=" * 80)
    print("BATCH COUNTRY ANALYSIS MODE")
    print("=" * 80)

    countries_config = config['countries']
    analysis_opts = config.get('analysis_options', {})
    viz_opts = config.get('visualization', {})

    # Load countries list
    if countries_config.get('source') == 'csv':
        csv_path = countries_config.get('csv_path', './World_Countries.csv')
        iso_filter = countries_config.get('iso_filter')
        print(f"\nLoading countries from CSV: {csv_path}")
        countries_df = load_countries_from_csv(csv_path, iso_filter=iso_filter)
    else:
        # Manual list of ISO codes
        iso_codes = countries_config.get('iso_codes', [])
        print(f"\nProcessing countries: {', '.join(iso_codes)}")
        countries_df = pd.DataFrame({
            'iso_code': iso_codes,
            'country_name': iso_codes  # Will be filled from GeoJSON
        })

    if countries_df is None or len(countries_df) == 0:
        print("❌ No countries to process")
        return

    print(f"Total countries to process: {len(countries_df)}")

    # Check if time series is enabled
    ts_config = config.get('time_series', {})
    if ts_config.get('enabled', False):
        start_year = ts_config['start_year']
        end_year = ts_config['end_year']
        interval = ts_config['interval']
        print(f"Time series enabled: {start_year}-{end_year} ({interval})")
    else:
        start_year = None
        end_year = None
        interval = 'yearly'
        print("Running snapshot analysis for each country")

    # Run batch analysis
    print("\nStarting batch processing...")
    results = analyze_countries_batch(
        countries_df,
        geojson_path=countries_config['geojson_path'],
        output_dir=str(output_dir),
        start_year=start_year,
        end_year=end_year,
        interval=interval,
        filter=analysis_opts.get('filter', 'type:way and building=*'),
        chunked_threshold_km2=analysis_opts.get('chunked_threshold_km2', 5000),
        include_user_count=analysis_opts.get('include_user_count', True),
        resume=analysis_opts.get('resume', True)
    )

    if results is None:
        print("❌ Batch analysis failed")
        return

    print(f"\n✓ Successfully processed {len(results)} countries")

    # Export shapefile
    if config['output'].get('export_shapefile', False):
        print("\nExporting results to shapefile...")
        shp_path = export_summary_to_shapefile(
            results,
            geojson_path=countries_config['geojson_path'],
            output_dir=str(output_dir),
            output_name='batch_countries_summary'
        )
        if shp_path:
            print(f"✓ Shapefile exported: {shp_path}")

    # Create visualizations
    print("\nGenerating visualizations...")

    if viz_opts.get('create_dashboards', True):
        print("  - Creating summary dashboard...")
        plot_summary_dashboard(
            [results],
            save_path=str(output_dir / 'batch_dashboard.png')
        )

    if viz_opts.get('create_user_correlation_plot', True) and 'user_count' in results.columns:
        print("  - Creating user vs complexity correlation plot...")
        plot_users_vs_complexity(
            results,
            save_path=str(output_dir / 'user_vs_complexity.png')
        )

    print("✓ Visualizations complete")


# ============================================================================
# SNAPSHOT ANALYSIS
# ============================================================================

def run_snapshot_analysis(config, output_dir):
    """Run snapshot analysis for configured regions."""
    print("\n" + "=" * 80)
    print("SNAPSHOT ANALYSIS MODE")
    print(f"Timestamp: {config['analysis'].get('timestamp', '2025-08-01')}")
    print("=" * 80)

    # Create directories
    results_dir = output_dir / "results"
    logs_dir = output_dir / "logs"
    results_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)

    # Get configuration
    regions_config = config.get('regions', {})
    analysis_opts = config.get('analysis_options', {})
    viz_opts = config.get('visualization', {})
    snapshot_time = config['analysis'].get('timestamp', '2025-08-01')
    chunked_threshold = analysis_opts.get('chunked_threshold_km2', 5000)

    summary_list = []

    # Process each region
    for region_name, region_cfg in regions_config.items():
        print(f"\n{'='*80}")
        print(f"Processing: {region_name.upper()}")
        print(f"{'='*80}")

        # Setup logging for this region
        log_file = logs_dir / f'analysis_{region_name}.log'
        logger = setup_logging(
            log_file=str(log_file),
            log_level=logging.DEBUG,
            console_level=logging.INFO
        )

        # Get bounding box
        if region_cfg['type'] == 'city':
            bbox = get_bbox_by_city(region_cfg['name'], radius_km=region_cfg.get('radius_km', 15))
        elif region_cfg['type'] == 'bbox':
            bbox = region_cfg['bbox']
        elif region_cfg['type'] == 'predefined':
            bbox = BBOXES.get(region_cfg['name'])
        else:
            logger.error(f"Unknown region type: {region_cfg['type']}")
            continue

        if bbox is None:
            logger.error(f"Could not get bounding box for {region_name}")
            continue

        logger.info(f"Analyzing {region_name}: {bbox}")

        # Determine if chunking is needed
        area_km2 = bbox_area_km2(bbox)
        use_chunked = area_km2 > chunked_threshold

        # Run analysis
        if use_chunked:
            logger.info(f"Large region ({area_km2:.0f} km²) - using chunked processing")
            result = get_poly_coords_chunked(
                region_name,
                bbox,
                filter=analysis_opts.get('filter', 'type:way and building=*'),
                time_param=snapshot_time,
                path=str(results_dir),
                filename=f"{region_name}_buildings.csv",
                use_adaptive_chunking=True,
                resume=analysis_opts.get('resume', True),
                cleanup_after=True
            )
        else:
            logger.info(f"Small region ({area_km2:.0f} km²) - using direct processing")
            result = get_poly_coords(
                region_name,
                bbox,
                filter=analysis_opts.get('filter', 'type:way and building=*'),
                time_param=snapshot_time,
                path=str(results_dir),
                filename=f"{region_name}_buildings.csv",
                include_counts=analysis_opts.get('include_building_count', True),
                include_user_count=analysis_opts.get('include_user_count', True)
            )

        if result is not None:
            print("\nBuilding Metrics:")
            print(result.to_string())
            summary_list.append(result)
        else:
            logger.error(f"Failed to analyze {region_name}")

    # Generate visualizations and exports
    if summary_list:
        print("\n" + "=" * 80)
        print("GENERATING OUTPUTS")
        print("=" * 80 + "\n")

        combined_data = summary_list[0] if len(summary_list) == 1 else \
                       pd.concat(summary_list, ignore_index=True)

        # Print summary
        print_completeness_summary(combined_data)

        # Create dashboards
        if viz_opts.get('create_dashboards', True):
            print("Creating summary dashboard...")
            plot_summary_dashboard(
                summary_list,
                save_path=str(output_dir / "completeness_dashboard.png")
            )
            print("✓ Dashboard saved")

        # User correlation plot
        if viz_opts.get('create_user_correlation_plot', True) and len(summary_list) > 1:
            if 'user_count' in combined_data.columns:
                print("Creating user vs complexity correlation plot...")
                plot_users_vs_complexity(
                    combined_data,
                    save_path=str(output_dir / 'user_vs_complexity.png')
                )
                print("✓ User correlation plot saved")

        # Export shapefiles
        if config['output'].get('export_shapefile', False):
            print("Exporting to shapefile...")
            export_summary_to_shapefile(
                combined_data,
                output_dir=str(output_dir),
                output_name='snapshot_summary'
            )
            print("✓ Shapefile exported")


# ============================================================================
# TIME SERIES ANALYSIS
# ============================================================================

def run_time_series_analysis(config, output_dir, data_dir):
    """Run time series analysis for configured regions."""
    ts_config = config['time_series']

    print("\n" + "=" * 80)
    print("TIME SERIES ANALYSIS MODE")
    print(f"Period: {ts_config['start_year']}-{ts_config['end_year']}")
    print(f"Interval: {ts_config['interval']}")
    print("=" * 80)

    # Create directories
    data_dir.mkdir(exist_ok=True)
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Get configuration
    regions_config = config.get('regions', {})
    analysis_opts = config.get('analysis_options', {})
    viz_opts = config.get('visualization', {})

    time_series_results = {}

    # Process each region
    for region_name, region_cfg in regions_config.items():
        print(f"\n{'=' * 80}")
        print(f"TIME SERIES: {region_name.upper()}")
        print("=" * 80)

        # Setup logging
        log_file = logs_dir / f'timeseries_{region_name}.log'
        logger = setup_logging(
            log_file=str(log_file),
            log_level=logging.DEBUG,
            console_level=logging.INFO
        )

        # Get bounding box
        if region_cfg['type'] == 'city':
            bbox = get_bbox_by_city(region_cfg['name'], radius_km=region_cfg.get('radius_km', 15))
        elif region_cfg['type'] == 'bbox':
            bbox = region_cfg['bbox']
        elif region_cfg['type'] == 'predefined':
            bbox = BBOXES.get(region_cfg['name'])
        else:
            logger.error(f"Unknown region type: {region_cfg['type']}")
            continue

        if bbox is None:
            logger.error(f"Could not get bounding box for {region_name}")
            continue

        # Run time series analysis
        ts_data = analyze_region_time_series(
            region_name=region_name,
            bbox=bbox,
            start_year=ts_config['start_year'],
            end_year=ts_config['end_year'],
            interval=ts_config['interval'],
            filter=analysis_opts.get('filter', 'type:way and building=*'),
            path=str(data_dir / "time_series"),
            base_filename=f"{region_name}_ts",
            use_chunked_threshold_km2=analysis_opts.get('chunked_threshold_km2', 5000),
            resume=analysis_opts.get('resume', True)
        )

        if ts_data is not None:
            time_series_results[region_name] = ts_data

            # Print summary
            print(f"\nTime series complete: {len(ts_data)} snapshots")
            print("\nComplexity Evolution:")
            cols_to_show = ['timestamp', 'mean_ratio', 'median_ratio']
            if 'building_count' in ts_data.columns:
                cols_to_show.append('building_count')
            if 'user_count' in ts_data.columns:
                cols_to_show.append('user_count')
            print(ts_data[cols_to_show].to_string())
        else:
            logger.error(f"Failed to analyze time series for {region_name}")

    # Generate visualizations
    if time_series_results:
        print("\n" + "=" * 80)
        print("GENERATING TIME SERIES VISUALIZATIONS")
        print("=" * 80 + "\n")

        for region_name, ts_data in time_series_results.items():
            # Individual region plot
            if viz_opts.get('create_time_series_plots', True):
                plot_path = output_dir / f"{region_name}_time_series.png"
                plot_time_series_complexity(
                    ts_data,
                    title=f"Complexity Evolution - {region_name.replace('_', ' ').title()}",
                    save_path=str(plot_path)
                )
                print(f"✓ Time series plot: {plot_path.name}")

            # Detailed dashboard
            if viz_opts.get('create_dashboards', True):
                dashboard_path = output_dir / f"{region_name}_ts_dashboard.png"
                plot_time_series_dashboard(
                    ts_data,
                    save_path=str(dashboard_path)
                )
                print(f"✓ Dashboard: {dashboard_path.name}")

            # User correlation
            if viz_opts.get('create_user_correlation_plot', True) and 'user_count' in ts_data.columns:
                corr_path = output_dir / f"{region_name}_user_correlation.png"
                plot_users_vs_complexity(
                    ts_data,
                    save_path=str(corr_path)
                )
                print(f"✓ User correlation: {corr_path.name}")



def main():
    # Parse arguments
    args = parse_arguments()

    # Handle config creation
    if args.create_config:
        output_file = f'config_{args.create_config}.yaml'
        if save_config_template(output_file, args.create_config):
            print(f"\n✓ Created example configuration: {output_file}")
            print(f"  Edit this file and run: python main.py --config {output_file}\n")
        return

    # Load and validate configuration
    print(f"\nLoading configuration from: {args.config}")
    config = load_config(args.config)

    if config is None:
        print("Failed to load configuration")
        print("   Create a config file with: python main.py --create-config batch")
        return

    # Validate configuration
    is_valid, error_message = validate_config(config)
    if not is_valid:
        print(f"Configuration error: {error_message}")
        return

    # Merge with defaults
    config = merge_with_defaults(config)

    # Create output directories
    output_dir = Path(config['output']['directory'])
    output_dir.mkdir(parents=True, exist_ok=True)

    data_dir = Path(config['output'].get('data_directory', './data'))
    data_dir.mkdir(parents=True, exist_ok=True)

    logs_dir = Path(config['output'].get('logs_directory', './logs'))
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Setup main logging
    log_file = logs_dir / 'main_analysis.log'
    logger = setup_logging(log_file=str(log_file))

    # Display configuration
    mode = config['analysis']['mode']
    print(f"\n{'='*80}")
    print(f"OSM GEOMETRICAL COMPLEXITY ANALYSIS")
    print(f"Mode: {mode.upper()}")
    print(f"Output directory: {output_dir}")
    print(f"{'='*80}")

    # Dispatch to appropriate analysis mode
    try:
        if mode == 'batch_countries':
            run_batch_countries_analysis(config, output_dir, data_dir)
        elif mode == 'time_series':
            run_time_series_analysis(config, output_dir, data_dir)
        elif mode == 'snapshot':
            run_snapshot_analysis(config, output_dir)
        else:
            print(f"❌ Unknown analysis mode: {mode}")
            return

        print(f"\n{'='*80}")
        print(f"✓ ANALYSIS COMPLETE")
        print(f"Results saved to: {output_dir}")
        print(f"{'='*80}\n")

    except KeyboardInterrupt:
        print("\n\n⚠ Analysis interrupted by user")
        print("  Progress has been saved and can be resumed")
    except Exception as e:
        print(f"\n❌ Error during analysis: {str(e)}")
        logger.exception("Analysis failed with exception")
        raise


if __name__ == "__main__":
    main()
