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
from admin_level_analysis import (
    analyze_country_by_admin_level,
    analyze_multiple_countries_by_admin_level
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
# HELPER FUNCTIONS
# ============================================================================

def should_merge_viz(viz_opts, viz_type):
    """
    Determine if visualizations should be merged based on config.

    Args:
        viz_opts: Visualization options from config
        viz_type: Type of visualization ('dashboards', 'time_series', 'correlation_plots')

    Returns:
        Boolean indicating whether to merge visualizations
    """
    # Check for specific override
    merge_key = f'merge_{viz_type}'
    if viz_opts.get(merge_key) is not None:
        return viz_opts[merge_key]

    # Fall back to general merge setting
    return viz_opts.get('merge_visualizations', False)


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

    # Check if admin-level subdivision is enabled
    subdivide_by_admin = countries_config.get('subdivide_by_admin_level', False)
    if subdivide_by_admin:
        print("\nAdministrative subdivision enabled")
        admin_level = countries_config.get('admin_level', 6)
        print(f"  Admin level: {admin_level}")
        return run_batch_countries_with_admin_subdivision(config, output_dir, data_dir)

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
        print("ERROR: No countries to process")
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
        print("ERROR: Batch analysis failed")
        return

    print(f"\nSuccessfully processed {len(results)} countries")

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
            print(f"Shapefile exported: {shp_path}")

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

    print("Visualizations complete")


def run_batch_countries_with_admin_subdivision(config, output_dir, data_dir):
    """Run batch country analysis with administrative subdivision."""
    print("\n" + "=" * 80)
    print("BATCH COUNTRY ANALYSIS WITH ADMIN SUBDIVISION")
    print("=" * 80)

    countries_config = config['countries']
    analysis_opts = config.get('analysis_options', {})
    viz_opts = config.get('visualization', {})
    admin_level = countries_config.get('admin_level', 6)
    cache_boundaries = countries_config.get('cache_boundaries', True)
    overpass_timeout = countries_config.get('overpass_timeout', 120)

    print(f"\nAdministrative level: {admin_level}")
    print(f"Boundary caching: {'Enabled' if cache_boundaries else 'Disabled'}")

    # Visualization settings
    create_viz = (viz_opts.get('create_dashboards', False) or
                  viz_opts.get('create_time_series_plots', False) or
                  viz_opts.get('create_box_plots', False))
    viz_top_n = viz_opts.get('top_n_subdivisions', 10)

    if create_viz:
        print(f"Visualizations: Enabled (top {viz_top_n} subdivisions)")
    else:
        print(f"Visualizations: Disabled")

    # Load countries list
    if countries_config.get('source') == 'csv':
        csv_path = countries_config.get('csv_path', './World_Countries.csv')
        iso_filter = countries_config.get('iso_filter')
        print(f"Loading countries from CSV: {csv_path}")
        countries_df = load_countries_from_csv(csv_path, iso_filter=iso_filter)
    else:
        iso_codes = countries_config.get('iso_codes', [])
        print(f"Processing countries: {', '.join(iso_codes)}")
        countries_df = pd.DataFrame({
            'iso_code': iso_codes,
            'country_name': iso_codes  # Will be filled from API
        })

    if countries_df is None or len(countries_df) == 0:
        print("ERROR: No countries to process")
        return

    print(f"Total countries to process: {len(countries_df)}")

    # Check if time series is enabled
    ts_config = config.get('time_series', {})
    if ts_config.get('enabled', False):
        start_year = ts_config['start_year']
        end_year = ts_config['end_year']
        interval = ts_config['interval']
        print(f"Time series: {start_year}-{end_year} ({interval})")
    else:
        start_year = None
        end_year = None
        interval = 'yearly'
        print("Mode: Snapshot analysis")

    # Convert DataFrame to list of dicts
    countries_list = []
    for _, row in countries_df.iterrows():
        countries_list.append({
            'name': row.get('country_name', row.get('iso_code')),
            'iso_code': row.get('iso_code')
        })

    # Run analysis with admin subdivision
    print("\nStarting admin-level subdivision analysis...")
    print("This will:")
    print(f"  1. Query Overpass API for admin_level={admin_level} boundaries")
    print(f"  2. Analyze each subdivision separately")
    print(f"  3. Apply chunking within subdivisions if needed")
    print(f"  4. Organize results hierarchically\n")

    results = analyze_multiple_countries_by_admin_level(
        countries_list=countries_list,
        admin_level=admin_level,
        output_dir=str(output_dir),
        start_year=start_year,
        end_year=end_year,
        interval=interval,
        filter=analysis_opts.get('filter', 'type:way and building=*'),
        chunked_threshold_km2=analysis_opts.get('chunked_threshold_km2', 5000),
        include_user_count=analysis_opts.get('include_user_count', True),
        resume=analysis_opts.get('resume', True),
        cache_boundaries=cache_boundaries,
        overpass_timeout=overpass_timeout,
        geojson_path=countries_config.get('geojson_path'),
        create_visualizations=create_viz,
        viz_top_n=viz_top_n
    )

    if not results:
        print("\nERROR: Admin-level analysis failed")
        return

    print(f"\nSuccessfully processed {len(results)} countries with admin subdivision")

    # Display summary for each country
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for iso_code, result in results.items():
        summary = result.get('summary', {})
        print(f"\n{summary.get('country_name')} ({iso_code}):")
        print(f"  Subdivisions: {summary.get('successful_subdivisions')}/{summary.get('total_subdivisions')}")
        print(f"  Buildings: {summary.get('total_buildings', 0):,}")
        print(f"  Runtime: {summary.get('runtime_minutes', 0):.1f} minutes")
        print(f"  Output: {result.get('output_dir')}")

    print("\nBatch admin-level analysis complete")


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
                include_user_count=analysis_opts.get('include_user_count', True),
                resume=analysis_opts.get('resume', True)
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
            merge_dash = should_merge_viz(viz_opts, 'dashboards')

            if merge_dash or len(summary_list) == 1:
                # Only combined dashboard
                print("Creating combined summary dashboard...")
                plot_summary_dashboard(
                    summary_list,
                    save_path=str(output_dir / "completeness_dashboard.png")
                )
                print("✓ Combined dashboard saved")
            else:
                # Separate dashboards per region + combined
                print("Creating dashboards (separate + combined)...")
                for i, summary in enumerate(summary_list):
                    region_name = summary['region'].iloc[0] if 'region' in summary.columns else f"region_{i}"
                    plot_summary_dashboard(
                        [summary],
                        save_path=str(output_dir / f"dashboard_{region_name}.png")
                    )
                # Combined dashboard
                plot_summary_dashboard(
                    summary_list,
                    save_path=str(output_dir / "completeness_dashboard_combined.png")
                )
                print(f"✓ Dashboards saved (separate per region + combined)")

        # User correlation plot
        if viz_opts.get('create_user_correlation_plot', True) and len(summary_list) > 1:
            if 'user_count' in combined_data.columns:
                print("Creating user vs complexity correlation plot...")
                plot_users_vs_complexity(
                    combined_data,
                    save_path=str(output_dir / 'user_vs_complexity.png'),
                    show_labels=False  # Use legend instead of labels for combined plot
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

        # Qualitative samples - plot example polygons
        if viz_opts.get('create_qualitative_samples', True):
            from visualization import plot_sample_polygons
            import os

            print("\nGenerating qualitative polygon samples...")

            n_samples = config['output'].get('sample_complex_buildings', 10)
            n_complex = n_samples
            n_medium = max(3, n_samples // 2)
            n_simple = max(3, n_samples // 2)

            for region_name in regions_config.keys():
                # Load detailed building data if it exists
                buildings_file = results_dir / f"{region_name}_buildings.csv"
                geom_file = results_dir / f"{region_name}_buildings_geom.geojson"

                if buildings_file.exists() and geom_file.exists():
                    try:
                        buildings_df = pd.read_csv(buildings_file)

                        if len(buildings_df) > 0:
                            sample_path = output_dir / f"{region_name}_qualitative_samples.png"
                            plot_sample_polygons(
                                buildings_df,
                                region_name.replace('_', ' ').title(),
                                geom_file_path=str(geom_file),
                                n_complex=n_complex,
                                n_medium=n_medium,
                                n_simple=n_simple,
                                save_path=str(sample_path)
                            )
                            print(f"✓ Qualitative samples: {sample_path.name}")
                    except Exception as e:
                        logger.warning(f"Could not generate qualitative samples for {region_name}: {e}")
                elif not geom_file.exists():
                    logger.info(f"Geometry file not found for {region_name}, skipping qualitative samples")
                else:
                    logger.info(f"No detailed building data found for {region_name}, skipping qualitative samples")


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

        merge_ts = should_merge_viz(viz_opts, 'time_series')
        merge_dash = should_merge_viz(viz_opts, 'dashboards')
        merge_corr = should_merge_viz(viz_opts, 'correlation_plots')

        # Individual region plots (if not merging or only one region)
        if not merge_ts or len(time_series_results) == 1:
            for region_name, ts_data in time_series_results.items():
                if viz_opts.get('create_time_series_plots', True):
                    plot_path = output_dir / f"{region_name}_time_series.png"
                    plot_time_series_complexity(
                        ts_data,
                        title=f"Complexity Evolution - {region_name.replace('_', ' ').title()}",
                        save_path=str(plot_path)
                    )
                    print(f"Time series plot: {plot_path.name}")

        # Individual dashboards (if not merging or only one region)
        if not merge_dash or len(time_series_results) == 1:
            for region_name, ts_data in time_series_results.items():
                if viz_opts.get('create_dashboards', True):
                    dashboard_path = output_dir / f"{region_name}_ts_dashboard.png"
                    plot_time_series_dashboard(
                        ts_data,
                        save_path=str(dashboard_path)
                    )
                    print(f"✓ Dashboard: {dashboard_path.name}")

        # Individual correlation plots (if not merging or only one region)
        if not merge_corr or len(time_series_results) == 1:
            for region_name, ts_data in time_series_results.items():
                if viz_opts.get('create_user_correlation_plot', True) and 'user_count' in ts_data.columns:
                    corr_path = output_dir / f"{region_name}_user_correlation.png"
                    plot_users_vs_complexity(
                        ts_data,
                        save_path=str(corr_path)
                    )
                    print(f"✓ User correlation: {corr_path.name}")

        # Combined plots (if multiple regions)
        if len(time_series_results) > 1:
            # Just concatenate - region column already exists in each dataframe
            combined_ts = pd.concat(
                [data for name, data in time_series_results.items()],
                ignore_index=True
            )

            if viz_opts.get('create_time_series_plots', True):
                suffix = "" if merge_ts else "_combined"
                plot_time_series_complexity(
                    combined_ts,
                    title="Complexity Evolution - All Regions",
                    save_path=str(output_dir / f"time_series{suffix}.png")
                )
                print(f"✓ Combined time series plot saved")

            if viz_opts.get('create_user_correlation_plot', True) and 'user_count' in combined_ts.columns:
                suffix = "" if merge_corr else "_combined"
                plot_users_vs_complexity(
                    combined_ts,
                    save_path=str(output_dir / f"user_correlation{suffix}.png"),
                    show_labels=False  # Use legend instead of labels for combined plot
                )
                print(f"✓ Combined user correlation plot saved")


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
        print("Create a config file with: python main.py --create-config batch")
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
            print(f" Unknown analysis mode: {mode}")
            return

        print(f"\n{'='*80}")
        print(f"ANALYSIS COMPLETE")
        print(f"Results saved to: {output_dir}")
        print(f"{'='*80}\n")

    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user")
        print("  Progress has been saved and can be resumed")
    except Exception as e:
        print(f"\nError during analysis: {str(e)}")
        logger.exception("Analysis failed with exception")
        raise


if __name__ == "__main__":
    main()
