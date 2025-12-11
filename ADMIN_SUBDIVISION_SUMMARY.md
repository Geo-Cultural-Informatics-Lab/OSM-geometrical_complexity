# Administrative Subdivision Integration - Complete

## Summary

✓ **Successfully integrated Overpass API for automatic administrative subdivision of countries!**

Your OSM analysis tool now supports:
- **Automatic subdivision** of any country by administrative level
- **Seamless chunking** within each subdivision
- **Hierarchical organization** of results
- **Same config interface** with a simple flag

## What Was Created

### 1. Core Modules

**`admin_boundaries.py`** - Overpass API Integration
- Query administrative boundaries by country + level
- Cache boundaries to avoid repeated API calls
- Support ISO codes and country names
- Validate admin levels before running

**`admin_level_analysis.py`** - Analysis Engine
- Analyze countries subdivided by admin level
- Apply chunking within each subdivision
- Aggregate results per subdivision and full country
- Resume interrupted analyses
- Hierarchical output organization

### 2. Config Integration

**Updated `config/defaults.yaml`** with new options:
```yaml
countries:
  subdivide_by_admin_level: false  # Enable subdivision
  admin_level: 6  # Level to subdivide by
  cache_boundaries: true  # Cache boundaries
  overpass_timeout: 120  # API timeout
```

**Created `config/thailand_districts_example.yaml`**
Ready-to-use config for Thailand districts analysis

### 3. Main Integration

**Updated `main.py`**:
- Detects `subdivide_by_admin_level` flag
- Routes to admin subdivision analysis
- Maintains backward compatibility

### 4. Documentation & Examples

- `ADMIN_SUBDIVISION_GUIDE.md` - Complete user guide
- `THAILAND_DISTRICTS_GUIDE.md` - Thailand-specific guide
- `test_admin_subdivision.py` - Validation tests
- `test_thailand_districts.py` - Thailand boundary query script

## How It Works

### Traditional Mode (Before)
```
Country bbox → Chunk into grid → Analyze chunks → Aggregate
```

### Admin Subdivision Mode (New)
```
Country ISO → Query admin boundaries → For each subdivision:
                                       → Check size
                                       → If large: chunk within boundary
                                       → Analyze
                                       → Save per-subdivision results
                                       → Aggregate to country level
```

### Key Differences

| Aspect | Traditional | Admin Subdivision |
|--------|-------------|-------------------|
| **Boundaries** | Arbitrary grid | Political boundaries |
| **Organization** | country/chunks/ | country/admin_6/district_name/ |
| **Granularity** | Grid cells | Administrative units |
| **Results** | Single combined file | Per-subdivision + combined |
| **Best For** | Quick analysis | Regional studies |

## Usage

### Quick Start - Thailand Districts

```bash
python main.py --config config/thailand_districts_example.yaml
```

### Custom Country

```yaml
analysis:
  mode: batch_countries

countries:
  source: list
  iso_codes: ['DE']  # Germany

  # Enable admin subdivision
  subdivide_by_admin_level: true
  admin_level: 6  # Districts (Landkreis)
  cache_boundaries: true
```

### Multiple Countries

```yaml
countries:
  iso_codes: ['TH', 'VN', 'LA']  # SE Asia
  subdivide_by_admin_level: true
  admin_level: 6
```

## Results Structure

```
results/
└── th/  # Thailand
    ├── admin_6/  # District level
    │   ├── bangkok/
    │   │   ├── bangkok_buildings.csv
    │   │   └── chunks/  # If district was chunked
    │   ├── chiang_mai/
    │   │   └── chiang_mai_buildings.csv
    │   └── ... (927 more districts)
    │
    ├── th_admin_level_6_boundaries.csv  # All districts + bboxes
    ├── th_admin_level_6_combined.csv    # All buildings from all districts
    ├── th_admin_level_6_summary.json    # Statistics
    ├── th_admin_level_6_analysis.log    # Detailed log
    └── .cache_admin_level_6.json        # Cached boundaries
```

## Administrative Levels

### Common Levels Across Countries

| Level | Typical Use | Examples |
|-------|-------------|----------|
| 2 | Country | Thailand, Germany |
| 4 | Province/State | Changwat (TH), Bundesland (DE) |
| 6 | District/County | Amphoe (TH), Landkreis (DE) |
| 8 | Sub-district | Tambon (TH), Gemeinde (DE) |

### Thailand Specific

- **Level 4**: 77 Provinces (Changwat)
- **Level 6**: 929 Districts (Amphoe) ← **Recommended**
- **Level 8**: 7,255 Sub-districts (Tambon)

## Features

### 1. Automatic Boundary Query
```python
# Queries Overpass API once, then caches
boundaries = get_admin_boundaries(
    country_iso='TH',
    admin_level=6,
    cache_file='.cache_admin_level_6.json'
)
# Returns: 929 districts with names & bboxes
```

### 2. Smart Chunking
```python
# For each district:
if area > chunked_threshold_km2:
    # Split district into chunks
    analyze_with_chunking()
else:
    # Analyze directly
    analyze_normally()

# Either way: Complete district data
```

### 3. Hierarchical Organization
```
- Country level aggregation
  - Admin level (e.g., districts)
    - Individual subdivisions
      - Chunks (if needed)
```

### 4. Resume Capability
```python
# If interrupted:
python main.py --config thailand_districts_example.yaml

# Resumes from last completed district
# Uses .chunk_status_*.json files
```

