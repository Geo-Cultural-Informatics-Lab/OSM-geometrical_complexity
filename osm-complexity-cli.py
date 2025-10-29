#!/usr/bin/env python3
"""
OSM Geometrical Complexity Analysis - Command Line Interface

This CLI tool provides easy access to OSM building complexity analysis
for countries, cities, and custom regions.

Usage Examples:
    # Single country snapshot
    python osm-complexity-cli.py --country Israel --snapshot

    # Country time series
    python osm-complexity-cli.py --country Germany --time-series --years 2015-2025

    # Multiple cities comparison
    python osm-complexity-cli.py --cities Jerusalem London Paris --radius 20

    # Batch from config file
    python osm-complexity-cli.py --batch batch_config.yaml

    # Countries from CSV file
    python osm-complexity-cli.py --countries-file countries_polygons/middle_east.csv
"""

import argparse
import sys
from pathlib import Path

# Import convenience API
from convenience_api import (
    analyze_country, analyze_city_comparison,
    analyze_custom_region, analyze_from_countries_file,
    analyze_multiple_countries
)
from batch_config import (
    load_batch_config, validate_config,
    print_config_summary, save_config_template
)
from api_helpers import setup_logging, logger


# ============================================================================
# CLI Argument Parser
# ============================================================================

def create_parser():
    """Create and configure argument parser."""

    parser = argparse.ArgumentParser(
        prog='osm-complexity-cli',
        description='OSM Geometrical Complexity Analysis Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Snapshot analysis:
    %(prog)s --country Israel --snapshot

  Time series analysis:
    %(prog)s --country Germany --time-series --years 2015-2025 --interval yearly

  Multiple countries:
    %(prog)s --countries Israel Jordan --time-series

  City comparison:
    %(prog)s --cities Jerusalem London Paris --radius 15

  Batch from config:
    %(prog)s --batch config.yaml

  Countries from CSV:
    %(prog)s --countries-file countries_polygons/middle_east.csv --time-series

  Custom region:
    %(prog)s --region "West Bank" --lat 31.9 --lon 35.2 --radius 30

  Generate config template:
    %(prog)s --generate-template basic --output my_config.yaml

For more information, see: https://github.com/your-repo/complex-geometry-scale
        """
    )

    # ===== Input Selection (mutually exclusive) =====
    input_group = parser.add_mutually_exclusive_group(required=False)
    input_group.add_argument('--country', type=str,
                            help='Single country name (e.g., "Israel", "Germany")')
    input_group.add_argument('--countries', nargs='+',
                            help='Multiple countries (space-separated)')
    input_group.add_argument('--city', type=str,
                            help='Single city name')
    input_group.add_argument('--cities', nargs='+',
                            help='Multiple cities for comparison')
    input_group.add_argument('--region', type=str,
                            help='Custom region name')
    input_group.add_argument('--batch', type=str,
                            help='YAML/JSON batch configuration file')
    input_group.add_argument('--countries-file', type=str,
                            help='CSV/JSON file with country definitions')
    input_group.add_argument('--generate-template', choices=['basic', 'timeseries', 'full'],
                            help='Generate configuration template file')

    # ===== Analysis Type =====
    analysis_group = parser.add_mutually_exclusive_group()
    analysis_group.add_argument('--snapshot', action='store_true',
                               help='Single time snapshot (default)')
    analysis_group.add_argument('--time-series', action='store_true',
                               help='Time series analysis')

    # ===== Snapshot Options =====
    snapshot_group = parser.add_argument_group('snapshot options')
    snapshot_group.add_argument('--timestamp', type=str,
                              help='Timestamp (YYYY-MM-DD, default: 2025-08-01)')

    # ===== Time Series Options =====
    timeseries_group = parser.add_argument_group('time series options')
    timeseries_group.add_argument('--years', type=str,
                                 help='Year range: START-END (e.g., 2015-2025)')
    timeseries_group.add_argument('--start-year', type=int, default=2015,
                                 help='Start year (default: 2015)')
    timeseries_group.add_argument('--end-year', type=int, default=2025,
                                 help='End year (default: 2025)')
    timeseries_group.add_argument('--interval', choices=['yearly', 'quarterly', 'monthly'],
                                 default='yearly',
                                 help='Time interval (default: yearly)')

    # ===== Geographic Options =====
    geo_group = parser.add_argument_group('geographic options')
    geo_group.add_argument('--lat', type=float,
                          help='Latitude for custom region')
    geo_group.add_argument('--lon', type=float,
                          help='Longitude for custom region')
    geo_group.add_argument('--radius', type=float, default=15,
                          help='Radius in km (default: 15)')
    geo_group.add_argument('--bbox', type=str,
                          help='Custom bbox: "min_lon,min_lat,max_lon,max_lat"')

    # ===== Processing Options =====
    proc_group = parser.add_argument_group('processing options')
    proc_group.add_argument('--filter', type=str,
                           default="type:way and building=*",
                           help='OSM filter query (default: buildings)')
    proc_group.add_argument('--no-chunking', action='store_true',
                           help='Disable adaptive chunking')
    proc_group.add_argument('--chunk-size', type=int, default=50,
                           help='Chunk size in km (default: 50)')
    proc_group.add_argument('--resume', action='store_true', default=True,
                           help='Resume interrupted analysis (default: enabled)')
    proc_group.add_argument('--no-resume', action='store_false', dest='resume',
                           help='Disable resume capability')

    # ===== Output Options =====
    output_group = parser.add_argument_group('output options')
    output_group.add_argument('--output', '-o', type=str,
                            help='Output directory (default: ./results/)')
    output_group.add_argument('--no-plots', action='store_true',
                            help='Skip plot generation')

    # ===== Logging Options =====
    logging_group = parser.add_argument_group('logging options')
    logging_group.add_argument('--verbose', '-v', action='store_true',
                             help='Verbose output (INFO level)')
    logging_group.add_argument('--debug', action='store_true',
                             help='Debug logging (DEBUG level)')
    logging_group.add_argument('--quiet', '-q', action='store_true',
                             help='Quiet mode (WARNING level only)')

    # ===== Other Options =====
    parser.add_argument('--version', action='version',
                       version='%(prog)s 1.0.0')

    return parser


# ============================================================================
# Command Handlers
# ============================================================================

def handle_single_country(args):
    """Handle single country analysis."""
    print(f"\n{'='*80}")
    print(f"ANALYZING COUNTRY: {args.country}")
    print(f"{'='*80}\n")

    # Determine analysis type
    analysis_type = 'time_series' if args.time_series else 'snapshot'

    # Parse year range if provided
    start_year, end_year = args.start_year, args.end_year
    if args.years:
        try:
            start_year, end_year = map(int, args.years.split('-'))
        except ValueError:
            print(f"Error: Invalid --years format '{args.years}'. Expected: START-END (e.g., 2015-2025)")
            return False

    # Run analysis
    result = analyze_country(
        country_name=args.country,
        analysis_type=analysis_type,
        timestamp=args.timestamp,
        start_year=start_year,
        end_year=end_year,
        interval=args.interval,
        output_dir=args.output,
        filter=args.filter,
        use_adaptive_chunking=not args.no_chunking,
        chunk_size_km=args.chunk_size,
        generate_plots=not args.no_plots,
        verbose=args.verbose or args.debug
    )

    if result:
        print(f"\n{'='*80}")
        print(f"ANALYSIS COMPLETE")
        print(f"{'='*80}")
        print(f"Output directory: {result['output_dir']}")
        if result.get('plots_saved'):
            print(f"Plots saved: {len(result['plots_saved'])} files")
        return True
    else:
        print("\nAnalysis failed. Check logs for details.")
        return False


def handle_multiple_countries(args):
    """Handle multiple countries analysis."""
    countries = args.countries

    print(f"\n{'='*80}")
    print(f"ANALYZING {len(countries)} COUNTRIES")
    print(f"{'='*80}\n")

    # Determine analysis type
    analysis_type = 'time_series' if args.time_series else 'snapshot'

    # Parse year range
    start_year, end_year = args.start_year, args.end_year
    if args.years:
        try:
            start_year, end_year = map(int, args.years.split('-'))
        except ValueError:
            print(f"Error: Invalid --years format. Expected: START-END")
            return False

    # Run analysis
    results = analyze_multiple_countries(
        countries=countries,
        analysis_type=analysis_type,
        output_dir=args.output,
        timestamp=args.timestamp,
        start_year=start_year,
        end_year=end_year,
        interval=args.interval,
        filter=args.filter,
        use_adaptive_chunking=not args.no_chunking,
        generate_plots=not args.no_plots
    )

    if results:
        print(f"\n{'='*80}")
        print(f"BATCH ANALYSIS COMPLETE")
        print(f"{'='*80}")
        print(f"Successful: {len(results)}/{len(countries)} countries")
        return True
    else:
        print("\nBatch analysis failed.")
        return False


def handle_city_comparison(args):
    """Handle city comparison analysis."""
    cities = args.cities

    print(f"\n{'='*80}")
    print(f"COMPARING {len(cities)} CITIES")
    print(f"{'='*80}\n")

    result = analyze_city_comparison(
        cities=cities,
        radius_km=args.radius,
        timestamp=args.timestamp or "2025-08-01",
        output_dir=args.output,
        filter=args.filter,
        generate_plots=not args.no_plots
    )

    if result is not None:
        print(f"\n{'='*80}")
        print(f"COMPARISON COMPLETE")
        print(f"{'='*80}")
        print(f"\nSummary Statistics:")
        print(result.groupby('city')['mean_ratio'].describe())
        return True
    else:
        print("\nComparison failed.")
        return False


def handle_custom_region(args):
    """Handle custom region analysis."""
    print(f"\n{'='*80}")
    print(f"ANALYZING CUSTOM REGION: {args.region}")
    print(f"{'='*80}\n")

    # Determine analysis type
    analysis_type = 'time_series' if args.time_series else 'snapshot'

    # Parse year range
    start_year, end_year = args.start_year, args.end_year
    if args.years:
        try:
            start_year, end_year = map(int, args.years.split('-'))
        except ValueError:
            print(f"Error: Invalid --years format. Expected: START-END")
            return False

    result = analyze_custom_region(
        region_name=args.region,
        bbox=args.bbox,
        lat=args.lat,
        lon=args.lon,
        radius_km=args.radius,
        analysis_type=analysis_type,
        timestamp=args.timestamp,
        start_year=start_year,
        end_year=end_year,
        interval=args.interval,
        filter=args.filter,
        output_dir=args.output
    )

    if result:
        print(f"\n{'='*80}")
        print(f"ANALYSIS COMPLETE")
        print(f"{'='*80}")
        print(f"Output directory: {result['output_dir']}")
        return True
    else:
        print("\nAnalysis failed.")
        return False


def handle_batch_config(args):
    """Handle batch configuration file."""
    config_path = args.batch

    print(f"\n{'='*80}")
    print(f"LOADING BATCH CONFIGURATION")
    print(f"{'='*80}\n")

    try:
        # Load configuration
        config = load_batch_config(config_path)

        # Print summary
        print_config_summary(config)

        # Validate
        errors = validate_config(config)
        if errors:
            print("Configuration errors found:")
            for error in errors:
                print(f"  - {error}")
            return False

        print("Configuration valid!\n")

        # Not implemented yet - would need to execute batch config
        print("Note: Batch execution from config not yet implemented in CLI.")
        print("Use the Python API with load_batch_config() instead.")
        return True

    except Exception as e:
        print(f"Error loading configuration: {str(e)}")
        return False


def handle_countries_file(args):
    """Handle countries file processing."""
    csv_path = args.countries_file

    print(f"\n{'='*80}")
    print(f"LOADING COUNTRIES FROM FILE")
    print(f"{'='*80}\n")

    # Determine analysis type
    analysis_type = 'time_series' if args.time_series else 'snapshot'

    # Parse year range
    start_year, end_year = args.start_year, args.end_year
    if args.years:
        try:
            start_year, end_year = map(int, args.years.split('-'))
        except ValueError:
            print(f"Error: Invalid --years format. Expected: START-END")
            return False

    result = analyze_from_countries_file(
        csv_path=csv_path,
        analysis_type=analysis_type,
        output_dir=args.output,
        timestamp=args.timestamp,
        start_year=start_year,
        end_year=end_year,
        interval=args.interval,
        filter=args.filter,
        chunk_size_km=args.chunk_size,
        use_adaptive_chunking=not args.no_chunking
    )

    if result:
        print(f"\n{'='*80}")
        print(f"BATCH PROCESSING COMPLETE")
        print(f"{'='*80}")
        print(f"Dataset: {result['dataset_name']}")
        print(f"Processed: {len(result['results'])} countries")
        if result.get('comparison_file'):
            print(f"Comparison file: {result['comparison_file']}")
        return True
    else:
        print("\nBatch processing failed.")
        return False


def handle_generate_template(args):
    """Handle configuration template generation."""
    template_type = args.generate_template
    output_path = args.output or f"config_template_{template_type}.yaml"

    print(f"\nGenerating {template_type} configuration template...")

    try:
        save_config_template(output_path, template_type)
        print(f"✓ Template saved to: {output_path}")
        print(f"\nEdit this file and run:")
        print(f"  python osm-complexity-cli.py --batch {output_path}")
        return True
    except Exception as e:
        print(f"Error generating template: {str(e)}")
        return False


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main CLI entry point."""

    # Create parser
    parser = create_parser()

    # Parse arguments
    args = parser.parse_args()

    # Setup logging
    if args.debug:
        log_level = 'DEBUG'
    elif args.verbose:
        log_level = 'INFO'
    elif args.quiet:
        log_level = 'WARNING'
    else:
        log_level = 'INFO'

    setup_logging(console_level=log_level)

    # Handle commands
    try:
        # Generate template
        if args.generate_template:
            success = handle_generate_template(args)

        # Single country
        elif args.country:
            success = handle_single_country(args)

        # Multiple countries
        elif args.countries:
            success = handle_multiple_countries(args)

        # Single city (treat as single-city comparison)
        elif args.city:
            args.cities = [args.city]
            success = handle_city_comparison(args)

        # Multiple cities
        elif args.cities:
            success = handle_city_comparison(args)

        # Custom region
        elif args.region:
            success = handle_custom_region(args)

        # Batch config
        elif args.batch:
            success = handle_batch_config(args)

        # Countries file
        elif args.countries_file:
            success = handle_countries_file(args)

        # No command specified
        else:
            parser.print_help()
            print("\nError: No analysis type specified.")
            print("Use one of: --country, --countries, --city, --cities, --region, --batch, --countries-file")
            sys.exit(1)

        # Exit with appropriate code
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user.")
        sys.exit(130)

    except Exception as e:
        logger.exception("Unexpected error occurred")
        print(f"\nFatal error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
