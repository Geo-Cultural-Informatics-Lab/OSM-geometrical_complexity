## Administrative Subdivision Analysis - Complete Guide

This guide explains how to analyze countries automatically subdivided by administrative levels (provinces, districts, sub-districts, etc.).

## Overview

The admin subdivision feature allows you to:
- **Automatically subdivide** any country by administrative level
- **Analyze each subdivision** separately (e.g., each district in Thailand)
- **Apply chunking within subdivisions** for large districts
- **Organize results hierarchically** by country → admin_level → subdivision
- **Aggregate data** for both individual subdivisions and full country

## Quick Start

### 1. Create Configuration File

```yaml
analysis:
  mode: batch_countries

countries:
  source: list
  iso_codes: ['TH']  # Thailand

  # Enable admin subdivision
  subdivide_by_admin_level: true
  admin_level: 6  # Districts
```

### 2. Run Analysis

```bash
python main.py --config config/thailand_districts_example.yaml
```

### 3. Results Structure

```
results/thailand_districts/
└── th/
    ├── admin_6/
    │   ├── bangkok/
    │   │   └── bangkok_buildings.csv
    │   ├── chiang_mai/
    │   │   └── chiang_mai_buildings.csv
    │   └── ... (927 more districts)
    ├── th_admin_level_6_boundaries.csv      # All districts with bboxes
    ├── th_admin_level_6_combined.csv        # Combined data from all districts
    ├── th_admin_level_6_summary.json        # Analysis summary
    └── th_admin_level_6_analysis.log        # Detailed log
```

## Configuration Options

### Administrative Levels

Different countries use different administrative hierarchies. Common levels:

| Level | Description | Example (Thailand) | Typical Count |
|-------|-------------|-------------------|---------------|
| 2 | Country | Thailand | 1 |
| 4 | Province/State/Region | Changwat | ~50-100 |
| 6 | District/County | Amphoe | ~500-1000 |
| 8 | Sub-district/Municipality | Tambon | ~3000-5000 |

**Thailand specifically:**
- admin_level=4: 77 Provinces (Changwat)
- admin_level=6: 929 Districts (Amphoe) ← **Recommended**
- admin_level=8: 7,255 Sub-districts (Tambon)

### Config Parameters

```yaml
countries:
  # Enable subdivision
  subdivide_by_admin_level: true

  # Administrative level
  admin_level: 6  # 4=province, 6=district, 8=sub-district

  # Cache boundary data (recommended)
  cache_boundaries: true

  # Overpass API timeout (increase for large countries)
  overpass_timeout: 120
```

### Chunking Within Subdivisions

The system automatically applies chunking **within** each subdivision if it exceeds the threshold:

```yaml
analysis_options:
  chunked_threshold_km2: 5000  # Chunk districts larger than 5000 km²
```

**How it works:**
1. Query Overpass API for all districts
2. For each district:
   - If district < 5000 km² → analyze normally
   - If district > 5000 km² → split into chunks, then aggregate
3. Each district gets complete data regardless of size

## Use Cases

### Full Country Analysis
Analyze the entire country as one unit (traditional mode):

```yaml
analysis:
  mode: batch_countries

countries:
  source: list
  iso_codes: ['TH']
  subdivide_by_admin_level: false  # Disabled
```

### District-Level Analysis
Analyze each district separately:

```yaml
countries:
  iso_codes: ['TH']
  subdivide_by_admin_level: true
  admin_level: 6  # Districts
```

### Province-Level Analysis
Analyze by provinces (fewer, larger regions):

```yaml
countries:
  iso_codes: ['TH']
  subdivide_by_admin_level: true
  admin_level: 4  # Provinces (77 regions)
```

### Multiple Countries with Subdivision
Analyze multiple countries, each subdivided:

```yaml
countries:
  source: list
  iso_codes: ['TH', 'VN', 'MM']  # Thailand, Vietnam, Myanmar
  subdivide_by_admin_level: true
  admin_level: 6
```

Results organized as:
```
results/
├── th/  # Thailand - 929 districts
├── vn/  # Vietnam - districts
└── mm/  # Myanmar - districts
```

## Time Series with Admin Subdivision

You can combine time series analysis with admin subdivision:

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

This will analyze each district's evolution over time (2020-2025).

## Performance Considerations

### Caching Boundaries

**Always enable caching** to avoid repeated Overpass API calls:

```yaml
countries:
  cache_boundaries: true  # Saves boundaries to .cache_admin_level_6.json
```

The first run queries Overpass API (~30-60 seconds). Subsequent runs load from cache (instant).

### Processing Time Estimates

**Thailand Districts (929 districts):**
- Boundary query (first time): ~60 seconds
- Boundary query (cached): <1 second
- Per district analysis: ~10-60 seconds each
- Total: **~3-15 hours** depending on:
  - District sizes
  - Chunking frequency
  - Network speed
  - API response times

**Thailand Provinces (77 provinces):**
- Total: **~1-3 hours** (fewer but larger regions)

### Resume Capability

If interrupted, analysis resumes from last completed subdivision:

```yaml
analysis_options:
  resume: true  # Enable resume
```

Progress tracked in `.chunk_status_*.json` files.

## Advanced Features

### Custom Filters

Analyze different features per subdivision:

