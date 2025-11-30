"""
Convenience API for OSM Geometrical Complexity Analysis

This module provides high-level wrapper functions for common analysis workflows,
making it easy to analyze countries, cities, and custom regions without dealing
with low-level API details.
"""

import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Import from existing modules
from api_helpers import setup_logging, logger
from bbox_utils import (
    get_country_bbox, get_bbox_by_city, bbox_by_location,
    load_countries_from_file
)
from geometry_analysis import get_poly_coords, get_poly_coords_chunked
from time_series_analysis import analyze_region_time_series, compare_regions_time_series
from visualization import (
    plot_summary_dashboard, plot_time_series_complexity,
    plot_time_series_dashboard, print_completeness_summary
)
from chunking_utils import bbox_area_km2


# ============================================================================
# Output Directory Management
# ============================================================================

def organize_output_directory(
    base_dir: str,
    dataset_name: str,
    region_name: str,
    analysis_type: str,
    time_range: str = None
) -> Dict[str, Path]:
    """
    Create organized output directory structure.

    Structure:
    {base_dir}/
      └── {dataset_name}/
          └── {region_name}/
              └── {analysis_type}_{time_info}/
                  ├── data/
                  ├── plots/
                  ├── logs/
                  └── results/

    Args:
        base_dir: Base output directory (e.g., './results')
        dataset_name: Dataset/batch name (e.g., 'middle_east')
        region_name: Region/country name
        analysis_type: 'snapshot' or 'time_series'
        time_range: Optional timestamp or range (e.g., '2025' or '2015-2025')

    Returns:
        Dict with Path objects for each subdirectory

    Example:
        >>> paths = organize_output_directory(
        ...     "./results",
        ...     "middle_east",
        ...     "israel",
        ...     "time_series",
        ...     "2015-2025"
        ... )
    """
    base_path = Path(base_dir)

    # Create directory path
    if time_range:
        analysis_dir = base_path / dataset_name / region_name / f"{analysis_type}_{time_range}"
    else:
        timestamp = datetime.now().strftime('%Y%m%d')
        analysis_dir = base_path / dataset_name / region_name / f"{analysis_type}_{timestamp}"

    # Create subdirectories
    paths = {
        'root': analysis_dir,
        'data': analysis_dir / 'data',
        'plots': analysis_dir / 'plots',
        'logs': analysis_dir / 'logs',
        'results': analysis_dir / 'results'
    }

    # Create all directories
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)

    return paths


# ============================================================================
# Single Country Analysis
# ============================================================================

