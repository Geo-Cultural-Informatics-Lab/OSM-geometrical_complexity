"""
GIS Export Functions for OSM Geometrical Complexity Analysis

This module provides functions to export analysis results as shapefiles and GeoJSON
for use in GIS software like QGIS, ArcGIS, etc.
"""

import os
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape, Point
from pathlib import Path
from api_helpers import logger, call_ohsome_api
from geometry_analysis import calculate_convex_hull_metrics


def export_buildings_to_shapefile(region_name, bounds, filter="type:way and building=*",
                                   time_param="2025-08-01", output_dir="./results",
                                   include_metrics=True):
    """
    Export building polygons with complexity metrics to shapefile.

    Args:
        region_name: Name of the region
        bounds: Bounding box string
        filter: OSM filter query
        time_param: ISO-8601 timestamp
        output_dir: Directory to save shapefile
        include_metrics: Include complexity metrics in attributes

    Returns:
        Path to created shapefile or None on error
    """
    logger.info(f"Exporting buildings for {region_name} to shapefile...")

    try:
        # Get geometry data from API
        data = call_ohsome_api('geometry', bounds, filter, time_param, return_type='json')

        if not data or 'features' not in data:
            logger.error("No geometry data retrieved from API")
            return None

        features = data['features']
        logger.info(f"Retrieved {len(features)} buildings")

        # Convert to GeoDataFrame
        gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")

        # Add metrics if requested
        if include_metrics:
            logger.info("Calculating complexity metrics...")
            metrics_df = calculate_convex_hull_metrics(features, bounds, use_vectorized=True)

            if metrics_df is not None:
                # Merge metrics with geometries
                # Match on OSM ID
                gdf['osm_id'] = gdf['osmId']
                metrics_df['osm_id'] = metrics_df['way_id']

                gdf = gdf.merge(metrics_df[['osm_id', 'area_m2', 'convex_hull_m2', 'ratio',
                                            'is_multipolygon', 'inner_ring_count']],
                               on='osm_id', how='left')

        # Clean up column names for shapefile (max 10 chars)
        column_mapping = {
            'osmId': 'osm_id',
            'timestamp': 'timestamp',
            'area_m2': 'area_m2',
            'convex_hull_m2': 'chull_m2',
            'ratio': 'ratio',
            'is_multipolygon': 'is_multi',
            'inner_ring_count': 'inner_ring'
        }

        gdf = gdf.rename(columns=column_mapping)

        # Select only relevant columns
        cols_to_keep = ['osm_id', 'timestamp', 'geometry']
        if include_metrics:
            cols_to_keep.extend(['area_m2', 'chull_m2', 'ratio', 'is_multi', 'inner_ring'])

        gdf = gdf[[col for col in cols_to_keep if col in gdf.columns]]

        # Create output directory
        output_path = Path(output_dir) / "shapefiles"
        output_path.mkdir(parents=True, exist_ok=True)

        # Save as shapefile
        shp_path = output_path / f"{region_name}_buildings.shp"
        gdf.to_file(shp_path, driver='ESRI Shapefile')
        logger.info(f"Shapefile saved to {shp_path}")

        # Also save as GeoJSON for web compatibility
        geojson_path = output_path / f"{region_name}_buildings.geojson"
        gdf.to_file(geojson_path, driver='GeoJSON')
        logger.info(f"GeoJSON saved to {geojson_path}")

        return str(shp_path)

    except Exception as e:
        logger.error(f"Error exporting buildings to shapefile: {str(e)}")
        return None


