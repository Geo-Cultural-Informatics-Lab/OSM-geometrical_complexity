"""
Batch Country Analysis for OSM Geometrical Complexity

This module provides functions to analyze multiple countries from a CSV list,
extracting bounding boxes from GeoJSON and processing them sequentially or in parallel.
"""

import os
import pandas as pd
import geopandas as gpd
from pathlib import Path
import time
from api_helpers import logger, setup_logging
from geometry_analysis import get_poly_coords_chunked, get_poly_coords
from bbox_utils import get_bbox_by_city
from chunking_utils import bbox_area_km2


# ISO 3166-1 alpha-3 to alpha-2 mapping for common countries
ISO3_TO_ISO2 = {
    'DEU': 'DE',  # Germany
    'GBR': 'GB',  # United Kingdom
    'FRA': 'FR',  # France
    'NLD': 'NL',  # Netherlands
    'BEL': 'BE',  # Belgium
    'USA': 'US',  # United States
    'CAN': 'CA',  # Canada
    'MEX': 'MX',  # Mexico
    'ESP': 'ES',  # Spain
    'ITA': 'IT',  # Italy
    'POL': 'PL',  # Poland
    'SWE': 'SE',  # Sweden
    'NOR': 'NO',  # Norway
    'DNK': 'DK',  # Denmark
    'FIN': 'FI',  # Finland
    'CHE': 'CH',  # Switzerland
    'AUT': 'AT',  # Austria
    'CZE': 'CZ',  # Czech Republic
    'PRT': 'PT',  # Portugal
    'GRC': 'GR',  # Greece
    'JPN': 'JP',  # Japan
    'CHN': 'CN',  # China
    'IND': 'IN',  # India
    'AUS': 'AU',  # Australia
    'NZL': 'NZ',  # New Zealand
    'BRA': 'BR',  # Brazil
    'ARG': 'AR',  # Argentina
    'ZAF': 'ZA',  # South Africa
    'RUS': 'RU',  # Russia
    'TUR': 'TR',  # Turkey
}


def convert_iso3_to_iso2(iso3_code):
    """
    Convert ISO 3166-1 alpha-3 (3-letter) code to alpha-2 (2-letter) code.

    Args:
        iso3_code: 3-letter ISO code (e.g., 'DEU', 'GBR')

    Returns:
        2-letter ISO code (e.g., 'DE', 'GB'), or original code if not found
    """
    return ISO3_TO_ISO2.get(iso3_code.upper(), iso3_code)


def load_countries_from_csv(csv_path, iso_filter=None):
    """
    Load countries from World_Countries.csv file.

    Args:
        csv_path: Path to World_Countries.csv
        iso_filter: Optional list of ISO codes to filter (e.g., ['USA', 'DEU', 'GBR'])

    Returns:
        DataFrame with country names and ISO codes
    """
    logger.info(f"Loading countries from {csv_path}")

    try:
        df = pd.read_csv(csv_path)

        # Standardize column names (handle different formats)
        column_mapping = {
            'Two-character ISO Code for the Country': 'iso_code',
            'Country Name': 'country_name',
            'ISO': 'iso_code',
            'COUNTRY': 'country_name'
        }

        for old_col, new_col in column_mapping.items():
            if old_col in df.columns:
                df.rename(columns={old_col: new_col}, inplace=True)

        # Filter by ISO codes if provided
        if iso_filter:
            df = df[df['iso_code'].isin(iso_filter)]
            logger.info(f"Filtered to {len(df)} countries: {', '.join(iso_filter)}")
        else:
            logger.info(f"Loaded {len(df)} countries")

        return df[['country_name', 'iso_code']]

    except FileNotFoundError:
        logger.error(f"Country CSV file not found: {csv_path}")
        return None
    except Exception as e:
        logger.error(f"Error loading countries from CSV: {str(e)}")
        return None