def analyze_country(
    country_name: str,
    analysis_type: str = 'snapshot',
    timestamp: str = None,
    start_year: int = 2015,
    end_year: int = 2025,
    interval: str = 'yearly',
    output_dir: str = None,
    filter: str = "type:way and building=*",
    use_adaptive_chunking: bool = True,
    chunk_size_km: int = 50,
    generate_plots: bool = True,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Analyze OSM building complexity for an entire country.

    Args:
        country_name: Name of country (e.g., "Israel", "Germany")
        analysis_type: 'snapshot' or 'time_series'
        timestamp: ISO date for snapshot (default: 2025-08-01)
        start_year: Start year for time series
        end_year: End year for time series
        interval: 'yearly', 'quarterly', or 'monthly' for time series
        output_dir: Output directory (default: ./results/{country}/)
        filter: OSM filter query
        use_adaptive_chunking: Auto-chunk large regions
        chunk_size_km: Chunk size in kilometers
        generate_plots: Create visualizations
        verbose: Print progress information

    Returns:
        Dict with keys: 'summary', 'plots_saved', 'output_dir'

    Example:
        >>> results = analyze_country("Israel", interval='yearly')
        >>> print(results['summary'])
    """
    # Setup logging
    if verbose:
        logger_instance = setup_logging(console_level='INFO')
    else:
        logger_instance = setup_logging(console_level='WARNING')

    logger.info(f"Analyzing country: {country_name}")

    # Get country bounding box
    bbox = get_country_bbox(country_name)
    if bbox is None:
        logger.error(f"Could not get bounding box for country: {country_name}")
        return None

    # Setup output directory
    if output_dir is None:
        output_dir = f"./results/{country_name.lower().replace(' ', '_')}"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine if chunking is needed
    area_km2 = bbox_area_km2(bbox)
    use_chunked = use_adaptive_chunking and area_km2 > 5000

    logger.info(f"Country area: {area_km2:,.0f} km²")
    logger.info(f"Using {'chunked' if use_chunked else 'direct'} processing")

    # Snapshot analysis
    if analysis_type == 'snapshot':
        if timestamp is None:
            timestamp = "2025-08-01"

        logger.info(f"Running snapshot analysis for {timestamp}")

        if use_chunked:
            summary = get_poly_coords_chunked(
                region_name=country_name,
                bounds=bbox,
                filter=filter,
                time_param=timestamp,
                path=str(output_dir / 'data'),
                filename=f"{country_name.lower()}_buildings.csv",
                chunk_size_km=chunk_size_km,
                resume=True,
                cleanup_after=True
            )
        else:
            summary = get_poly_coords(
                region_name=country_name,
                bounds=bbox,
                filter=filter,
                time_param=timestamp,
                path=str(output_dir / 'data'),
                filename=f"{country_name.lower()}_buildings.csv"
            )

        # Generate plots
        plots_saved = []
        if generate_plots and summary is not None:
            plot_path = output_dir / 'plots' / f"{country_name.lower()}_dashboard.png"
            plot_path.parent.mkdir(parents=True, exist_ok=True)

            plot_summary_dashboard(
                [summary],
                save_path=str(plot_path)
            )
            plots_saved.append(str(plot_path))
            logger.info(f"Dashboard saved: {plot_path}")

        return {
            'analysis_type': 'snapshot',
            'country': country_name,
            'timestamp': timestamp,
            'summary': summary,
            'plots_saved': plots_saved,
            'output_dir': str(output_dir)
        }

    # Time series analysis
    elif analysis_type == 'time_series':
        logger.info(f"Running time series analysis: {start_year}-{end_year} ({interval})")

        ts_data = analyze_region_time_series(
            region_name=country_name,
            bbox=bbox,
            start_year=start_year,
            end_year=end_year,
            interval=interval,
            filter=filter,
            path=str(output_dir / 'data' / 'time_series'),
            base_filename=f"{country_name.lower()}_ts",
            use_chunked_threshold_km2=5000 if use_adaptive_chunking else float('inf'),
            resume=True
        )

        # Generate plots
        plots_saved = []
        if generate_plots and ts_data is not None:
            plots_dir = output_dir / 'plots'
            plots_dir.mkdir(parents=True, exist_ok=True)

            # Time series plot
            ts_plot_path = plots_dir / f"{country_name.lower()}_time_series.png"
            plot_time_series_complexity(
                ts_data,
                title=f"Complexity Evolution - {country_name}",
                save_path=str(ts_plot_path)
            )
            plots_saved.append(str(ts_plot_path))

            # Dashboard
            dashboard_path = plots_dir / f"{country_name.lower()}_ts_dashboard.png"
            plot_time_series_dashboard(
                ts_data,
                save_path=str(dashboard_path)
            )
            plots_saved.append(str(dashboard_path))

            logger.info(f"Plots saved: {len(plots_saved)} files")

        return {
            'analysis_type': 'time_series',
            'country': country_name,
            'start_year': start_year,
            'end_year': end_year,
            'interval': interval,
            'summary': ts_data,
            'plots_saved': plots_saved,
            'output_dir': str(output_dir)
        }

    else:
        logger.error(f"Invalid analysis_type: {analysis_type}. Must be 'snapshot' or 'time_series'")
        return None


# ============================================================================
# Countries File Batch Processing
# ============================================================================

def analyze_from_countries_file(
    csv_path: str,
    analysis_type: str = 'snapshot',
    output_dir: str = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Batch process countries from CSV or JSON file.

    Args:
        csv_path: Path to countries CSV/JSON file
        analysis_type: 'snapshot' or 'time_series'
        output_dir: Base output directory
        **kwargs: Additional arguments passed to analyze_country()

    Returns:
        Dict mapping country names to results

    Example:
        >>> results = analyze_from_countries_file(
        ...     "countries_polygons/middle_east.csv",
        ...     analysis_type='time_series',
        ...     start_year=2015,
        ...     end_year=2025
        ... )
    """
    logger.info(f"Loading countries from file: {csv_path}")

    # Load countries
    countries = load_countries_from_file(csv_path)
    if countries is None:
        logger.error("Failed to load countries file")
        return None

    # Extract dataset name from filename
    dataset_name = Path(csv_path).stem

    # Setup output directory
    if output_dir is None:
        output_dir = f"./results/{dataset_name}"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Processing {len(countries)} countries from '{dataset_name}'")

    results = {}
    all_summaries = []

    for i, country_data in enumerate(countries):
        country_name = country_data['name']
        bbox = country_data['bbox']

        logger.info(f"\n[{i+1}/{len(countries)}] Processing: {country_name}")
        logger.info("=" * 80)

        # Create country-specific output directory
        country_dir = output_dir / country_name.lower().replace(' ', '_')
        country_dir.mkdir(parents=True, exist_ok=True)

        # Determine area and chunking
        area_km2 = bbox_area_km2(bbox)
        use_chunked = area_km2 > kwargs.get('use_chunked_threshold_km2', 5000)

        try:
            if analysis_type == 'snapshot':
                timestamp = kwargs.get('timestamp', '2025-08-01')

                if use_chunked:
                    summary = get_poly_coords_chunked(
                        region_name=country_name,
                        bounds=bbox,
                        filter=kwargs.get('filter', "type:way and building=*"),
                        time_param=timestamp,
                        path=str(country_dir / 'data'),
                        filename=f"{country_name.lower()}_buildings.csv",
                        chunk_size_km=kwargs.get('chunk_size_km', 50),
                        resume=True,
                        cleanup_after=True
                    )
                else:
                    summary = get_poly_coords(
                        region_name=country_name,
                        bounds=bbox,
                        filter=kwargs.get('filter', "type:way and building=*"),
                        time_param=timestamp,
                        path=str(country_dir / 'data'),
                        filename=f"{country_name.lower()}_buildings.csv"
                    )

                if summary is not None:
                    summary['country'] = country_name
                    all_summaries.append(summary)
                    results[country_name] = {'summary': summary, 'output_dir': str(country_dir)}
                    logger.info(f"✓ {country_name} completed")
                else:
                    logger.warning(f"✗ {country_name} returned no data")

            elif analysis_type == 'time_series':
                ts_data = analyze_region_time_series(
                    region_name=country_name,
                    bbox=bbox,
                    start_year=kwargs.get('start_year', 2015),
                    end_year=kwargs.get('end_year', 2025),
                    interval=kwargs.get('interval', 'yearly'),
                    filter=kwargs.get('filter', "type:way and building=*"),
                    path=str(country_dir / 'data' / 'time_series'),
                    base_filename=f"{country_name.lower()}_ts",
                    use_chunked_threshold_km2=5000,
                    resume=True
                )

                if ts_data is not None:
                    ts_data['country'] = country_name
                    all_summaries.append(ts_data)
                    results[country_name] = {'summary': ts_data, 'output_dir': str(country_dir)}
                    logger.info(f"✓ {country_name} completed: {len(ts_data)} time points")
                else:
                    logger.warning(f"✗ {country_name} returned no data")

        except Exception as e:
            logger.error(f"✗ {country_name} failed: {str(e)}")
            continue

    # Save comparison summary
    if all_summaries:
        comparison_file = output_dir / f"{dataset_name}_comparison.csv"
        combined_df = pd.concat(all_summaries, ignore_index=True)
        combined_df.to_csv(comparison_file, index=False)
        logger.info(f"\n✓ Comparison saved: {comparison_file}")

    logger.info(f"\n✓ Batch processing complete: {len(results)}/{len(countries)} countries")

    return {
        'dataset_name': dataset_name,
        'results': results,
        'comparison_file': str(comparison_file) if all_summaries else None,
        'output_dir': str(output_dir)
    }


# ============================================================================
# City Comparison
# ============================================================================

def analyze_city_comparison(
    cities: List[str],
    radius_km: float = 15,
    timestamp: str = None,
    output_dir: str = None,
    filter: str = "type:way and building=*",
    generate_plots: bool = True
) -> pd.DataFrame:
    """
    Compare building complexity across multiple cities.

    Args:
        cities: List of city names (e.g., ["Jerusalem", "London", "Berlin"])
        radius_km: Radius around city center
        timestamp: ISO date for analysis
        output_dir: Output directory
        filter: OSM filter query
        generate_plots: Create comparison visualizations

    Returns:
        DataFrame with comparison metrics

    Example:
        >>> comparison = analyze_city_comparison(
        ...     ["Jerusalem", "London", "Paris"],
        ...     radius_km=20
        ... )
    """
    if timestamp is None:
        timestamp = "2025-08-01"

    if output_dir is None:
        output_dir = "results/archive/city_comparison"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Comparing {len(cities)} cities with radius {radius_km} km")

    summaries = []

    for city in cities:
        logger.info(f"\nAnalyzing city: {city}")

        bbox = get_bbox_by_city(city, radius_km=radius_km)
        if bbox is None:
            logger.warning(f"Could not geocode city: {city}")
            continue

        summary = get_poly_coords(
            region_name=city,
            bounds=bbox,
            filter=filter,
            time_param=timestamp,
            path=str(output_dir / 'data'),
            filename=f"{city.lower().replace(' ', '_')}_buildings.csv"
        )

        if summary is not None:
            summary['city'] = city
            summaries.append(summary)
            logger.info(f"✓ {city} completed")

    if not summaries:
        logger.error("No cities successfully analyzed")
        return None

    # Combine results
    comparison_df = pd.concat(summaries, ignore_index=True)

    # Save comparison
    comparison_file = output_dir / "cities_comparison.csv"
    comparison_df.to_csv(comparison_file, index=False)
    logger.info(f"\nComparison saved: {comparison_file}")

    # Generate plots
    if generate_plots:
        plot_path = output_dir / "cities_comparison_dashboard.png"
        plot_summary_dashboard(
            summaries,
            save_path=str(plot_path)
        )
        logger.info(f"Dashboard saved: {plot_path}")

    return comparison_df


# ============================================================================
# Custom Region Analysis
# ============================================================================

def analyze_custom_region(
    region_name: str,
    bbox: str = None,
    lat: float = None,
    lon: float = None,
    radius_km: float = 15,
    analysis_type: str = 'snapshot',
    **kwargs
) -> Dict[str, Any]:
    """
    Analyze custom region defined by bbox or center point.

    Args:
        region_name: Name for the region
        bbox: Bounding box string (if provided, lat/lon ignored)
        lat: Latitude of center point
        lon: Longitude of center point
        radius_km: Radius around center point
        analysis_type: 'snapshot' or 'time_series'
        **kwargs: Additional arguments passed to analysis functions

    Returns:
        Dict with analysis results

    Example:
        >>> # Analyze by coordinates
        >>> results = analyze_custom_region(
        ...     "my_region",
        ...     lat=31.7683,
        ...     lon=35.2137,
        ...     radius_km=25
        ... )
    """
    logger.info(f"Analyzing custom region: {region_name}")

    # Get or generate bounding box
    if bbox is None:
        if lat is None or lon is None:
            logger.error("Must provide either bbox or (lat, lon)")
            return None
        bbox = bbox_by_location(lat, lon, radius_km)

    logger.info(f"Bounding box: {bbox}")

    # Create output directory
    output_dir = kwargs.get('output_dir', f"./results/custom/{region_name}")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine area and chunking
    area_km2 = bbox_area_km2(bbox)
    use_chunked = area_km2 > kwargs.get('use_chunked_threshold_km2', 5000)

    if analysis_type == 'snapshot':
        timestamp = kwargs.get('timestamp', '2025-08-01')

        if use_chunked:
            summary = get_poly_coords_chunked(
                region_name=region_name,
                bounds=bbox,
                filter=kwargs.get('filter', "type:way and building=*"),
                time_param=timestamp,
                path=str(output_dir / 'data'),
                filename=f"{region_name}_buildings.csv",
                resume=True
            )
        else:
            summary = get_poly_coords(
                region_name=region_name,
                bounds=bbox,
                filter=kwargs.get('filter', "type:way and building=*"),
                time_param=timestamp,
                path=str(output_dir / 'data'),
                filename=f"{region_name}_buildings.csv"
            )

        return {
            'region_name': region_name,
            'bbox': bbox,
            'summary': summary,
            'output_dir': str(output_dir)
        }

    elif analysis_type == 'time_series':
        ts_data = analyze_region_time_series(
            region_name=region_name,
            bbox=bbox,
            start_year=kwargs.get('start_year', 2015),
            end_year=kwargs.get('end_year', 2025),
            interval=kwargs.get('interval', 'yearly'),
            filter=kwargs.get('filter', "type:way and building=*"),
            path=str(output_dir / 'data' / 'time_series'),
            base_filename=f"{region_name}_ts",
            resume=True
        )

        return {
            'region_name': region_name,
            'bbox': bbox,
            'summary': ts_data,
            'output_dir': str(output_dir)
        }


# ============================================================================
# Multiple Countries Analysis
# ============================================================================

def analyze_multiple_countries(
    countries: List[str],
    analysis_type: str = 'snapshot',
    output_dir: str = None,
    **kwargs
) -> Dict[str, pd.DataFrame]:
    """
    Analyze multiple countries with same settings.

    Args:
        countries: List of country names
        analysis_type: 'snapshot' or 'time_series'
        output_dir: Base output directory
        **kwargs: Additional arguments passed to analyze_country()

    Returns:
        Dict mapping country names to results

    Example:
        >>> results = analyze_multiple_countries(
        ...     ["Israel", "Palestine", "Jordan"],
        ...     start_year=2018,
        ...     end_year=2025
        ... )
    """
    if output_dir is None:
        output_dir = "./results/multi_country"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Analyzing {len(countries)} countries")

    results = {}

    for i, country in enumerate(countries):
        logger.info(f"\n[{i+1}/{len(countries)}] Processing: {country}")
        logger.info("=" * 80)

        country_dir = output_dir / country.lower().replace(' ', '_')

        try:
            result = analyze_country(
                country_name=country,
                analysis_type=analysis_type,
                output_dir=str(country_dir),
                **kwargs
            )

            if result:
                results[country] = result
                logger.info(f"✓ {country} completed")
            else:
                logger.warning(f"✗ {country} failed")

        except Exception as e:
            logger.error(f"✗ {country} error: {str(e)}")
            continue

    logger.info(f"\n✓ Multi-country analysis complete: {len(results)}/{len(countries)} countries")

    return results