def export_summary_to_shapefile(summary_df, geojson_path=None, output_dir="./results",
                                 output_name="country_summaries"):
    """
    Export country/region summary statistics as shapefile with boundary polygons.

    Args:
        summary_df: DataFrame with summary statistics (must have 'region' or 'iso_code' column)
        geojson_path: Path to GeoJSON with country boundaries (optional)
        output_dir: Directory to save shapefile
        output_name: Base name for output files

    Returns:
        Path to created shapefile or None on error
    """
    logger.info(f"Exporting summary data to shapefile...")

    try:
        # If GeoJSON path provided, merge with boundaries
        if geojson_path and os.path.exists(geojson_path):
            logger.info(f"Loading boundaries from {geojson_path}")
            boundaries = gpd.read_file(geojson_path)

            # Try to match on ISO code or country name
            if 'iso_code' in summary_df.columns and 'ISO' in boundaries.columns:
                merge_on = ('iso_code', 'ISO')
            elif 'country_name' in summary_df.columns and 'COUNTRY' in boundaries.columns:
                merge_on = ('country_name', 'COUNTRY')
            else:
                logger.warning("Could not find matching columns for merge, creating point geometries")
                geojson_path = None

            if geojson_path:
                # Merge summary with boundaries
                gdf = boundaries.merge(summary_df,
                                      left_on=merge_on[1],
                                      right_on=merge_on[0],
                                      how='inner')
                logger.info(f"Merged {len(gdf)} regions with boundaries")
        else:
            # Create point geometries from bounding box centers
            logger.info("Creating point geometries from bounding boxes")

            def bbox_center(bbox_str):
                """Extract center point from bbox string."""
                try:
                    coords = [float(x) for x in bbox_str.split(',')]
                    lon = (coords[0] + coords[2]) / 2
                    lat = (coords[1] + coords[3]) / 2
                    return Point(lon, lat)
                except:
                    return None

            if 'bbox' in summary_df.columns:
                summary_df['geometry'] = summary_df['bbox'].apply(bbox_center)
                gdf = gpd.GeoDataFrame(summary_df, crs="EPSG:4326")
            else:
                logger.error("No bbox column found and no GeoJSON provided")
                return None

        # Standardize column names for shapefile (10 char limit)
        column_mapping = {
            'region': 'region',
            'iso_code': 'iso',
            'country_name': 'country',
            'building_count': 'bldg_cnt',
            'user_count': 'user_cnt',
            'mean_ratio': 'mean_rat',
            'median_ratio': 'med_rat',
            'mean_area': 'mean_area',
            'multipolygon_ratio': 'multi_rat',
            'area_km2': 'area_km2'
        }

        gdf = gdf.rename(columns={k: v for k, v in column_mapping.items() if k in gdf.columns})

        # Create output directory
        output_path = Path(output_dir) / "shapefiles"
        output_path.mkdir(parents=True, exist_ok=True)

        # Save as shapefile
        shp_path = output_path / f"{output_name}.shp"
        gdf.to_file(shp_path, driver='ESRI Shapefile')
        logger.info(f"Summary shapefile saved to {shp_path}")

        # Also save as GeoJSON
        geojson_path = output_path / f"{output_name}.geojson"
        gdf.to_file(geojson_path, driver='GeoJSON')
        logger.info(f"Summary GeoJSON saved to {geojson_path}")

        return str(shp_path)

    except Exception as e:
        logger.error(f"Error exporting summary to shapefile: {str(e)}")
        return None


def create_analysis_package(region_name, summary_df, detailed_df=None,
                           geojson_path=None, output_dir="./results"):
    """
    Create a complete GIS package with both summary and detailed shapefiles.

    Args:
        region_name: Name of the region/analysis
        summary_df: Summary statistics DataFrame
        detailed_df: Optional detailed building DataFrame
        geojson_path: Optional path to boundary GeoJSON
        output_dir: Output directory

    Returns:
        Dictionary with paths to created files
    """
    logger.info(f"Creating GIS analysis package for {region_name}")

    output_files = {}

    # Export summary
    summary_path = export_summary_to_shapefile(
        summary_df,
        geojson_path=geojson_path,
        output_dir=output_dir,
        output_name=f"{region_name}_summary"
    )
    if summary_path:
        output_files['summary_shapefile'] = summary_path

    # Export detailed buildings if provided
    if detailed_df is not None and len(detailed_df) > 0:
        logger.info("Exporting detailed building data...")
        # This would require rebuilding geometries from the detailed_df
        # For now, we skip this as it requires the original GeoJSON features
        logger.warning("Detailed building export not yet implemented for pre-processed data")

    logger.info(f"GIS package complete: {len(output_files)} files created")
    return output_files