```yaml
analysis_options:
  filter: "type:way and highway=*"  # Roads instead of buildings
```

### Export Options

```yaml
output:
  export_shapefile: true  # Export to GIS format
  export_individual_buildings: true  # Export individual geometries
```

### Visualization Control

For large-scale analysis (e.g., 929 districts), disable visualizations:

```yaml
visualization:
  create_dashboards: false
  create_time_series_plots: false
  create_user_correlation_plot: false
```

Generate visualizations separately for specific districts of interest.

## API Usage

### Overpass API

- **Purpose**: Get administrative boundaries
- **Endpoint**: https://overpass-api.de/api/interpreter
- **Usage**: One query per country per admin level (cached)
- **Rate limit**: Be respectful, use timeouts

### ohsome API

- **Purpose**: Analyze OSM data per subdivision
- **Endpoint**: https://api.ohsome.org/v1
- **Usage**: Multiple queries per subdivision (chunked if large)
- **Rate limit**: 600 second timeout per request

## Data Flow

```
1. Config File
   ↓
2. Overpass API Query
   → Get all districts with bboxes
   → Cache boundaries
   ↓
3. For Each District:
   → Check size
   → If large: Apply chunking
   → Query ohsome API
   → Analyze geometry
   → Save district data
   ↓
4. Aggregate Results
   → Combine all districts
   → Generate summary
   → Save to country directory
```

## Output Files

### Boundaries CSV
`th_admin_level_6_boundaries.csv`

Contains all districts with metadata:
- name, bbox, center coordinates
- OSM IDs, Wikidata IDs
- Administrative codes

**Use for:**
- Reference lookup
- Creating custom analyses
- GIS integration

### Combined Data CSV
`th_admin_level_6_combined.csv`

All building data from all districts:
- Building geometries
- Complexity metrics
- Subdivision attribution

**Use for:**
- Country-wide analysis
- Cross-district comparisons
- Statistical analysis

### Summary JSON
`th_admin_level_6_summary.json`

Analysis metadata:
```json
{
  "country_name": "Thailand",
  "admin_level": 6,
  "total_subdivisions": 929,
  "successful_subdivisions": 925,
  "failed_subdivisions": 4,
  "total_buildings": 15234567,
  "runtime_minutes": 180.5
}
```

## Troubleshooting

### "No boundaries found"

**Cause**: Invalid ISO code or admin level

**Fix**: Check ISO code and validate admin level exists:
```python
from admin_boundaries import validate_admin_level
has_data, count = validate_admin_level('TH', 6)
print(f"Has data: {has_data}, Count: {count}")
```

### Timeout errors

**Cause**: Overpass API timeout

**Fix**: Increase timeout:
```yaml
countries:
  overpass_timeout: 300  # 5 minutes
```

### Slow performance

**Causes**:
1. Not using cache
2. Large subdivisions not chunking

**Fixes**:
```yaml
countries:
  cache_boundaries: true  # Enable cache

analysis_options:
  chunked_threshold_km2: 5000  # Lower threshold for more chunking
```

### Failed subdivisions

Check log file for specific errors:
```
results/th/th_admin_level_6_analysis.log
```

Common causes:
- Empty districts (no buildings)
- API timeout
- Network issues

## Examples

### Example 1: Thailand Districts Snapshot
```yaml
analysis:
  mode: batch_countries
  timestamp: "2025-08-01"

countries:
  iso_codes: ['TH']
  subdivide_by_admin_level: true
  admin_level: 6
```

### Example 2: Thailand Provinces Time Series
```yaml
analysis:
  mode: batch_countries

time_series:
  enabled: true
  start_year: 2015
  end_year: 2025
  interval: yearly

countries:
  iso_codes: ['TH']
  subdivide_by_admin_level: true
  admin_level: 4  # Provinces (faster, fewer regions)
```

### Example 3: Multiple Countries
```yaml
countries:
  iso_codes: ['TH', 'VN', 'LA', 'KH', 'MM']  # SE Asia
  subdivide_by_admin_level: true
  admin_level: 6
```

## Comparison: Full Country vs Admin Subdivision

| Aspect | Full Country | Admin Subdivision |
|--------|--------------|-------------------|
| **Granularity** | One bbox for entire country | Separate analysis per district |
| **Chunking** | Splits country into arbitrary grid | Respects administrative boundaries |
| **Results** | Single output file | Per-subdivision + combined |
| **Processing** | One large batch | 100s-1000s of smaller batches |
| **Use Case** | Quick country overview | Detailed regional analysis |
| **Best For** | Small countries | Large countries, regional studies |

## Best Practices

1. **Start with provinces** (admin_level=4) to test
2. **Enable caching** to avoid repeated API calls
3. **Use resume** for long-running analyses
4. **Lower chunk threshold** for faster processing
5. **Disable visualizations** for large-scale analyses
6. **Monitor logs** to track progress
7. **Check failed subdivisions** and rerun if needed

## Further Reading

- [Overpass API Documentation](https://overpass-api.de/)
- [ohsome API Documentation](https://docs.ohsome.org/)
- [OpenStreetMap Admin Boundaries](https://wiki.openstreetmap.org/wiki/Tag:boundary%3Dadministrative)
- [Thailand OSM Wiki](https://wiki.openstreetmap.org/wiki/Thailand)
