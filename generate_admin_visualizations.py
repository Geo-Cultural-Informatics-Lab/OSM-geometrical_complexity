"""
Generate visualizations for completed admin subdivision analysis

This script reads the combined CSV from a completed admin-level analysis
and generates visualizations for the top N subdivisions.

Usage:
    python generate_admin_visualizations.py
"""

import pandas as pd
from pathlib import Path
from admin_level_analysis import create_admin_subdivision_visualizations


def main():
    # Configuration - update these paths as needed
    iso_code = 'TH'
    admin_level = 4
    top_n = 10
    use_raw_data = True  # Set to True to load raw building data for better visualizations

    # Paths
    base_dir = Path(f'results/thailand_provinces/{iso_code.lower()}')
    combined_csv = base_dir / f'{iso_code.lower()}_admin_level_{admin_level}_combined.csv'
    boundaries_csv = base_dir / f'{iso_code.lower()}_admin_level_{admin_level}_boundaries.csv'
    admin_dir = base_dir / f'admin_{admin_level}'

    print("=" * 80)
    print("GENERATE ADMIN SUBDIVISION VISUALIZATIONS")
    print("=" * 80)
    print(f"\nCountry: {iso_code}")
    print(f"Admin level: {admin_level}")
    print(f"Top N: {top_n}")
    print(f"Use raw data: {use_raw_data}")

    # Check files exist
    if not combined_csv.exists():
        print(f"\nERROR: Combined CSV not found: {combined_csv}")
        print("Please run the analysis first with:")
        print(f"  python main.py --config config/thailand_provinces.yaml")
        return

    if not boundaries_csv.exists():
        print(f"\nERROR: Boundaries CSV not found: {boundaries_csv}")
        return

    # Load summary data first to identify top N
    print("\nLoading summary data...")
    combined_df = pd.read_csv(combined_csv)
    boundaries_df = pd.read_csv(boundaries_csv)

    # If using raw data, load individual province CSVs for top N
    if use_raw_data and admin_dir.exists():
        print(f"\nLoading raw building data from: {admin_dir}")

        # Get top N provinces by building count
        top_provinces = combined_df.nlargest(top_n, 'building_count')['subdivision_name_safe'].tolist()

        # Load raw data for top N provinces
        raw_dfs = []
        for province_safe in top_provinces:
            province_dir = admin_dir / province_safe
            csv_file = province_dir / f'{province_safe}_buildings.csv'

            if csv_file.exists():
                print(f"  Loading {province_safe}...")
                province_df = pd.read_csv(csv_file)

                # Add subdivision metadata
                province_info = combined_df[combined_df['subdivision_name_safe'] == province_safe].iloc[0]
                province_df['subdivision_name'] = province_info['subdivision_name']
                province_df['subdivision_name_safe'] = province_safe
                province_df['area_km2'] = province_info['area_km2']

                # Add user count if available (at subdivision level, not per building)
                if 'user_count' in province_info.index:
                    province_df['subdivision_user_count'] = province_info['user_count']

                raw_dfs.append(province_df)
            else:
                print(f"  WARNING: {csv_file} not found")

        if raw_dfs:
            print(f"\n  Loaded raw data for {len(raw_dfs)} provinces")
            combined_df = pd.concat(raw_dfs, ignore_index=True)
            print(f"  Total buildings in raw data: {len(combined_df):,}")
        else:
            print("\n  WARNING: No raw data found, using summary data")
            use_raw_data = False

    boundaries_df = pd.read_csv(boundaries_csv)

    print(f"  Combined data: {len(combined_df)} rows")
    print(f"  Boundaries: {len(boundaries_df)} subdivisions")

    # Convert boundaries to list of dicts
    boundaries = boundaries_df.to_dict('records')

    # Create visualizations
    print(f"\nGenerating visualizations for top {top_n} subdivisions...")

    try:
        viz_paths = create_admin_subdivision_visualizations(
            combined_df=combined_df,
            boundaries=boundaries,
            country_name='Thailand',  # Update as needed
            iso_code=iso_code,
            admin_level=admin_level,
            output_dir=str(base_dir),
            top_n=top_n,
            create_dashboards=True,
            create_box_plots=True
        )

        print("\n" + "=" * 80)
        print("VISUALIZATION COMPLETE")
        print("=" * 80)
        print(f"\nGenerated {len(viz_paths)} visualizations:")
        for viz_type, path in viz_paths.items():
            print(f"  {viz_type}: {Path(path).name}")

        print(f"\nAll visualizations saved to: {base_dir}")

    except Exception as e:
        print(f"\nERROR: Visualization failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
