"""
Visualization Functions for OSM Geometrical Complexity Analysis

This module provides plotting functions to visualize OSM data completeness
and geometrical complexity metrics, with focus on convex hull analysis.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from api_helpers import logger


# ============================================================================
# Plotting Functions
# ============================================================================

def plot_completeness_metrics(summary_df, save_path=None):
    """
    Plot OSM map completeness metrics comparing regions.

    This function creates a comprehensive visualization of building geometry complexity,
    focusing on the ratio between actual area and convex hull area. Higher ratios
    indicate more complex geometries (better mapping quality), while lower ratios
    suggest simpler box-like shapes (potentially automated/raw mapping).

    Args:
        summary_df: DataFrame with summary statistics from get_poly_coords()
                   Expected columns: 'region', 'mean_ratio', 'median_ratio',
                   'multipolygon_ratio', 'mean_inner_rings', 'mean_area'
        save_path: Optional path to save the figure (default: None, displays only)

    Example:
        >>> from geometry_analysis import get_poly_coords
        >>> summary = get_poly_coords('Paris', bbox, ...)
        >>> plot_completeness_metrics(summary)
    """
    if summary_df is None or len(summary_df) == 0:
        logger.error("No data provided for plotting")
        return

    logger.info(f"Plotting completeness metrics for {len(summary_df)} regions")

    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('OSM Building Geometry Completeness Analysis',
                 fontsize=16, fontweight='bold', y=0.995)

    regions = summary_df['region'].tolist()
    x_pos = np.arange(len(regions))

    # Get building counts - use actual count if available, otherwise estimate
    building_counts = []
    for idx, row in summary_df.iterrows():
        # Use actual building count if available
        if 'building_count' in summary_df.columns and pd.notna(row['building_count']):
            count = int(row['building_count'])
            building_counts.append(f"n={count:,}")
        # Fallback: estimate from total area / mean area
        elif 'sum_area' in summary_df.columns and 'mean_area' in summary_df.columns:
            if row['mean_area'] > 0:
                count = int(row['sum_area'] / row['mean_area'])
                building_counts.append(f"n≈{count:,}")
            else:
                building_counts.append("")
        else:
            building_counts.append("")

    # Create region labels with building counts if available
    if any(building_counts):
        region_labels = [f"{reg}\n{cnt}" if cnt else reg
                        for reg, cnt in zip(regions, building_counts)]
    else:
        region_labels = regions

    # ===== Plot 1: Mean Complexity Ratio =====
    ax1 = axes[0, 0]
    mean_ratios = summary_df['mean_ratio'].tolist()
    colors = ['#2ecc71' if r > 0.3 else '#f39c12' if r > 0.15 else '#e74c3c' for r in mean_ratios]

    bars1 = ax1.bar(x_pos, mean_ratios, color=colors, alpha=0.7, edgecolor='black')
    ax1.set_xlabel('Region', fontweight='bold')
    ax1.set_ylabel('Mean Complexity Ratio', fontweight='bold')
    ax1.set_title('Building Complexity: Mean Ratio (Area vs Convex Hull)', fontsize=12)
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels(region_labels, rotation=45, ha='right', fontsize=10)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    # ax1.axhline(y=0.3, color='green', linestyle='--', alpha=0.5, label='High complexity')
    # ax1.axhline(y=0.15, color='orange', linestyle='--', alpha=0.5, label='Medium complexity')
    ax1.legend(loc='upper right', fontsize=8)

    # Add value labels on bars
    for i, (bar, val) in enumerate(zip(bars1, mean_ratios)):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:.3f}', ha='center', va='bottom', fontsize=9)

    # ===== Plot 2: Median Complexity Ratio =====
    ax2 = axes[0, 1]
    median_ratios = summary_df['median_ratio'].tolist()
    colors2 = ['#2ecc71' if r > 0.3 else '#f39c12' if r > 0.15 else '#e74c3c' for r in median_ratios]

    bars2 = ax2.bar(x_pos, median_ratios, color=colors2, alpha=0.7, edgecolor='black')
    ax2.set_xlabel('Region', fontweight='bold')
    ax2.set_ylabel('Median Complexity Ratio', fontweight='bold')
    ax2.set_title('Building Complexity: Median Ratio', fontsize=12)
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(region_labels, rotation=45, ha='right', fontsize=10)
    ax2.grid(axis='y', alpha=0.3, linestyle='--')
    # ax2.axhline(y=0.3, color='green', linestyle='--', alpha=0.5)
    # ax2.axhline(y=0.15, color='orange', linestyle='--', alpha=0.5)

    # Add value labels
    for bar, val in zip(bars2, median_ratios):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:.3f}', ha='center', va='bottom', fontsize=9)

    # ===== Plot 3: MultiPolygon Ratio (Complexity Indicator) =====
    ax3 = axes[1, 0]
    multipoly_ratios = summary_df['multipolygon_ratio'].tolist()

    bars3 = ax3.bar(x_pos, multipoly_ratios, color='#3498db', alpha=0.7, edgecolor='black')
    ax3.set_xlabel('Region', fontweight='bold')
    ax3.set_ylabel('MultiPolygon Ratio', fontweight='bold')
    ax3.set_title('Geometry Complexity: MultiPolygon Features\n(Higher = More Complex Shapes)',
                  fontsize=12)
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels(region_labels, rotation=45, ha='right', fontsize=10)
    ax3.grid(axis='y', alpha=0.3, linestyle='--')

    # Add value labels
    for bar, val in zip(bars3, multipoly_ratios):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:.2%}', ha='center', va='bottom', fontsize=9)

    # ===== Plot 4: Mean Inner Rings (Holes in Buildings) =====
    ax4 = axes[1, 1]
    mean_inner = summary_df['mean_inner_rings'].tolist()

    bars4 = ax4.bar(x_pos, mean_inner, color='#9b59b6', alpha=0.7, edgecolor='black')
    ax4.set_xlabel('Region', fontweight='bold')
    ax4.set_ylabel('Mean Inner Rings per Building', fontweight='bold')
    ax4.set_title('Building Complexity: Average Holes/Courtyards\n(Higher = More Detailed Mapping)',
                  fontsize=12)
    ax4.set_xticks(x_pos)
    ax4.set_xticklabels(region_labels, rotation=45, ha='right', fontsize=10)
    ax4.grid(axis='y', alpha=0.3, linestyle='--')

    # Add value labels
    for bar, val in zip(bars4, mean_inner):
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:.3f}', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()

    # Save if path provided
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Plot saved to {save_path}")

    plt.show()
    logger.info("Completeness metrics plot displayed")


def plot_area_comparison(summary_df, save_path=None):
    """
    Plot comparison of actual area vs convex hull area across regions.
    Includes both absolute values and normalized percentage view.

    Args:
        summary_df: DataFrame with summary statistics from get_poly_coords()
        save_path: Optional path to save the figure
    """
    if summary_df is None or len(summary_df) == 0:
        logger.error("No data provided for plotting")
        return

    logger.info(f"Plotting area comparison for {len(summary_df)} regions")

    # Create figure with 2 subplots (2 rows, 1 column)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12))
    fig.suptitle('Building Area Analysis: Absolute vs Normalized Comparison',
                 fontsize=16, fontweight='bold', y=0.995)

    regions = summary_df['region'].tolist()
    x_pos = np.arange(len(regions))
    width = 0.35

    # Get mean areas
    mean_area = summary_df['mean_area'].tolist()
    mean_chull = summary_df['mean_chull_area'].tolist()

    # Calculate percentages and differences
    percentages = [(area / chull * 100) if chull > 0 else 0
                   for area, chull in zip(mean_area, mean_chull)]
    differences = [chull - area for area, chull in zip(mean_area, mean_chull)]

    # ===== Subplot 1: Absolute Values =====
    bars1 = ax1.bar(x_pos - width/2, mean_area, width, label='Actual Area',
                   color='#3498db', alpha=0.7, edgecolor='black')
    bars2 = ax1.bar(x_pos + width/2, mean_chull, width, label='Convex Hull Area',
                   color='#e74c3c', alpha=0.7, edgecolor='black')

    ax1.set_ylabel('Mean Area (m²)', fontweight='bold', fontsize=12)
    ax1.set_title('Absolute Area Comparison: Actual vs Convex Hull\n(Closer values = Simpler/Box-like shapes)',
                 fontsize=13, fontweight='bold')
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels(regions, rotation=45, ha='right', fontsize=11)
    ax1.legend(fontsize=11, loc='upper left')
    ax1.grid(axis='y', alpha=0.3, linestyle='--')

    # Add percentage labels on bars
    for i, (bar1, bar2, pct) in enumerate(zip(bars1, bars2, percentages)):
        height1 = bar1.get_height()
        height2 = bar2.get_height()

        # Label on actual area bar
        ax1.text(bar1.get_x() + bar1.get_width()/2., height1,
                f'{height1:.1f}m²\n({pct:.1f}%)',
                ha='center', va='bottom', fontsize=9, fontweight='bold')

        # Label on convex hull bar
        ax1.text(bar2.get_x() + bar2.get_width()/2., height2,
                f'{height2:.1f}m²',
                ha='center', va='bottom', fontsize=9)

    # ===== Subplot 2: Normalized Percentage View =====
    # Show actual area as percentage of convex hull
    bars3 = ax2.bar(x_pos, percentages, color='#2ecc71', alpha=0.7, edgecolor='black',
                    label='Actual Area (% of Convex Hull)')

    # Add reference line at 100%
    ax2.axhline(y=100, color='red', linestyle='--', linewidth=2, alpha=0.5,
                label='100% (Perfect match = Box-like)')
    ax2.axhline(y=95, color='orange', linestyle='--', linewidth=1, alpha=0.4,
                label='95% (Very Simple)')
    ax2.axhline(y=90, color='yellow', linestyle='--', linewidth=1, alpha=0.4,
                label='90% (Moderate Complexity)')

    ax2.set_xlabel('Region', fontweight='bold', fontsize=12)
    ax2.set_ylabel('Actual Area as % of Convex Hull', fontweight='bold', fontsize=12)
    ax2.set_title('Normalized Comparison: Area Efficiency Ratio\n(Lower % = More Complex/Irregular Shapes)',
                 fontsize=13, fontweight='bold')
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(regions, rotation=45, ha='right', fontsize=11)
    ax2.set_ylim([0, 105])  # Set y-axis from 0 to 105%
    ax2.legend(fontsize=10, loc='lower right')
    ax2.grid(axis='y', alpha=0.3, linestyle='--')

    # Add percentage labels and gap info on bars
    for i, (bar, pct, diff) in enumerate(zip(bars3, percentages, differences)):
        height = bar.get_height()

        # Color code based on percentage
        if pct > 95:
            color = '#e74c3c'  # Red - very simple
        elif pct > 90:
            color = '#f39c12'  # Orange - simple
        else:
            color = '#27ae60'  # Green - complex

        bar.set_color(color)
        bar.set_alpha(0.7)

        # Label showing percentage and absolute gap
        ax2.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{pct:.2f}%\nΔ {diff:.1f}m²',
                ha='center', va='bottom', fontsize=9, fontweight='bold')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Plot saved to {save_path}")

    plt.show()
    logger.info("Area comparison plot displayed")


def plot_summary_dashboard(summary_data_list, save_path=None):
    """
    Create a comprehensive dashboard from multiple region analyses.

    This is the main plotting function that combines data from multiple regions
    and creates a complete visualization of OSM mapping completeness.

    Args:
        summary_data_list: List of DataFrames from get_poly_coords() calls
        save_path: Optional path to save the figure

    Example:
        >>> summaries = []
        >>> for region, bbox in regions.items():
        >>>     summary = get_poly_coords(region, bbox, ...)
        >>>     summaries.append(summary)
        >>> plot_summary_dashboard(summaries, 'completeness_dashboard.png')
    """
    if not summary_data_list or all(df is None for df in summary_data_list):
        logger.error("No valid data provided for dashboard")
        return

    # Combine all summaries into one DataFrame
    valid_dfs = [df for df in summary_data_list if df is not None and not df.empty]

    if not valid_dfs:
        logger.error("No valid DataFrames to plot")
        return

    combined_df = pd.concat(valid_dfs, ignore_index=True)

    logger.info(f"Creating dashboard for {len(combined_df)} regions")

    # Create both plots
    plot_completeness_metrics(combined_df, save_path=None)

    if save_path:
        # Save completeness plot
        plot_completeness_metrics(combined_df, save_path=save_path.replace('.png', '_completeness.png'))
        # Save area comparison plot
        plot_area_comparison(combined_df, save_path=save_path.replace('.png', '_area_comparison.png'))
        logger.info(f"Dashboard saved to {save_path}")
    else:
        plot_area_comparison(combined_df)


def interpret_complexity_score(mean_ratio):
    """
    Interpret complexity ratio score into mapping quality assessment.

    Args:
        mean_ratio: Mean complexity ratio value (0-1)

    Returns:
        String interpretation of the score

    Interpretation guide:
        - 0.00-0.10: Very simple, likely automated box mapping
        - 0.10-0.20: Simple shapes, basic manual mapping
        - 0.20-0.35: Moderate complexity, decent manual mapping
        - 0.35-0.50: High complexity, detailed manual mapping
        - 0.50+: Very high complexity, excellent detailed mapping
    """
    if mean_ratio < 0.10:
        return "Very Low - Likely automated box mapping with minimal human refinement"
    elif mean_ratio < 0.20:
        return "Low - Simple shapes indicating basic manual mapping"
    elif mean_ratio < 0.35:
        return "Moderate - Decent level of manual mapping with some detail"
    elif mean_ratio < 0.50:
        return "High - Detailed manual mapping with complex geometries"
    else:
        return "Very High - Excellent detailed mapping with complex features"


def print_completeness_summary(summary_df):
    """
    Print text summary of completeness analysis.

    Args:
        summary_df: DataFrame with summary statistics
    """
    if summary_df is None or len(summary_df) == 0:
        print("No data to summarize")
        return

    print("\n" + "="*80)
    print("OSM BUILDING GEOMETRY COMPLETENESS SUMMARY")
    print("="*80)

    for _, row in summary_df.iterrows():
        region = row['region']
        mean_ratio = row['mean_ratio']
        interpretation = interpret_complexity_score(mean_ratio)

        print(f"\n{region.upper()}")
        print("-" * 80)
        print(f"  Mean Complexity Ratio:     {mean_ratio:.4f}")
        print(f"  Median Complexity Ratio:   {row['median_ratio']:.4f}")
        print(f"  MultiPolygon Features:     {row['multipolygon_ratio']:.2%}")
        print(f"  Mean Inner Rings/Holes:    {row['mean_inner_rings']:.3f}")
        print(f"  Mean Building Area:        {row['mean_area']:.2f} m²")
        print(f"  Quality Assessment:        {interpretation}")

    print("\n" + "="*80)
    print("INTERPRETATION GUIDE:")
    print("  - Complexity Ratio: 1 - (actual_area / convex_hull_area)")
    print("    Higher values = More complex shapes = Better mapping quality")
    print("  - MultiPolygon Ratio: Percentage of buildings with multiple parts")
    print("  - Inner Rings: Average number of holes/courtyards per building")
    print("="*80 + "\n")


def plot_time_series_complexity(ts_df, metric='mean_ratio', region_column='region',
                                timestamp_column='timestamp', save_path=None,
                                title="Geometrical Complexity Evolution Over Time"):
    """
    Plot time series line chart showing complexity metric evolution.

    Args:
        ts_df: Time series DataFrame
        metric: Metric column to plot (default: 'mean_ratio')
        region_column: Column containing region names
        timestamp_column: Column containing timestamps
        save_path: Optional path to save the plot
        title: Plot title

    Returns:
        matplotlib figure object
    """
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from datetime import datetime

    # Convert timestamp strings to datetime
    ts_df = ts_df.copy()
    ts_df[timestamp_column] = pd.to_datetime(ts_df[timestamp_column])

    # Get unique regions
    regions = ts_df[region_column].unique()

    # Create figure
    fig, ax = plt.subplots(figsize=(14, 8))

    # Plot line for each region
    for region in regions:
        region_data = ts_df[ts_df[region_column] == region].sort_values(timestamp_column)
        ax.plot(region_data[timestamp_column], region_data[metric],
               marker='o', linewidth=2, markersize=6, label=region, alpha=0.8)

    # Formatting
    ax.set_xlabel('Time', fontsize=12, fontweight='bold')
    ax.set_ylabel(f'{metric.replace("_", " ").title()}', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    ax.grid(True, alpha=0.3, linestyle='--')

    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    plt.xticks(rotation=45, ha='right')

    # Add reference lines if it's a ratio metric
    if 'ratio' in metric:
        mean = ts_df['mean_ratio'].mean()
        ax.axhline(y=mean, color='red', linestyle=':', alpha=0.7, label='Mean')
    #     ax.axhline(y=0.2, color='orange', linestyle=':', alpha=0.3, label='Moderate (0.2)')
    #     ax.axhline(y=0.3, color='green', linestyle=':', alpha=0.3, label='Complex (0.3)')

    ax.legend(loc='best', fontsize=10)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Time series plot saved to {save_path}")

    return fig


def plot_time_series_heatmap(ts_df, metric='mean_ratio', region_column='region',
                             timestamp_column='timestamp', save_path=None,
                             title="Temporal Evolution Heatmap"):
    """
    Create heatmap showing metric values across regions and time.

    Args:
        ts_df: Time series DataFrame
        metric: Metric column to plot (default: 'mean_ratio')
        region_column: Column containing region names
        timestamp_column: Column containing timestamps
        save_path: Optional path to save the plot
        title: Plot title

    Returns:
        matplotlib figure object
    """
    import matplotlib.pyplot as plt
    import seaborn as sns

    # Pivot data for heatmap
    pivot_data = ts_df.pivot(index=region_column, columns=timestamp_column, values=metric)

    # Create figure
    fig, ax = plt.subplots(figsize=(16, len(pivot_data) * 0.8 + 2))

    # Create heatmap
    sns.heatmap(pivot_data, annot=True, fmt='.3f', cmap='RdYlGn', center=0.2,
               cbar_kws={'label': metric.replace('_', ' ').title()},
               linewidths=0.5, ax=ax)

    # Formatting
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel('Time', fontsize=12, fontweight='bold')
    ax.set_ylabel('Region', fontsize=12, fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Heatmap saved to {save_path}")

    return fig


def plot_growth_comparison(ts_df, metric='mean_ratio', region_column='region',
                          timestamp_column='timestamp', save_path=None):
    """
    Create multi-panel comparison showing absolute values, changes, and growth rates.

    Args:
        ts_df: Time series DataFrame
        metric: Metric column to analyze
        region_column: Column containing region names
        timestamp_column: Column containing timestamps
        save_path: Optional path to save the plot

    Returns:
        matplotlib figure object
    """
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from time_series_analysis import calculate_growth_metrics

    # Convert timestamps
    ts_df = ts_df.copy()
    ts_df[timestamp_column] = pd.to_datetime(ts_df[timestamp_column])

    # Calculate growth metrics for each region
    regions = ts_df[region_column].unique()
    growth_data = []

    for region in regions:
        region_data = ts_df[ts_df[region_column] == region].sort_values(timestamp_column)
        region_growth = calculate_growth_metrics(region_data, metric)
        growth_data.append(region_growth)

    growth_df = pd.concat(growth_data, ignore_index=True)

    # Create figure with 3 subplots
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))

    # Plot 1: Absolute values
    for region in regions:
        region_data = growth_df[growth_df[region_column] == region]
        axes[0].plot(region_data[timestamp_column], region_data[metric],
                    marker='o', linewidth=2, label=region, alpha=0.8)

    axes[0].set_ylabel(f'{metric.replace("_", " ").title()}', fontsize=11, fontweight='bold')
    axes[0].set_title('Absolute Metric Values Over Time', fontsize=12, fontweight='bold')
    axes[0].legend(loc='best')
    axes[0].grid(True, alpha=0.3)

    # Plot 2: Absolute change
    for region in regions:
        region_data = growth_df[growth_df[region_column] == region]
        axes[1].plot(region_data[timestamp_column], region_data[f'{metric}_change'],
                    marker='s', linewidth=2, label=region, alpha=0.8)

    axes[1].axhline(y=0, color='black', linestyle='-', alpha=0.3)
    axes[1].set_ylabel(f'Change in {metric.replace("_", " ").title()}', fontsize=11, fontweight='bold')
    axes[1].set_title('Period-over-Period Change', fontsize=12, fontweight='bold')
    axes[1].legend(loc='best')
    axes[1].grid(True, alpha=0.3)

    # Plot 3: Percentage change
    for region in regions:
        region_data = growth_df[growth_df[region_column] == region]
        axes[2].plot(region_data[timestamp_column], region_data[f'{metric}_pct_change'],
                    marker='^', linewidth=2, label=region, alpha=0.8)

    axes[2].axhline(y=0, color='black', linestyle='-', alpha=0.3)
    axes[2].set_ylabel('Percentage Change (%)', fontsize=11, fontweight='bold')
    axes[2].set_xlabel('Time', fontsize=11, fontweight='bold')
    axes[2].set_title('Percentage Change Over Time', fontsize=12, fontweight='bold')
    axes[2].legend(loc='best')
    axes[2].grid(True, alpha=0.3)

    # Format x-axis dates for all subplots
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.YearLocator())
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Growth comparison plot saved to {save_path}")

    return fig


def plot_time_series_dashboard(ts_df, metric='mean_ratio', save_path=None):
    """
    Create comprehensive dashboard with multiple time series visualizations.

    Args:
        ts_df: Time series DataFrame
        metric: Metric to analyze (default: 'mean_ratio')
        save_path: Optional path to save the plot

    Returns:
        matplotlib figure object
    """
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    # Convert timestamps
    ts_df = ts_df.copy()
    ts_df['timestamp'] = pd.to_datetime(ts_df['timestamp'])

    regions = ts_df['region'].unique()
    n_regions = len(regions)

    # Create figure with multiple subplots
    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)

    # 1. Main time series (large, spans top row)
    ax1 = fig.add_subplot(gs[0, :])
    for region in regions:
        region_data = ts_df[ts_df['region'] == region].sort_values('timestamp')
        ax1.plot(region_data['timestamp'], region_data[metric],
                marker='o', linewidth=2.5, markersize=7, label=region, alpha=0.85)

    ax1.set_ylabel(f'{metric.replace("_", " ").title()}', fontsize=12, fontweight='bold')
    ax1.set_title('Geometrical Complexity Evolution Over Time', fontsize=14, fontweight='bold', pad=15)
    ax1.legend(loc='best', fontsize=10, ncol=min(3, n_regions))
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax1.xaxis.set_major_locator(mdates.YearLocator())

    # 2. Distribution by region (box plot)
    ax2 = fig.add_subplot(gs[1, 0])
    data_for_box = [ts_df[ts_df['region'] == r][metric].values for r in regions]
    bp = ax2.boxplot(data_for_box, labels=regions, patch_artist=True)
    for patch in bp['boxes']:
        patch.set_facecolor('lightblue')
        patch.set_alpha(0.7)
    ax2.set_ylabel(metric.replace('_', ' ').title(), fontsize=11, fontweight='bold')
    ax2.set_title('Distribution by Region', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # 3. Change over time (bar chart showing start vs end)
    ax3 = fig.add_subplot(gs[1, 1])
    start_values = []
    end_values = []
    for region in regions:
        region_data = ts_df[ts_df['region'] == region].sort_values('timestamp')
        start_values.append(region_data[metric].iloc[0])
        end_values.append(region_data[metric].iloc[-1])

    x = range(len(regions))
    width = 0.35
    ax3.bar([i - width/2 for i in x], start_values, width, label='Start', alpha=0.8, color='coral')
    ax3.bar([i + width/2 for i in x], end_values, width, label='End', alpha=0.8, color='skyblue')
    ax3.set_ylabel(metric.replace('_', ' ').title(), fontsize=11, fontweight='bold')
    ax3.set_title('Start vs End Comparison', fontsize=12, fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels(regions, rotation=45, ha='right')
    ax3.legend()
    ax3.grid(True, alpha=0.3, axis='y')

    # 4. Cumulative improvement (if data shows improvement)
    ax4 = fig.add_subplot(gs[2, :])
    for region in regions:
        region_data = ts_df[ts_df['region'] == region].sort_values('timestamp')
        if len(region_data) > 1:
            start_val = region_data[metric].iloc[0]
            cumulative_change = region_data[metric] - start_val
            ax4.plot(region_data['timestamp'], cumulative_change,
                    marker='o', linewidth=2, label=region, alpha=0.8)

    ax4.axhline(y=0, color='black', linestyle='-', alpha=0.5, linewidth=1)
    ax4.set_ylabel(f'Cumulative Change in {metric.replace("_", " ").title()}',
                  fontsize=11, fontweight='bold')
    ax4.set_xlabel('Time', fontsize=11, fontweight='bold')
    ax4.set_title('Cumulative Change from Baseline', fontsize=12, fontweight='bold')
    ax4.legend(loc='best', fontsize=10)
    ax4.grid(True, alpha=0.3, linestyle='--')
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax4.xaxis.set_major_locator(mdates.YearLocator())
    plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.suptitle('OSM Geometrical Complexity: Time Series Analysis Dashboard',
                fontsize=16, fontweight='bold', y=0.995)

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Time series dashboard saved to {save_path}")

    return fig


# ============================================================================
# User Count Analysis
# ============================================================================

def plot_users_vs_complexity(summary_df, save_path=None, show_labels=True):
    """
    Create scatter plot showing relationship between number of users and complexity.

    Args:
        summary_df: DataFrame with user_count and mean_ratio columns
        save_path: Optional path to save the plot
        show_labels: If True, show individual point labels. If False, use legend for regions.

    Returns:
        matplotlib figure object
    """
    import matplotlib.pyplot as plt
    import numpy as np

    # Filter to rows with user count data
    df = summary_df.copy()
    if 'user_count' not in df.columns or 'mean_ratio' not in df.columns:
        logger.warning("user_count or mean_ratio column not found in summary DataFrame")
        return None

    # Remove rows with missing data
    df = df.dropna(subset=['user_count', 'mean_ratio'])

    if len(df) == 0:
        logger.warning("No data available for user count vs complexity plot")
        return None

    fig, ax = plt.subplots(figsize=(12, 8))

    # Check if we have multiple regions
    has_multiple_regions = 'region' in df.columns and df['region'].nunique() > 1

    if has_multiple_regions and not show_labels:
        # Extract base region name (remove timestamp suffix)
        df['base_region'] = df['region'].str.replace(r'_\d{4}-\d{2}-\d{2}$', '', regex=True)

        # Plot each region with different color
        import matplotlib.cm as cm
        regions = df['base_region'].unique()
        colors = cm.tab10(np.linspace(0, 1, len(regions)))

        for region, color in zip(regions, colors):
            region_data = df[df['base_region'] == region]
            ax.scatter(
                region_data['user_count'],
                region_data['mean_ratio'],
                s=100,
                alpha=0.6,
                c=[color],
                edgecolors='black',
                linewidths=1,
                label=region.replace('_', ' ').title()
            )
    else:
        # Single region or show_labels=True: use colormap
        scatter = ax.scatter(
            df['user_count'],
            df['mean_ratio'],
            s=100,
            alpha=0.6,
            c=df['mean_ratio'],
            cmap='RdYlGn',
            edgecolors='black',
            linewidths=1
        )

        # Add colorbar
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('Mean Complexity Ratio', rotation=270, labelpad=20, fontweight='bold')

    # Add region labels only if requested
    if show_labels and 'region' in df.columns:
        for idx, row in df.iterrows():
            ax.annotate(
                row['region'],
                (row['user_count'], row['mean_ratio']),
                xytext=(5, 5),
                textcoords='offset points',
                fontsize=9,
                alpha=0.8
            )

    # Add trend line if enough points
    if len(df) >= 3:
        z = np.polyfit(df['user_count'], df['mean_ratio'], 1)
        p = np.poly1d(z)
        x_trend = np.linspace(df['user_count'].min(), df['user_count'].max(), 100)
        ax.plot(x_trend, p(x_trend), "r--", alpha=0.5, linewidth=2, label=f'Trend: y={z[0]:.2e}x+{z[1]:.3f}')

    # Labels and title
    ax.set_xlabel('Number of Contributors/Users', fontsize=12, fontweight='bold')
    ax.set_ylabel('Mean Complexity Ratio', fontsize=12, fontweight='bold')
    ax.set_title('OSM Building Complexity vs. Number of Contributors', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, linestyle='--')

    # Add reference lines for complexity thresholds
    # ax.axhline(y=0.30, color='green', linestyle='--', alpha=0.4, label='High complexity')
    # ax.axhline(y=0.15, color='orange', linestyle='--', alpha=0.4, label='Medium complexity')

    ax.legend(loc='best', fontsize=10)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"User count vs complexity plot saved to {save_path}")

    return fig


# ============================================================================
# Box Plot Distributions
# ============================================================================

def plot_complexity_boxplots(data_df, region_column='region', save_path=None):
    """
    Create box plots showing distribution of complexity ratios across regions.

    This shows the full distribution (quartiles, outliers) rather than just mean/median.

    Args:
        data_df: DataFrame with detailed building data (distribution=True from get_poly_coords)
                Must have 'region_name' or region_column and 'ratio' columns
        region_column: Column name containing region identifiers
        save_path: Optional path to save the plot

    Returns:
        matplotlib figure object
    """
    import matplotlib.pyplot as plt
    import numpy as np

    if region_column not in data_df.columns or 'ratio' not in data_df.columns:
        logger.warning(f"Required columns not found. Need '{region_column}' and 'ratio'")
        return None

    # Prepare data for box plot
    regions = data_df[region_column].unique()
    data_by_region = [data_df[data_df[region_column] == r]['ratio'].values for r in regions]

    fig, ax = plt.subplots(figsize=(14, 8))

    # Create box plot
    bp = ax.boxplot(data_by_region,
                    labels=regions,
                    patch_artist=True,
                    showmeans=True,
                    meanline=True,
                    notch=True,
                    vert=True)

    # Color the boxes by median complexity
    for patch, region_data in zip(bp['boxes'], data_by_region):
        median_val = np.median(region_data)
        if median_val > 0.30:
            color = '#2ecc71'  # Green - high complexity
        elif median_val > 0.15:
            color = '#f39c12'  # Orange - medium
        else:
            color = '#e74c3c'  # Red - low
        patch.set_facecolor(color)
        patch.set_alpha(0.6)

    # Styling
    ax.set_xlabel('Region', fontsize=12, fontweight='bold')
    ax.set_ylabel('Complexity Ratio', fontsize=12, fontweight='bold')
    ax.set_title('Distribution of Building Complexity Ratios', fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    # Add reference lines
    # ax.axhline(y=0.30, color='green', linestyle='--', alpha=0.4, linewidth=1.5, label='High complexity threshold')
    # ax.axhline(y=0.15, color='orange', linestyle='--', alpha=0.4, linewidth=1.5, label='Medium complexity threshold')

    # Rotate labels if many regions
    if len(regions) > 5:
        plt.xticks(rotation=45, ha='right')

    ax.legend(loc='upper right', fontsize=10)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Box plot saved to {save_path}")

    return fig


def plot_time_series_boxplots(ts_detailed_df, timestamp_column='timestamp',
                               region_column='region_name', save_path=None):
    """
    Create box plots showing how complexity distribution evolves over time.

    Args:
        ts_detailed_df: DataFrame with full building data across multiple timestamps
                       Must have timestamp, region_name, and ratio columns
        timestamp_column: Column containing timestamps
        region_column: Column containing region names
        save_path: Optional path to save the plot

    Returns:
        matplotlib figure object
    """
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np

    if timestamp_column not in ts_detailed_df.columns or 'ratio' not in ts_detailed_df.columns:
        logger.warning(f"Required columns not found for time series box plot")
        return None

    # Convert timestamps
    ts_detailed_df = ts_detailed_df.copy()
    ts_detailed_df[timestamp_column] = pd.to_datetime(ts_detailed_df[timestamp_column])

    # Get unique timestamps and regions
    timestamps = sorted(ts_detailed_df[timestamp_column].unique())
    regions = ts_detailed_df[region_column].unique() if region_column in ts_detailed_df.columns else [None]

    # Create subplot for each region
    n_regions = len(regions)
    fig, axes = plt.subplots(n_regions, 1, figsize=(14, 6*n_regions), squeeze=False)

    for idx, region in enumerate(regions):
        ax = axes[idx, 0]

        # Filter data for this region
        if region:
            region_data = ts_detailed_df[ts_detailed_df[region_column] == region]
            title = f'Complexity Distribution Evolution - {region}'
        else:
            region_data = ts_detailed_df
            title = 'Complexity Distribution Evolution'

        # Prepare data for each timestamp
        data_by_time = [region_data[region_data[timestamp_column] == ts]['ratio'].values
                       for ts in timestamps]

        # Create box plot
        positions = np.arange(len(timestamps))
        bp = ax.boxplot(data_by_time,
                       positions=positions,
                       patch_artist=True,
                       showmeans=True,
                       widths=0.6)

        # Color boxes by trend (green if improving, red if declining)
        medians = [np.median(d) if len(d) > 0 else 0 for d in data_by_time]
        for i, (patch, median_val) in enumerate(zip(bp['boxes'], medians)):
            if i == 0:
                color = '#3498db'  # Blue for first
            elif median_val > medians[i-1]:
                color = '#2ecc71'  # Green - improving
            elif median_val < medians[i-1]:
                color = '#e74c3c'  # Red - declining
            else:
                color = '#95a5a6'  # Gray - stable

            patch.set_facecolor(color)
            patch.set_alpha(0.6)

        # Styling
        ax.set_xlabel('Time', fontsize=11, fontweight='bold')
        ax.set_ylabel('Complexity Ratio', fontsize=11, fontweight='bold')
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        # Set x-axis labels as dates
        ax.set_xticks(positions)
        ax.set_xticklabels([ts.strftime('%Y-%m') for ts in timestamps], rotation=45, ha='right')

        # Add reference lines
        # ax.axhline(y=0.30, color='green', linestyle='--', alpha=0.3, linewidth=1)
        # ax.axhline(y=0.15, color='orange', linestyle='--', alpha=0.3, linewidth=1)

    plt.suptitle('OSM Building Complexity: Distribution Over Time',
                fontsize=14, fontweight='bold', y=0.995)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Time series box plots saved to {save_path}")

    return fig
