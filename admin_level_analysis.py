"""
Administrative Level Analysis Module

This module extends the batch analysis functionality to automatically subdivide
countries into administrative regions (provinces, districts, etc.) and analyze
each subdivision separately while maintaining proper organization and chunking.
"""

import os
import pandas as pd
from pathlib import Path
import time
from api_helpers import logger, setup_logging
from admin_boundaries import get_admin_boundaries, get_country_iso_code, save_boundaries_to_csv
from geometry_analysis import get_poly_coords_chunked, get_poly_coords
from chunking_utils import bbox_area_km2
from batch_country_analysis import get_country_bbox_with_fallback


def create_admin_subdivision_visualizations(
    combined_df,
    boundaries,
    country_name,
    iso_code,
    admin_level,
    output_dir,
    top_n=10,
    create_dashboards=True,
    create_box_plots=True
):
    """
    Create visualizations for admin subdivision analysis.

    Args:
        combined_df: Combined DataFrame with all subdivision data
        boundaries: List of boundary dicts
        country_name: Country name
        iso_code: ISO code
        admin_level: Administrative level
        output_dir: Output directory path
        top_n: Number of top subdivisions to show in plots (default: 10)
        create_dashboards: Whether to create dashboards
        create_box_plots: Whether to create box plots

    Returns:
        Dict with paths to created visualizations
    """
    from visualization import (
        plot_summary_dashboard,
        plot_complexity_boxplots,
        plot_users_vs_complexity
    )
    import matplotlib.pyplot as plt

    logger.info(f"\n{'='*80}")
    logger.info(f"Creating visualizations (top {top_n} subdivisions)...")
    logger.info(f"{'='*80}")

    output_path = Path(output_dir)
    viz_paths = {}

    # Calculate subdivision-level statistics
    # Check if data is already aggregated (has building_count column) or raw
    if 'building_count' in combined_df.columns:
        # Data is already aggregated at subdivision level
        subdivision_stats = combined_df[['subdivision_name', 'building_count', 'mean_ratio', 'area_km2']].copy()
        subdivision_stats.columns = ['subdivision_name', 'building_count', 'avg_complexity', 'area_km2']
    else:
        # Raw building data - aggregate it
        # Check which columns are available
        if 'way_id' in combined_df.columns:
            count_col = 'way_id'
        elif '@osmId' in combined_df.columns:
            count_col = '@osmId'
        else:
            count_col = combined_df.columns[0]

        # Use ratio as complexity metric if nodes not available
        if 'nodes' in combined_df.columns:
            complexity_col = 'nodes'
        elif 'ratio' in combined_df.columns:
            complexity_col = 'ratio'
        else:
            complexity_col = None

        agg_dict = {count_col: 'count', 'area_km2': 'first'}
        if complexity_col:
            agg_dict[complexity_col] = 'mean'

        subdivision_stats = combined_df.groupby('subdivision_name').agg(agg_dict).reset_index()

        # Rename columns
        col_mapping = {'subdivision_name': 'subdivision_name', count_col: 'building_count', 'area_km2': 'area_km2'}
        if complexity_col:
            col_mapping[complexity_col] = 'avg_complexity'
        subdivision_stats.rename(columns=col_mapping, inplace=True)

    subdivision_stats = subdivision_stats.sort_values('building_count', ascending=False)

    # Get top N subdivisions
    top_subdivisions = subdivision_stats.head(top_n)['subdivision_name'].tolist()
    logger.info(f"Top {top_n} subdivisions by building count:")
    for i, name in enumerate(top_subdivisions, 1):
        stats = subdivision_stats[subdivision_stats['subdivision_name'] == name].iloc[0]
        if 'avg_complexity' in stats.index:
            logger.info(f"  {i}. {name}: {int(stats['building_count']):,} buildings, "
                       f"avg complexity: {stats['avg_complexity']:.2f}")
        else:
            logger.info(f"  {i}. {name}: {int(stats['building_count']):,} buildings")

    # Filter to top N for visualization
    top_df = combined_df[combined_df['subdivision_name'].isin(top_subdivisions)].copy()

    try:
        # Check if we have raw building data or aggregated data
        is_aggregated = 'building_count' in combined_df.columns

        if not is_aggregated:
            # 1. Summary dashboard for top N (only for raw data)
            # Note: Dashboard function expects country-level summary format, not building-level data
            # Skipping dashboard for admin subdivision data
            if False and create_dashboards:  # Disabled - incompatible with building-level data
                logger.info(f"Creating summary dashboard for top {top_n} subdivisions...")
                dashboard_path = output_path / f"{iso_code.lower()}_admin_{admin_level}_top{top_n}_dashboard.png"

                plot_summary_dashboard(
                    [top_df],
                    save_path=str(dashboard_path)
                )
                viz_paths['dashboard'] = str(dashboard_path)
                logger.info(f"  Saved: {dashboard_path.name}")

            # 2. Box plots comparing subdivisions (only for raw data)
            if create_box_plots:
                logger.info(f"Creating complexity comparison box plots...")

                # Use ratio or nodes for complexity metric
                complexity_metric = 'ratio' if 'ratio' in top_df.columns else 'nodes'

                # Prepare data for box plot
                plot_data = []
                plot_labels = []
                for name in top_subdivisions:
                    subdivision_data = top_df[top_df['subdivision_name'] == name][complexity_metric].dropna()
                    if len(subdivision_data) > 0:
                        plot_data.append(subdivision_data.values)
                        # Shorten names if too long
                        label = name if len(name) <= 20 else name[:17] + '...'
                        plot_labels.append(label)

                # Create two versions: full range and focused on 95th percentile
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 14))

                # Version 1: Full range with outliers
                bp1 = ax1.boxplot(plot_data, labels=plot_labels, patch_artist=True, showfliers=True)
                for patch in bp1['boxes']:
                    patch.set_facecolor('#3498db')
                    patch.set_alpha(0.7)

                ax1.set_xlabel('Subdivision', fontsize=12)
                ylabel = 'Building Complexity (Perimeter²/Area Ratio)' if complexity_metric == 'ratio' else 'Building Complexity (nodes)'
                ax1.set_ylabel(ylabel, fontsize=12)
                ax1.set_title(f'{country_name} - Building Complexity by Subdivision (Full Range)\n(Top {top_n} by Building Count)',
                            fontsize=14, fontweight='bold')
                ax1.grid(axis='y', alpha=0.3)
                ax1.tick_params(axis='x', rotation=45)
                plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

                # Version 2: Focused view - zoom to 95th percentile
                bp2 = ax2.boxplot(plot_data, labels=plot_labels, patch_artist=True, showfliers=False)
                for patch in bp2['boxes']:
                    patch.set_facecolor('#e74c3c')
                    patch.set_alpha(0.7)

                # Calculate 95th percentile across all subdivisions for zoom
                all_values = []
                for data in plot_data:
                    all_values.extend(data)
                p95 = pd.Series(all_values).quantile(0.95)

                ax2.set_ylim(-0.002, p95 * 1.1)  # Zoom to 95th percentile with 10% margin
                ax2.set_xlabel('Subdivision', fontsize=12)
                ax2.set_ylabel(ylabel, fontsize=12)
                ax2.set_title(f'{country_name} - Building Complexity by Subdivision (Zoomed to 95th Percentile)\n(Top {top_n} by Building Count)',
                            fontsize=14, fontweight='bold')
                ax2.grid(axis='y', alpha=0.3)
                ax2.tick_params(axis='x', rotation=45)
                plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

                plt.tight_layout()
                boxplot_path = output_path / f"{iso_code.lower()}_admin_{admin_level}_top{top_n}_boxplot.png"
                plt.savefig(boxplot_path, dpi=300, bbox_inches='tight')
                plt.close()

                viz_paths['boxplot'] = str(boxplot_path)
                logger.info(f"  Saved: {boxplot_path.name}")

            # 3. Histogram of complexity distributions (only for raw data)
            logger.info(f"Creating complexity distribution histograms...")
            hist_path = output_path / f"{iso_code.lower()}_admin_{admin_level}_top{top_n}_histogram.png"

            # Create histogram grid
            n_subdivisions = len(top_subdivisions)
            n_cols = 2
            n_rows = (n_subdivisions + 1) // 2

            fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, 4 * n_rows))
            axes = axes.flatten() if n_subdivisions > 1 else [axes]

            for idx, name in enumerate(top_subdivisions):
                ax = axes[idx]
                subdivision_data = top_df[top_df['subdivision_name'] == name][complexity_metric].dropna()

                if len(subdivision_data) > 0:
                    # Plot histogram with logarithmic bins for better visualization
                    # Filter out zeros for better visualization
                    non_zero_data = subdivision_data[subdivision_data > 0]

                    ax.hist(subdivision_data, bins=50, color='#3498db', alpha=0.7, edgecolor='black')

                    # Add mean and median lines
                    mean_val = subdivision_data.mean()
                    median_val = subdivision_data.median()

                    ax.axvline(mean_val, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_val:.4f}')
                    ax.axvline(median_val, color='orange', linestyle='--', linewidth=2, label=f'Median: {median_val:.4f}')

                    # Shorten name if too long
                    display_name = name if len(name) <= 30 else name[:27] + '...'
                    ax.set_title(display_name, fontsize=11, fontweight='bold')
                    ax.set_xlabel('Complexity (Ratio)', fontsize=9)
                    ax.set_ylabel('Frequency', fontsize=9)
                    ax.grid(axis='y', alpha=0.3)

                    # Add legend in upper center to avoid overlap with stats box
                    ax.legend(fontsize=8, loc='upper center', ncol=2, framealpha=0.9)

                    # Add text box with statistics in upper right, lower position to avoid legend
                    stats_text = f'n={len(subdivision_data):,}\n95th %ile: {subdivision_data.quantile(0.95):.4f}'
                    ax.text(0.98, 0.70, stats_text, transform=ax.transAxes,
                           verticalalignment='top', horizontalalignment='right',
                           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                           fontsize=8)

            # Hide any unused subplots
            for idx in range(len(top_subdivisions), len(axes)):
                axes[idx].axis('off')

            plt.suptitle(f'{country_name} - Building Complexity Distribution by Subdivision\n(Top {top_n} by Building Count)',
                        fontsize=14, fontweight='bold', y=0.995)
            plt.tight_layout()
            plt.savefig(hist_path, dpi=300, bbox_inches='tight')
            plt.close()

            viz_paths['histogram'] = str(hist_path)
            logger.info(f"  Saved: {hist_path.name}")

            # 4. User correlation plot (only for raw data)
            if 'user_count' in top_df.columns:
                logger.info(f"Creating user vs complexity correlation plot...")
                corr_path = output_path / f"{iso_code.lower()}_admin_{admin_level}_top{top_n}_user_correlation.png"

                plot_users_vs_complexity(
                    top_df,
                    save_path=str(corr_path),
                    title=f"{country_name} - Top {top_n} Subdivisions"
                )
                viz_paths['user_correlation'] = str(corr_path)
                logger.info(f"  Saved: {corr_path.name}")

        # 4. Create summary statistics bar chart
        logger.info(f"Creating subdivision statistics bar chart...")
        stats_path = output_path / f"{iso_code.lower()}_admin_{admin_level}_top{top_n}_stats.png"

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

        # Building counts
        top_stats = subdivision_stats.head(top_n)
        bars1 = ax1.bar(range(len(top_stats)), top_stats['building_count'], color='#2ecc71', alpha=0.7)
        ax1.set_xlabel('Subdivision Rank', fontsize=12)
        ax1.set_ylabel('Number of Buildings', fontsize=12)
        ax1.set_title(f'{country_name} - Building Counts by Subdivision (Top {top_n})',
                     fontsize=14, fontweight='bold')
        ax1.set_xticks(range(len(top_stats)))
        ax1.set_xticklabels([f"#{i+1}" for i in range(len(top_stats))])
        ax1.grid(axis='y', alpha=0.3)

        # Add subdivision names as labels
        for i, (idx, row) in enumerate(top_stats.iterrows()):
            name = row['subdivision_name'] if len(row['subdivision_name']) <= 25 else row['subdivision_name'][:22] + '...'
            ax1.text(i, row['building_count'], f"\n{name}",
                    ha='center', va='bottom', fontsize=8, rotation=0)

        # Average complexity (if available)
        if 'avg_complexity' in top_stats.columns:
            bars2 = ax2.bar(range(len(top_stats)), top_stats['avg_complexity'], color='#e74c3c', alpha=0.7)
            ax2.set_xlabel('Subdivision Rank', fontsize=12)
            # Determine label based on whether we have ratio or nodes
            complexity_label = 'Average Building Complexity (Ratio)' if not is_aggregated and 'ratio' in combined_df.columns else 'Average Building Complexity (nodes)'
            ax2.set_ylabel(complexity_label, fontsize=12)
            ax2.set_title(f'{country_name} - Average Complexity by Subdivision (Top {top_n})',
                         fontsize=14, fontweight='bold')
            ax2.set_xticks(range(len(top_stats)))
            ax2.set_xticklabels([f"#{i+1}" for i in range(len(top_stats))])
            ax2.grid(axis='y', alpha=0.3)
        else:
            # No complexity data - hide second subplot
            ax2.axis('off')

        plt.tight_layout()
        plt.savefig(stats_path, dpi=300, bbox_inches='tight')
        plt.close()

        viz_paths['stats_chart'] = str(stats_path)
        logger.info(f"  Saved: {stats_path.name}")

        # 5. User correlation scatter plot (subdivision level)
        # Check if we have user_count data in the summary stats
        if 'user_count' in subdivision_stats.columns or 'user_count' in combined_df.columns or 'subdivision_user_count' in combined_df.columns:
            logger.info(f"Creating user correlation scatter plot...")

            # Get user counts from the original combined_df if it has them
            if 'user_count' in combined_df.columns and is_aggregated:
                # Use aggregated data directly
                user_data = subdivision_stats.copy()
                if 'user_count' not in user_data.columns:
                    # Merge from combined_df
                    user_data = user_data.merge(
                        combined_df[['subdivision_name', 'user_count']],
                        on='subdivision_name',
                        how='left'
                    )
            elif 'subdivision_user_count' in combined_df.columns:
                # Raw data with subdivision-level user counts
                logger.info(f"Found subdivision_user_count in raw data, creating user correlation...")
                user_by_subdivision = combined_df.groupby('subdivision_name')['subdivision_user_count'].first().reset_index()
                user_by_subdivision.columns = ['subdivision_name', 'user_count']
                user_data = subdivision_stats.merge(user_by_subdivision, on='subdivision_name', how='left')
            else:
                user_data = None

            if user_data is not None and 'user_count' in user_data.columns:
                user_corr_path = output_path / f"{iso_code.lower()}_admin_{admin_level}_top{top_n}_user_correlation.png"

                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

                # Filter to top N
                top_user_data = user_data.head(top_n)

                # Plot 1: User count vs Building count
                ax1.scatter(top_user_data['user_count'], top_user_data['building_count'],
                           s=100, alpha=0.6, c='#3498db')
                ax1.set_xlabel('Number of Contributors', fontsize=12)
                ax1.set_ylabel('Number of Buildings', fontsize=12)
                ax1.set_title(f'{country_name} - Contributors vs Buildings\n(Top {top_n} Subdivisions)',
                             fontsize=14, fontweight='bold')
                ax1.grid(True, alpha=0.3)

                # Add labels for each point
                for _, row in top_user_data.iterrows():
                    label = row['subdivision_name'][:15] + '...' if len(row['subdivision_name']) > 15 else row['subdivision_name']
                    ax1.annotate(label, (row['user_count'], row['building_count']),
                               fontsize=8, alpha=0.7, xytext=(5, 5), textcoords='offset points')

                # Plot 2: User count vs Avg complexity (if available)
                if 'avg_complexity' in top_user_data.columns:
                    ax2.scatter(top_user_data['user_count'], top_user_data['avg_complexity'],
                               s=100, alpha=0.6, c='#e74c3c')
                    ax2.set_xlabel('Number of Contributors', fontsize=12)
                    complexity_label = 'Average Complexity (Ratio)' if not is_aggregated and 'ratio' in combined_df.columns else 'Average Complexity (nodes)'
                    ax2.set_ylabel(complexity_label, fontsize=12)
                    ax2.set_title(f'{country_name} - Contributors vs Complexity\n(Top {top_n} Subdivisions)',
                                 fontsize=14, fontweight='bold')
                    ax2.grid(True, alpha=0.3)

                    # Add labels
                    for _, row in top_user_data.iterrows():
                        label = row['subdivision_name'][:15] + '...' if len(row['subdivision_name']) > 15 else row['subdivision_name']
                        ax2.annotate(label, (row['user_count'], row['avg_complexity']),
                                   fontsize=8, alpha=0.7, xytext=(5, 5), textcoords='offset points')
                else:
                    ax2.axis('off')

                plt.tight_layout()
                plt.savefig(user_corr_path, dpi=300, bbox_inches='tight')
                plt.close()

                viz_paths['user_correlation'] = str(user_corr_path)
                logger.info(f"  Saved: {user_corr_path.name}")

        logger.info(f"\nVisualization complete! Created {len(viz_paths)} plots")
        return viz_paths

    except Exception as e:
        logger.error(f"Error creating visualizations: {e}", exc_info=True)
        return viz_paths