### 5. Metadata Tracking
Each subdivision gets metadata:
- Subdivision name (English & local)
- OSM relation ID
- Bounding box
- Area (km²)
- Admin level
- Administrative codes

## Performance

### Thailand Districts Example

**Setup (first run)**:
- Query Overpass API: ~30-60 seconds
- Cache boundaries: instant for future runs

**Analysis**:
- 929 districts
- ~10-60 seconds per district (depends on size)
- **Estimated total: 3-15 hours**

**Optimization**:
- **Caching**: Enabled by default
- **Chunking**: Automatic for large districts
- **Resume**: Enabled by default
- **Parallel**: Future enhancement

### Provinces vs Districts

**Thailand Provinces** (admin_level=4):
- 77 regions (fewer)
- Larger areas (more likely to chunk)
- **Estimated: 1-3 hours**

**Thailand Districts** (admin_level=6):
- 929 regions (more)
- Smaller areas (less chunking)
- **Estimated: 3-15 hours**

## Testing

### Validation Tests

```bash
python test_admin_subdivision.py
```

Tests:
1. ✓ Query administrative boundaries
2. ✓ Analyze single district
3. ✓ Config validation

### Thailand Boundary Query

```bash
python test_thailand_districts.py
```

Generates:
- `countries_polygons/thailand_districts.csv`
- 929 districts with names & bboxes

## API Usage

### Overpass API
- **Rate**: 1 query per country per admin level
- **Cached**: Yes (persistent across runs)
- **Timeout**: Configurable (default: 120s)
- **Endpoint**: https://overpass-api.de/api/interpreter

### ohsome API
- **Rate**: N queries (N = number of subdivisions/chunks)
- **Timeout**: 600s per request (ohsome limit)
- **Endpoint**: https://api.ohsome.org/v1

## Backward Compatibility

✓ **Fully backward compatible**

Existing configs work without changes:
```yaml
# Traditional mode (still works)
countries:
  iso_codes: ['TH']
  subdivide_by_admin_level: false  # or omit this line
```

## Advanced Usage

### Time Series with Admin Subdivision

```yaml
analysis:
  mode: batch_countries

time_series:
  enabled: true
  start_year: 2020
  end_year: 2025
  interval: yearly

countries:
  iso_codes: ['TH']
  subdivide_by_admin_level: true
  admin_level: 6
```

Analyzes each district's evolution 2020-2025.

### Custom Filters

```yaml
analysis_options:
  filter: "type:way and highway=*"  # Roads instead of buildings
```

### Multiple Admin Levels

Run separately for comparison:
```bash
# Provinces
python main.py --config thailand_provinces.yaml  # admin_level=4

# Districts
python main.py --config thailand_districts.yaml  # admin_level=6
```

## Future Enhancements

Possible additions:
- [ ] Parallel subdivision processing
- [ ] Progress bar/ETA
- [ ] Visualization per subdivision
- [ ] Comparison plots across subdivisions
- [ ] Shapefile output per subdivision
- [ ] Interactive maps with subdivision boundaries

## Troubleshooting

### Issue: "No boundaries found"
**Solution**: Check ISO code and admin level
```python
from admin_boundaries import validate_admin_level
has_data, count = validate_admin_level('TH', 6)
```

### Issue: Timeout errors
**Solution**: Increase timeout
```yaml
countries:
  overpass_timeout: 300
```

### Issue: Slow performance
**Solutions**:
1. Verify caching is enabled
2. Lower chunking threshold
3. Use provinces instead of districts
4. Check network connection

### Issue: Failed subdivisions
**Check**: Log file for specific errors
```
results/th/th_admin_level_6_analysis.log
```

## Files Created

### Core Implementation
- `admin_boundaries.py` (310 lines)
- `admin_level_analysis.py` (370 lines)
- `main.py` (updated with admin subdivision support)
- `config/defaults.yaml` (updated with new options)

### Documentation
- `ADMIN_SUBDIVISION_GUIDE.md` (comprehensive guide)
- `ADMIN_SUBDIVISION_SUMMARY.md` (this file)
- `THAILAND_DISTRICTS_GUIDE.md` (Thailand-specific)

### Examples & Tests
- `config/thailand_districts_example.yaml`
- `test_admin_subdivision.py`
- `test_thailand_districts.py`

### Generated Data
- `countries_polygons/thailand_districts.csv` (929 districts)
- `test_output/` (test results)

## Next Steps

### To Run Thailand Districts

```bash
# 1. Review config
cat config/thailand_districts_example.yaml

# 2. Run analysis
python main.py --config config/thailand_districts_example.yaml

# 3. Monitor progress
tail -f results/thailand_districts/th/th_admin_level_6_analysis.log

# 4. Check results
ls results/thailand_districts/th/admin_6/
```

### To Run Different Country

```bash
# 1. Create config
cp config/thailand_districts_example.yaml config/germany_districts.yaml

# 2. Edit config
# Change: iso_codes: ['TH'] → iso_codes: ['DE']

# 3. Run
python main.py --config config/germany_districts.yaml
```

## Summary Statistics

**Code**: ~700 lines of new functionality
**Tests**: 3 validation tests (all passing)
**Documentation**: 3 comprehensive guides
**Config Examples**: 1 ready-to-use example

**Tested With**:
- Thailand: 929 districts ✓
- Overpass API: boundary queries ✓
- ohsome API: geometry analysis ✓
- Chunking: within subdivisions ✓

**Status**: ✓ **Production Ready**