def get_country_bbox_from_geojson(geojson_path, country_name=None, iso_code=None):
    """
    Extract bounding box for a country from GeoJSON file.

    Args:
        geojson_path: Path to World_Countries.geojson
        country_name: Country name to search for
        iso_code: ISO code to search for (takes precedence over name)
                  Accepts both ISO 3166-1 alpha-2 (2-letter) and alpha-3 (3-letter) codes

    Returns:
        Bounding box string "min_lon,min_lat,max_lon,max_lat" or None
    """
    try:
        gdf = gpd.read_file(geojson_path)

        # Search by ISO code (preferred) or country name
        if iso_code:
            # Convert ISO3 to ISO2 if needed (GeoJSON uses 2-letter codes)
            iso2_code = convert_iso3_to_iso2(iso_code)
            country_data = gdf[gdf['ISO'] == iso2_code]

            # If not found with converted code, try original code
            if country_data.empty and iso2_code != iso_code:
                country_data = gdf[gdf['ISO'] == iso_code]

        elif country_name:
            country_data = gdf[gdf['COUNTRY'] == country_name]
        else:
            logger.error("Must provide either country_name or iso_code")
            return None

        if country_data.empty:
            logger.warning(f"Country not found in GeoJSON: {country_name or iso_code}")
            return None

        # Get bounds from geometry
        bounds = country_data.total_bounds  # [minx, miny, maxx, maxy]
        bbox = f"{bounds[0]},{bounds[1]},{bounds[2]},{bounds[3]}"

        area_km2 = bbox_area_km2(bbox)
        logger.info(f"Found bbox for {country_name or iso_code}: {area_km2:.0f} km²")

        return bbox

    except FileNotFoundError:
        logger.warning(f"GeoJSON file not found: {geojson_path}")
        return None
    except Exception as e:
        logger.warning(f"Error reading GeoJSON: {str(e)}")
        return None


def get_country_bbox_with_fallback(country_name, iso_code, geojson_path=None):
    """
    Get country bounding box with fallback to Nominatim API.

    First tries to get bbox from GeoJSON file if provided.
    If that fails, uses Nominatim API to geocode the country.

    Args:
        country_name: Country name
        iso_code: ISO country code
        geojson_path: Optional path to GeoJSON file

    Returns:
        Bounding box string or None
    """
    # Try GeoJSON first if path provided
    if geojson_path:
        bbox = get_country_bbox_from_geojson(geojson_path, country_name=country_name, iso_code=iso_code)
        if bbox:
            return bbox
        logger.info(f"GeoJSON lookup failed for {iso_code}, trying Nominatim API...")

    # Fallback to Nominatim API
    from bbox_utils import get_bbox_by_city

    # Try with country name
    if country_name:
        logger.info(f"Using Nominatim API to geocode: {country_name}")
        bbox = get_bbox_by_city(country_name, radius_km=50)  # Use larger radius for countries
        if bbox:
            return bbox

    # Try with ISO code as fallback
    logger.info(f"Trying Nominatim with ISO code: {iso_code}")
    bbox = get_bbox_by_city(iso_code, radius_km=50)
    return bbox