def analyze_country_by_admin_level(
    country_name,
    iso_code,
    admin_level=6,
    output_dir="./results",
    start_year=None,
    end_year=None,
    interval='yearly',
    filter="type:way and building=*",
    chunked_threshold_km2=5000,
    include_user_count=True,
    resume=True,
    cache_boundaries=True,
    overpass_timeout=120,
    geojson_path=None,
    create_visualizations=False,
    viz_top_n=10
):
    """
    Analyze a country subdivided by administrative level.

    This function:
    1. Queries Overpass API for all admin subdivisions in the country
    2. Analyzes each subdivision separately
    3. Uses chunking within each subdivision if needed
    4. Organizes results hierarchically: country/subdivision/chunks
    5. Aggregates results for the full country

    Args:
        country_name: Country name (e.g., "Thailand")
        iso_code: ISO 3166-1 alpha-2 code (e.g., "TH")
        admin_level: Administrative level (4=province, 6=district, 8=sub-district)
        output_dir: Base output directory
        start_year: Start year for time series (None for snapshot)
        end_year: End year for time series (None for snapshot)
        interval: Time interval ('yearly', 'monthly', 'quarterly')
        filter: OSM filter query
        chunked_threshold_km2: Area threshold for chunking within subdivisions
        include_user_count: Whether to include user count analysis
        resume: Resume interrupted analyses
        cache_boundaries: Cache boundary data from Overpass API
        overpass_timeout: Timeout for Overpass API queries
        geojson_path: Optional GeoJSON for country bbox fallback

    Returns:
        Dict with analysis results and metadata
    """
    # Setup output directory structure
    country_output = Path(output_dir) / iso_code.lower()
    country_output.mkdir(parents=True, exist_ok=True)

    # Setup logging
    log_file = country_output / f"{iso_code.lower()}_admin_level_{admin_level}_analysis.log"
    logger_admin = setup_logging(log_file=str(log_file))

    logger_admin.info("=" * 80)
    logger_admin.info(f"ADMINISTRATIVE LEVEL ANALYSIS")
    logger_admin.info(f"Country: {country_name} ({iso_code})")
    logger_admin.info(f"Admin Level: {admin_level}")
    logger_admin.info(f"Mode: {'Time Series' if start_year else 'Snapshot'}")
    if start_year:
        logger_admin.info(f"Period: {start_year}-{end_year}, Interval: {interval}")
    logger_admin.info("=" * 80)

    start_time = time.time()

    # Step 1: Get administrative boundaries
    logger_admin.info(f"\nStep 1: Querying administrative boundaries...")

    cache_file = None
    if cache_boundaries:
        cache_file = country_output / f".cache_admin_level_{admin_level}.json"

    boundaries = get_admin_boundaries(
        country_iso=iso_code,
        country_name=country_name,
        admin_level=admin_level,
        timeout=overpass_timeout,
        cache_file=str(cache_file) if cache_file else None
    )

    if not boundaries:
        logger_admin.error(f"Failed to get administrative boundaries for {country_name}")
        return None

    logger_admin.info(f"Found {len(boundaries)} administrative subdivisions")

    # Save boundaries to CSV for reference
    boundaries_csv = country_output / f"{iso_code.lower()}_admin_level_{admin_level}_boundaries.csv"
    save_boundaries_to_csv(boundaries, str(boundaries_csv))

    # Step 2: Analyze each subdivision
    logger_admin.info(f"\nStep 2: Analyzing each subdivision...")

    results = []
    failed_subdivisions = []
    successful_count = 0

    for idx, boundary in enumerate(boundaries):
        subdivision_name = boundary['name']
        bbox = boundary['bbox']
        area_km2 = bbox_area_km2(bbox)

        logger_admin.info(f"\n{'='*80}")
        logger_admin.info(f"[{idx+1}/{len(boundaries)}] {subdivision_name}")
        logger_admin.info(f"Bbox: {bbox}")
        logger_admin.info(f"Area: {area_km2:,.0f} km²")
        logger_admin.info(f"{'='*80}")

        # Create safe filename from subdivision name
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_'
                           for c in subdivision_name).strip().replace(' ', '_').lower()

        # Create subdivision output directory
        subdivision_output = country_output / f"admin_{admin_level}" / safe_name
        subdivision_output.mkdir(parents=True, exist_ok=True)

        try:
            if start_year and end_year:
                # Time series analysis
                from time_series_analysis import analyze_region_time_series

                logger_admin.info(f"Running time series analysis ({start_year}-{end_year})")
                subdivision_data = analyze_region_time_series(
                    region_name=safe_name,
                    bbox=bbox,
                    start_year=start_year,
                    end_year=end_year,
                    interval=interval,
                    filter=filter,
                    path=str(subdivision_output / "time_series"),
                    base_filename=f"{safe_name}_buildings",
                    use_chunked_threshold_km2=chunked_threshold_km2,
                    resume=resume
                )
            else:
                # Snapshot analysis
                logger_admin.info(f"Running snapshot analysis")
                timestamp = "2025-08-01"

                # Use chunking if area exceeds threshold
                if area_km2 > chunked_threshold_km2:
                    logger_admin.info(f"Using chunked processing (area > {chunked_threshold_km2} km²)")
                    subdivision_data = get_poly_coords_chunked(
                        region_name=safe_name,
                        bounds=bbox,
                        filter=filter,
                        time_param=timestamp,
                        path=str(subdivision_output),
                        filename=f"{safe_name}_buildings.csv",
                        resume=resume,
                        cleanup_after=True
                    )
                else:
                    logger_admin.info(f"Using standard processing (area <= {chunked_threshold_km2} km²)")
                    subdivision_data = get_poly_coords(
                        region_name=safe_name,
                        bounds=bbox,
                        filter=filter,
                        time_param=timestamp,
                        path=str(subdivision_output),
                        filename=f"{safe_name}_buildings.csv",
                        include_counts=True,
                        include_user_count=include_user_count
                    )

            if subdivision_data is not None and not subdivision_data.empty:
                # Add metadata
                subdivision_data['subdivision_name'] = subdivision_name
                subdivision_data['subdivision_name_safe'] = safe_name
                subdivision_data['osm_id'] = boundary['osm_id']
                subdivision_data['admin_level'] = admin_level
                subdivision_data['area_km2'] = area_km2
                subdivision_data['bbox'] = bbox

                results.append(subdivision_data)
                successful_count += 1
                logger_admin.info(f"✓ {subdivision_name} completed ({len(subdivision_data)} rows)")
            else:
                logger_admin.warning(f"✗ {subdivision_name} returned no data")
                failed_subdivisions.append(subdivision_name)

        except Exception as e:
            logger_admin.error(f"✗ {subdivision_name} failed: {str(e)}", exc_info=True)
            failed_subdivisions.append(subdivision_name)
            continue

    # Step 3: Aggregate and save combined results
    logger_admin.info(f"\n{'='*80}")
    logger_admin.info(f"Step 3: Aggregating results...")
    logger_admin.info(f"{'='*80}")

    if results:
        combined_df = pd.concat(results, ignore_index=True)

        # Save combined results
        combined_file = country_output / f"{iso_code.lower()}_admin_level_{admin_level}_combined.csv"
        combined_df.to_csv(combined_file, index=False)
        logger_admin.info(f"Saved combined results: {combined_file}")

        # Calculate summary statistics
        summary_stats = {
            'country_name': country_name,
            'iso_code': iso_code,
            'admin_level': admin_level,
            'total_subdivisions': len(boundaries),
            'successful_subdivisions': successful_count,
            'failed_subdivisions': len(failed_subdivisions),
            'total_buildings': combined_df['@osmId'].nunique() if '@osmId' in combined_df.columns else len(combined_df),
            'analysis_mode': 'time_series' if start_year else 'snapshot',
            'total_area_km2': sum(bbox_area_km2(b['bbox']) for b in boundaries),
            'runtime_minutes': (time.time() - start_time) / 60
        }

        # Save summary
        summary_file = country_output / f"{iso_code.lower()}_admin_level_{admin_level}_summary.json"
        import json
        with open(summary_file, 'w') as f:
            json.dump(summary_stats, f, indent=2)

        logger_admin.info(f"\n{'='*80}")
        logger_admin.info(f"ANALYSIS COMPLETE")
        logger_admin.info(f"{'='*80}")
        logger_admin.info(f"Country: {country_name} ({iso_code})")
        logger_admin.info(f"Admin Level: {admin_level}")
        logger_admin.info(f"Successful: {successful_count}/{len(boundaries)} subdivisions")
        logger_admin.info(f"Failed: {len(failed_subdivisions)} subdivisions")
        if failed_subdivisions:
            logger_admin.info(f"Failed subdivisions: {', '.join(failed_subdivisions[:10])}")
            if len(failed_subdivisions) > 10:
                logger_admin.info(f"  ... and {len(failed_subdivisions) - 10} more")
        logger_admin.info(f"Total buildings: {summary_stats['total_buildings']:,}")
        logger_admin.info(f"Runtime: {summary_stats['runtime_minutes']:.1f} minutes")
        logger_admin.info(f"Results directory: {country_output}")
        logger_admin.info(f"{'='*80}")

        # Create visualizations if requested
        viz_paths = {}
        if create_visualizations:
            try:
                viz_paths = create_admin_subdivision_visualizations(
                    combined_df=combined_df,
                    boundaries=boundaries,
                    country_name=country_name,
                    iso_code=iso_code,
                    admin_level=admin_level,
                    output_dir=str(country_output),
                    top_n=viz_top_n,
                    create_dashboards=True,
                    create_box_plots=True
                )
            except Exception as e:
                logger_admin.error(f"Visualization failed: {e}", exc_info=True)

        return {
            'success': True,
            'combined_data': combined_df,
            'summary': summary_stats,
            'boundaries': boundaries,
            'output_dir': str(country_output),
            'visualizations': viz_paths
        }
    else:
        logger_admin.error("No subdivisions were successfully processed")
        return None


