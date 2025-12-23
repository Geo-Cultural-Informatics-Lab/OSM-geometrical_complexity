"""
Generate geometry samples for top N subdivisions from admin subdivision analysis

This script reads the combined CSV from a completed admin-level analysis
and generates geometry samples for the top N subdivisions.

Usage:
    python generate_admin_samples.py
"""

import pandas as pd
from pathlib import Path
import sys

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent))

from visualization.visualization import plot_sample_polygons


def main():
    # Configuration - update these paths as needed
    iso_code = 'TH'
    admin_level = 4
    top_n = 10
    sample_size = 100  # Number of polygons to sample per subdivision

    # Paths
    base_dir = Path(f'results/thailand_provinces/{iso_code.lower()}')
    combined_csv = base_dir / f'{iso_code.lower()}_admin_level_{admin_level}_combined.csv'
    admin_dir = base_dir / f'admin_{admin_level}'

    print("=" * 80)
    print("GENERATE ADMIN SUBDIVISION GEOMETRY SAMPLES")
    print("=" * 80)
    print(f"\nCountry: {iso_code}")
    print(f"Admin level: {admin_level}")
    print(f"Top N: {top_n}")
    print(f"Sample size per subdivision: {sample_size}")

    # Check files exist
    if not combined_csv.exists():
        print(f"\nERROR: Combined CSV not found: {combined_csv}")
        print("Please run the analysis first with:")
        print(f"  python main.py --config config/thailand_provinces.yaml")
        return

    # Load summary data to identify top N
    print("\nLoading summary data...")
    combined_df = pd.read_csv(combined_csv)

    # Get top N subdivisions by building count
    top_subdivisions = combined_df.nlargest(top_n, 'building_count')[
        ['subdivision_name', 'subdivision_name_safe', 'building_count']
    ]

    print(f"\nTop {top_n} subdivisions by building count:")
    for i, row in enumerate(top_subdivisions.itertuples(), 1):
        print(f"  {i}. {row.subdivision_name}: {row.building_count:,} buildings")

    # Generate samples for each top subdivision
    print(f"\nGenerating samples for top {top_n} subdivisions...")
    for i, row in enumerate(top_subdivisions.itertuples(), 1):
        subdivision_safe = row.subdivision_name_safe
        subdivision_name = row.subdivision_name

        print(f"\n[{i}/{top_n}] {subdivision_name}")

        # Check if building CSV and geojson exist
        subdivision_dir = admin_dir / subdivision_safe
        buildings_csv = subdivision_dir / f'{subdivision_safe}_buildings.csv'
        geom_file = subdivision_dir / f'{subdivision_safe}_buildings_geom.geojson'

        if not buildings_csv.exists():
            print(f"  WARNING: Buildings CSV not found: {buildings_csv}")
            continue

        if not geom_file.exists():
            print(f"  WARNING: Geometry file not found: {geom_file}")
            continue

        # Load building data
        print(f"  Loading building data...")
        buildings_df = pd.read_csv(buildings_csv)
        print(f"  Found {len(buildings_df):,} buildings")

        # Calculate sample counts
        n_complex = min(sample_size // 3, 10)
        n_medium = min(sample_size // 3, 5)
        n_simple = min(sample_size // 3, 5)

        # Generate samples
        sample_path = subdivision_dir / f'{subdivision_safe}_qualitative_samples.png'

        try:
            plot_sample_polygons(
                buildings_df,
                subdivision_name,
                geom_file_path=str(geom_file),
                n_complex=n_complex,
                n_medium=n_medium,
                n_simple=n_simple,
                save_path=str(sample_path)
            )
            print(f"  Samples saved to: {sample_path}")
        except Exception as e:
            print(f"  ERROR: Failed to generate samples: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 80)
    print("GEOMETRY SAMPLING COMPLETE")
    print("=" * 80)
    print(f"\nGenerated samples for {top_n} subdivisions")
    print(f"Samples saved in: {admin_dir}/[subdivision]/samples/")


if __name__ == "__main__":
    main()