def analyze_countries_batch(countries_df, geojson_path, output_dir,
                            start_year=None, end_year=None, interval='yearly',
                            filter="type:way and building=*",
                            chunked_threshold_km2=5000,
                            include_user_count=True,
                            resume=True):
    """
    Analyze multiple countries in batch mode.

    Args:
        countries_df: DataFrame with 'country_name' and 'iso_code' columns
        geojson_path: Path to World_Countries.geojson for extracting bboxes
        output_dir: Directory to save results
        start_year: Start year for time series (None for snapshot)
        end_year: End year for time series (None for snapshot)
        interval: Time interval for time series ('yearly', 'monthly', 'quarterly')
        filter: OSM filter query
        chunked_threshold_km2: Use chunked processing for areas above this size
        include_user_count: Whether to include user count analysis
        resume: Resume from previous incomplete run

    Returns:
        DataFrame with combined results for all countries
    """
    from time_series_analysis import analyze_region_time_series

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Setup logging
    log_file = output_path / "batch_country_analysis.log"
    logger_batch = setup_logging(log_file=str(log_file))

    logger_batch.info("=" * 80)
    logger_batch.info(f"BATCH COUNTRY ANALYSIS")
    logger_batch.info(f"Countries: {len(countries_df)}")
    logger_batch.info(f"Mode: {'Time Series' if start_year else 'Snapshot'}")
    if start_year:
        logger_batch.info(f"Period: {start_year}-{end_year}, Interval: {interval}")
    logger_batch.info("=" * 80)

    results = []
    failed_countries = []
    start_time = time.time()

    for idx, row in countries_df.iterrows():
        country_name = row['country_name']
        iso_code = row['iso_code']

        logger_batch.info(f"\n{'='*80}")
        logger_batch.info(f"[{idx+1}/{len(countries_df)}] Processing: {country_name} ({iso_code})")
        logger_batch.info(f"{'='*80}")

        # Get bounding box with fallback to Nominatim API
        bbox = get_country_bbox_with_fallback(country_name, iso_code, geojson_path)

        if bbox is None:
            logger_batch.warning(f"Skipping {country_name} - could not get bounding box")
            failed_countries.append(iso_code)
            continue

        area_km2 = bbox_area_km2(bbox)

        try:
            if start_year and end_year:
                # Time series analysis
                logger_batch.info(f"Running time series analysis ({start_year}-{end_year})")
                country_data = analyze_region_time_series(
                    region_name=iso_code.lower(),
                    bbox=bbox,
                    start_year=start_year,
                    end_year=end_year,
                    interval=interval,
                    filter=filter,
                    path=str(output_path / "time_series"),
                    base_filename=f"{iso_code.lower()}_buildings",
                    use_chunked_threshold_km2=chunked_threshold_km2,
                    resume=resume
                )
            else:
                # Snapshot analysis
                logger_batch.info(f"Running snapshot analysis")
                timestamp = "2025-08-01"  # Latest available

                if area_km2 > chunked_threshold_km2:
                    country_data = get_poly_coords_chunked(
                        region_name=iso_code.lower(),
                        bounds=bbox,
                        filter=filter,
                        time_param=timestamp,
                        path=str(output_path),
                        filename=f"{iso_code.lower()}_buildings.csv",
                        resume=resume,
                        cleanup_after=True
                    )
                else:
                    country_data = get_poly_coords(
                        region_name=iso_code.lower(),
                        bounds=bbox,
                        filter=filter,
                        time_param=timestamp,
                        path=str(output_path),
                        filename=f"{iso_code.lower()}_buildings.csv",
                        include_counts=True,
                        include_user_count=include_user_count
                    )

            if country_data is not None:
                # Add country metadata
                country_data['country_name'] = country_name
                country_data['iso_code'] = iso_code
                country_data['area_km2'] = area_km2
                results.append(country_data)
                logger_batch.info(f"✓ {country_name} completed successfully")
            else:
                logger_batch.warning(f"✗ {country_name} returned no data")
                failed_countries.append(iso_code)

        except Exception as e:
            logger_batch.error(f"✗ {country_name} failed: {str(e)}")
            failed_countries.append(iso_code)
            continue

    # Combine results
    if results:
        combined_df = pd.concat(results, ignore_index=True)

        # Save combined results
        output_file = output_path / "batch_countries_summary.csv"
        combined_df.to_csv(output_file, index=False)

        logger_batch.info(f"\n{'='*80}")
        logger_batch.info(f"BATCH ANALYSIS COMPLETE")
        logger_batch.info(f"Successful: {len(results)}/{len(countries_df)} countries")
        logger_batch.info(f"Failed: {len(failed_countries)} countries")
        if failed_countries:
            logger_batch.info(f"Failed ISOs: {', '.join(failed_countries)}")
        logger_batch.info(f"Total time: {(time.time() - start_time)/60:.1f} minutes")
        logger_batch.info(f"Results saved to: {output_file}")
        logger_batch.info(f"{'='*80}")

        return combined_df
    else:
        logger_batch.error("No countries were successfully processed")
        return None


def create_batch_config_example():
    """
    Create example YAML configuration for batch country analysis.

    Returns:
        Dictionary with example configuration
    """
    return {
        'analysis': {
            'mode': 'batch_countries',
        },
        'countries': {
            'source': 'csv',  # 'csv' or 'list'
            'csv_path': './World_Countries.csv',
            'geojson_path': './countries_polygons/World_Countries.geojson',
            'iso_filter': ['USA', 'DEU', 'GBR', 'FRA', 'ITA'],  # None for all
        },
        'time_series': {
            'enabled': False,
            'start_year': 2015,
            'end_year': 2025,
            'interval': 'yearly'
        },
        'analysis_options': {
            'filter': 'type:way and building=*',
            'chunked_threshold_km2': 5000,
            'include_user_count': True,
            'resume': True
        },
        'output': {
            'directory': './results/batch_countries',
            'export_shapefile': True
        }
    }
