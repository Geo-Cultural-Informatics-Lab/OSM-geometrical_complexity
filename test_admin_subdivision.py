"""
Test script for admin subdivision functionality

This script tests the admin subdivision feature by:
1. Querying a few districts from Thailand
2. Analyzing one district as a proof of concept
3. Validating the output structure
"""

import sys
from pathlib import Path

# Test imports
try:
    from admin_boundaries import get_admin_boundaries, save_boundaries_to_csv
    from admin_level_analysis import analyze_country_by_admin_level
    from api_helpers import logger
    print("SUCCESS: All required modules imported successfully")
except ImportError as e:
    print(f"ERROR: Failed to import modules: {e}")
    sys.exit(1)


def test_get_boundaries():
    """Test getting administrative boundaries from Overpass API."""
    print("\n" + "=" * 80)
    print("TEST 1: Get Administrative Boundaries")
    print("=" * 80)

    print("\nQuerying Overpass API for Thailand districts (admin_level=6)...")
    print("NOTE: This will query only a few districts for testing")

    # Get boundaries (will be cached)
    boundaries = get_admin_boundaries(
        country_iso='TH',
        admin_level=6,
        timeout=120,
        cache_file='test_output/test_boundaries_cache.json'
    )

    if boundaries:
        print(f"\nSUCCESS: Retrieved {len(boundaries)} districts")
        print("\nFirst 3 districts:")
        for i, boundary in enumerate(boundaries[:3], 1):
            print(f"{i}. {boundary['name']}")
            print(f"   Bbox: {boundary['bbox']}")
            print(f"   OSM ID: {boundary['osm_id']}")

        # Save to CSV
        csv_file = 'test_output/test_boundaries.csv'
        print(f"\nSaving boundaries to {csv_file}...")
        save_boundaries_to_csv(boundaries, csv_file)
        print("SUCCESS: Boundaries saved")

        return boundaries
    else:
        print("\nERROR: Failed to retrieve boundaries")
        return None


def test_analyze_single_district(boundaries):
    """Test analyzing a single district."""
    print("\n" + "=" * 80)
    print("TEST 2: Analyze Single District")
    print("=" * 80)

    if not boundaries:
        print("ERROR: No boundaries available")
        return False

    # Pick a small district for testing (Bangkok district)
    test_district = boundaries[0]  # First district
    print(f"\nTest district: {test_district['name']}")
    print(f"Bbox: {test_district['bbox']}")

    # Simulate what analyze_country_by_admin_level would do for one district
    from geometry_analysis import get_poly_coords
    from chunking_utils import bbox_area_km2

    bbox = test_district['bbox']
    area_km2 = bbox_area_km2(bbox)
    print(f"Area: {area_km2:.2f} km²")

    print("\nRunning snapshot analysis for this district...")
    print("(This may take 30-60 seconds depending on district size)")

    try:
        district_data = get_poly_coords(
            region_name='test_district',
            bounds=bbox,
            filter="type:way and building=*",
            time_param="2025-08-01",
            path='test_output/single_district',
            filename='test_district_buildings.csv',
            include_counts=True,
            include_user_count=False  # Skip user count for faster testing
        )

        if district_data is not None and not district_data.empty:
            print(f"\nSUCCESS: Analyzed district")
            print(f"  Buildings found: {len(district_data)}")
            if 'nodes' in district_data.columns:
                avg_nodes = district_data['nodes'].mean()
                print(f"  Average nodes per building: {avg_nodes:.1f}")
            print(f"  Output: test_output/single_district/test_district_buildings.csv")
            return True
        else:
            print("\nWARNING: No data returned (district may be empty)")
            return False

    except Exception as e:
        print(f"\nERROR: Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_integration():
    """Test that config file is valid."""
    print("\n" + "=" * 80)
    print("TEST 3: Config File Validation")
    print("=" * 80)

    config_file = Path('config/thailand_districts_example.yaml')

    if not config_file.exists():
        print(f"ERROR: Config file not found: {config_file}")
        return False

    print(f"\nValidating config file: {config_file}")

    try:
        from config_loader import load_config
        config = load_config(str(config_file))

        print("\nSUCCESS: Config loaded successfully")
        print(f"  Mode: {config['analysis']['mode']}")
        print(f"  Countries: {config['countries']['iso_codes']}")
        print(f"  Admin subdivision: {config['countries']['subdivide_by_admin_level']}")
        print(f"  Admin level: {config['countries']['admin_level']}")

        # Validate required fields
        mode = config.get('analysis', {}).get('mode', 'unknown')
        subdivide = config.get('countries', {}).get('subdivide_by_admin_level', False)
        admin_level = config.get('countries', {}).get('admin_level', 0)
        iso_codes = config.get('countries', {}).get('iso_codes', [])

        print(f"\nValidating configuration values:")
        print(f"  Mode: {mode} (expected: batch_countries)")
        print(f"  Subdivide: {subdivide} (expected: True)")
        print(f"  Admin level: {admin_level} (expected: 6)")
        print(f"  ISO codes: {iso_codes} (expected: ['TH'])")

        assert mode == 'batch_countries', f"Mode should be batch_countries, got {mode}"
        assert subdivide == True, f"subdivide_by_admin_level should be True, got {subdivide}"
        assert admin_level == 6, f"admin_level should be 6, got {admin_level}"
        assert 'TH' in iso_codes, f"'TH' should be in iso_codes, got {iso_codes}"

        print("\nSUCCESS: All config fields valid")
        return True

    except Exception as e:
        print(f"\nERROR: Config validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 80)
    print("ADMIN SUBDIVISION FUNCTIONALITY TESTS")
    print("=" * 80)

    # Create test output directory
    Path('test_output').mkdir(exist_ok=True)

    results = {
        'boundaries': False,
        'analysis': False,
        'config': False
    }

    # Test 1: Get boundaries
    boundaries = test_get_boundaries()
    results['boundaries'] = boundaries is not None

    # Test 2: Analyze single district
    if boundaries:
        results['analysis'] = test_analyze_single_district(boundaries)

    # Test 3: Config validation
    results['config'] = test_config_integration()

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{test_name.title()}: {status}")

    all_passed = all(results.values())
    print("\n" + "=" * 80)
    if all_passed:
        print("ALL TESTS PASSED")
        print("\nYou can now run the full analysis with:")
        print("  python main.py --config config/thailand_districts_example.yaml")
    else:
        print("SOME TESTS FAILED")
        print("\nPlease check the errors above before running full analysis")
    print("=" * 80)

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