def analyze_multiple_countries_by_admin_level(
    countries_list,
    admin_level=6,
    output_dir="./results",
    **kwargs
):
    """
    Analyze multiple countries, each subdivided by administrative level.

    Args:
        countries_list: List of dicts with 'name' and 'iso_code' keys
                       e.g., [{'name': 'Thailand', 'iso_code': 'TH'}, ...]
        admin_level: Administrative level for subdivision
        output_dir: Base output directory
        **kwargs: Additional arguments passed to analyze_country_by_admin_level()

    Returns:
        Dict with results for each country
    """
    logger.info("=" * 80)
    logger.info(f"MULTI-COUNTRY ADMINISTRATIVE ANALYSIS")
    logger.info(f"Countries: {len(countries_list)}")
    logger.info(f"Admin Level: {admin_level}")
    logger.info("=" * 80)

    all_results = {}
    start_time = time.time()

    for idx, country in enumerate(countries_list):
        country_name = country.get('name')
        iso_code = country.get('iso_code')

        if not country_name or not iso_code:
            logger.warning(f"Skipping invalid country entry: {country}")
            continue

        logger.info(f"\n{'='*80}")
        logger.info(f"[{idx+1}/{len(countries_list)}] Processing: {country_name} ({iso_code})")
        logger.info(f"{'='*80}")

        result = analyze_country_by_admin_level(
            country_name=country_name,
            iso_code=iso_code,
            admin_level=admin_level,
            output_dir=output_dir,
            **kwargs
        )

        if result:
            all_results[iso_code] = result
            logger.info(f"✓ {country_name} completed")
        else:
            logger.warning(f"✗ {country_name} failed")

    total_time = (time.time() - start_time) / 60
    logger.info(f"\n{'='*80}")
    logger.info(f"MULTI-COUNTRY ANALYSIS COMPLETE")
    logger.info(f"Successful: {len(all_results)}/{len(countries_list)} countries")
    logger.info(f"Total runtime: {total_time:.1f} minutes")
    logger.info(f"{'='*80}")

    return all_results
