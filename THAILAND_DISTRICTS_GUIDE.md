# Thailand Districts Analysis Guide

## Summary

**YES**, you can get Thailand district names and bounding boxes! However, the ohsome API doesn't provide a direct endpoint to list districts. Instead, you need to use the **Overpass API** to query OpenStreetMap administrative boundaries.

## Quick Answer

### Thailand Administrative Levels:
- **admin_level=2**: Country (Thailand itself)
- **admin_level=4**: Provinces (Changwat) - 77 provinces
- **admin_level=6**: Districts (Amphoe) - **929 districts** ✓
- **admin_level=8**: Sub-districts (Tambon) - thousands

### Generated File:
A CSV file with all 929 Thailand districts has been created at:
```
countries_polygons/thailand_districts.csv
```

## How It Works

### 1. Overpass API (not ohsome API)
The **Overpass API** allows querying OpenStreetMap data, including administrative boundaries:

```python
# Query all Thailand districts
overpass_query = """
[out:json][timeout:60];
area["ISO3166-1"="TH"][admin_level=2];
(
  relation["admin_level"="6"](area);
);
out center tags bb;
"""
```

### 2. ohsome API Limitations
The ohsome API:
- ✓ **CAN**: Query OSM elements within specified boundaries (bbox, bcircles, bpolys)
- ✓ **CAN**: Analyze complexity, count elements, get geometries
- ✗ **CANNOT**: List or retrieve administrative boundary definitions
- ✗ **CANNOT**: Provide a catalog of districts/regions

### 3. Solution: Use Overpass API + ohsome API
1. **Overpass API** → Get district names and bounding boxes
2. **ohsome API** → Analyze each district's OSM data

## Usage

### Option 1: Run the Test Script
```bash
python test_thailand_districts.py
```

This will:
- Query Overpass API for all Thailand districts
- Extract names and bounding boxes
- Save to `countries_polygons/thailand_districts.csv`

### Option 2: Use the CSV Directly
The CSV is already generated with columns:
- `name`: District name (English if available, otherwise local)
- `name_en`: English name
- `name_local`: Thai name
- `bbox`: Bounding box in format "min_lon,min_lat,max_lon,max_lat"
- `center_lat`, `center_lon`: District center coordinates
- `osm_id`: OpenStreetMap relation ID
- `admin_level`: Administrative level (6 for districts)

### Option 3: Integrate with Your Batch Analysis

You can modify your existing `batch_country_analysis.py` to use the districts CSV:

```python
from bbox_utils import load_countries_from_csv

# Load districts as if they were countries
districts = load_countries_from_csv("countries_polygons/thailand_districts.csv")

# districts will be a list like:
# [
#   {'name': 'Phra Nakhon District', 'bbox': '100.487,13.738,100.509,13.772'},
#   {'name': 'Bang Rak District', 'bbox': '100.512,13.718,100.544,13.737'},
#   ...
# ]

# Then analyze each district
for district in districts:
    print(f"Analyzing {district['name']}...")
    analyze_region(bbox=district['bbox'], region_name=district['name'])
```

## Example: Full Thailand + Districts

### Step 1: Run Full Thailand
```python
from bbox_utils import get_country_bbox
from geometry_analysis import get_poly_coords_chunked

# Get full Thailand bbox
thailand_bbox = get_country_bbox("Thailand")
# Result: approximately "97.343,5.613,105.639,20.465"

# Analyze full Thailand
thailand_data = get_poly_coords_chunked(
    region_name="thailand",
    bounds=thailand_bbox,
    filter="type:way and building=*",
    time_param="2025-08-01",
    path="output/thailand"
)
```

### Step 2: Run Each District
```python
import pandas as pd

# Load districts
districts_df = pd.read_csv("countries_polygons/thailand_districts.csv")

# Analyze each district
for idx, row in districts_df.iterrows():
    district_name = row['name'].lower().replace(' ', '_')
    bbox = row['bbox']

    print(f"[{idx+1}/929] Analyzing {row['name']}...")

    district_data = get_poly_coords(
        region_name=district_name,
        bounds=bbox,
        filter="type:way and building=*",
        time_param="2025-08-01",
        path=f"output/thailand_districts/{district_name}"
    )
```

## API Comparison

### Overpass API
- **Purpose**: Query and download OpenStreetMap data
- **Use for**: Getting administrative boundaries, finding regions
- **Endpoint**: https://overpass-api.de/api/interpreter
- **Rate limits**: Be respectful, use timeouts
- **Output**: Raw OSM data (relations, ways, nodes)

### ohsome API
- **Purpose**: Analyze OSM data quality and history
- **Use for**: Complexity analysis, time series, statistics
- **Endpoint**: https://api.ohsome.org/v1
- **Rate limits**: 600 second timeout per request
- **Output**: Aggregated statistics and geometry data

### Nominatim API (Alternative)
- **Purpose**: Geocoding and reverse geocoding
- **Use for**: Finding individual locations by name
- **Limitation**: Not suitable for bulk queries (getting all districts)
- **Endpoint**: https://nominatim.openstreetmap.org
- **Use case**: `get_country_bbox("Thailand")` in your existing code

## Administrative Hierarchy

```
Thailand (admin_level=2)
├── Province 1 (admin_level=4) - 77 total
│   ├── District 1 (admin_level=6) - 929 total
│   │   ├── Sub-district 1 (admin_level=8)
│   │   ├── Sub-district 2 (admin_level=8)
│   │   └── ...
│   ├── District 2 (admin_level=6)
│   └── ...
├── Province 2 (admin_level=4)
└── ...
```

## Tips

1. **Start with full Thailand** to understand overall patterns
2. **Then analyze by district** for detailed regional insights
3. **Consider provinces** (admin_level=4) if 929 districts is too granular
4. **Use chunking** for large districts (some districts are very large)
5. **Cache results** to avoid re-querying Overpass API
6. **Respect rate limits** - add delays between requests if running many queries

## File Locations

- Test script: `test_thailand_districts.py`
- Districts CSV: `countries_polygons/thailand_districts.csv`
- This guide: `THAILAND_DISTRICTS_GUIDE.md`

## References

- Overpass API Documentation: https://overpass-api.de/
- ohsome API Documentation: https://docs.ohsome.org/
- OpenStreetMap Wiki - Thailand: https://wiki.openstreetmap.org/wiki/Thailand
- OSM Administrative Boundaries: https://wiki.openstreetmap.org/wiki/Tag:boundary%3Dadministrative
