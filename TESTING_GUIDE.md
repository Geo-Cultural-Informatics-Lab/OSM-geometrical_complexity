# Testing Guide for Country-Scale OSM Analysis

## What's Been Implemented

### ✅ Phase 1 & 2: Spatial Chunking (COMPLETE)
- **New Files:**
  - `chunking_utils.py` - Grid-based bbox splitting
  - Enhanced `api_helpers.py` - Chunk aggregation and status tracking
  - Enhanced `geometry_analysis.py` - Chunked processing function
  - Updated `main.py` - Auto-detection of large regions

### ✅ Phase 3: Time Series Analysis (COMPLETE)
- **New Files:**
  - `time_series_analysis.py` - Temporal analysis functions
  - Enhanced `visualization.py` - Time series plots
  - `example_time_series.py` - Usage examples

---

## Quick Tests

### Test 1: Time Interval Generation (No API calls)
```bash
python example_time_series.py
```
**Expected output:** List of yearly, quarterly, and monthly intervals

### Test 2: Small Region Direct Analysis
```python
python -c "
from bbox_utils import BBOXES
from geometry_analysis import get_poly_coords
from api_helpers import setup_logging

logger = setup_logging()
result = get_poly_coords(
    'heidelberg_test',
    BBOXES['heidelberg'],
    filter='type:way and building=*',
    time_param='2025-10-01',
    path='./test_output',
    filename='test_buildings.csv'
)
print(result)
"
```
**Expected:** Summary statistics for Heidelberg buildings

### Test 3: Chunking System (No API, just logic)
```python
python -c "
from chunking_utils import split_bbox_into_grid, bbox_area_km2, print_chunk_summary

# Simulate large region (London 1000km radius)
bbox = '-14.612632447983527,42.480324490990995,14.324522247983529,60.49834250900901'
print(f'Area: {bbox_area_km2(bbox):.0f} km²')

chunks = split_bbox_into_grid(bbox, chunk_size_km=50)
print_chunk_summary(chunks)
print(f'First chunk: {chunks[0]}')
"
```
**Expected:** Grid info showing ~576 chunks (32×18)

### Test 4: Chunked Analysis (With API calls - SLOW)
**WARNING:** This will make hundreds of API calls. Only run if you want to test for real.

```python
python main.py
```

With `london_1000km` configured, this will:
1. Detect large region (>3.2M km²)
2. Split into ~576 chunks of 50×50 km
3. Process each chunk with progress tracking
4. Save results incrementally
5. Aggregate final summary

**Time estimate:** ~10-30 minutes depending on API speed

---

## Test 5: Time Series (Small region recommended)

Edit `example_time_series.py` and uncomment the small region example:

```python
# Uncomment this in __main__:
example_single_region_time_series()
```

Then run:
```bash
python example_time_series.py
```

**What it does:**
- Analyzes Heidelberg from 2015-2025 (yearly)
- Creates 11 snapshots (2015, 2016, ... 2025)
- Generates time series visualizations
- Saves results to `data/time_series/`

**Time estimate:** ~5-15 minutes (11 API calls + processing)

---

## Files Created by Tests

### After Chunked Analysis:
```
├── results/
│   ├── convex-hull-analysis.csv (all buildings, all chunks)
│   ├── convex-hull-analysis_final_summary.csv (aggregated stats)
├── chunks/
│   ├── convex-hull-analysis_chunk_0_0.csv
│   ├── convex-hull-analysis_chunk_0_1.csv
│   └── ... (one per chunk)
├── .chunk_status_london_1000km.json (resume info)
└── logs/
    └── geometrical_complexity_analysis_london_1000km.log
```

### After Time Series:
```
├── data/
│   └── time_series/
│       ├── heidelberg_time_series_yearly.csv
│       ├── heidelberg_complexity_evolution.png
│       └── heidelberg_dashboard.png
└── logs/
    └── time_series_example.log
```

---

## Resume Capability

If any test is interrupted:

**Chunked analysis:**
```python
# Just re-run - it will resume automatically
python main.py
```

**Time series:**
```python
# Re-run example - skips completed timestamps
python example_time_series.py
```

Status files track progress:
- `.chunk_status_*.json` - Chunked processing progress
- `.time_series_status_*.json` - Time series progress

---

## Expected Performance

### Direct Processing (small regions <5000 km²):
- **Heidelberg:** ~500 buildings, ~2-5 seconds
- **Paris:** ~50K buildings, ~30-60 seconds
- **Beit Shemesh:** ~10K buildings, ~10-20 seconds

### Chunked Processing:
- **Per chunk (50×50 km):** ~10-60 seconds depending on building density
- **London 1000km (576 chunks):** ~1-10 hours total
- **Parallelization potential:** Can process ~3-5 chunks/minute

### Time Series:
- **Yearly (10 years):** 10× single snapshot time
- **Quarterly (3 years, 12 points):** 12× single snapshot time
- **Monthly (1 year, 12 points):** 12× single snapshot time

---

## Troubleshooting

### "Module not found" errors:
```bash
pip install requests pandas geopandas shapely pyproj scipy matplotlib seaborn python-dateutil
```

### "API timeout" or "Connection closed":
- **Solution:** Reduce chunk size (default 50km → 25km)
- Edit `main.py`, line 85: `chunk_size_km=25`

### "Memory error":
- **Solution:** Already using disk-based processing, but can reduce batch size
- Chunking should prevent this for any reasonable region

### Resume not working:
- Check for `.chunk_status_*.json` or `.time_series_status_*.json` files
- Delete status file to force fresh start

---

## What to Look For in Results

### Complexity Metrics:
- **mean_ratio < 0.10:** Very simple buildings (boxes/automated imports)
- **mean_ratio 0.10-0.20:** Simple shapes, basic manual mapping
- **mean_ratio 0.20-0.35:** Moderate complexity, decent mapping
- **mean_ratio > 0.35:** High complexity, detailed manual mapping

### Time Series Trends:
- **Increasing complexity:** Mapping quality improving (manual refinement)
- **Flat/decreasing:** Automated imports or bulk additions
- **Sudden jumps:** Major import events or remapping efforts

### Regional Comparisons:
- Compare historic city centers vs suburbs
- Compare different countries' mapping cultures
- Identify areas needing manual improvement

---

## Next Steps After Testing

Once basic tests work:

1. **Test with your target country**
   ```python
   bbox = get_bbox_by_city("Jerusalem", radius_km=50)
   ```

2. **Run time series for research**
   ```python
   analyze_region_time_series("israel", bbox, start_year=2008, end_year=2025, interval='yearly')
   ```

3. **Compare multiple countries**
   - Create config with multiple regions
   - Use `compare_regions_time_series()`
   - Generate comparative visualizations

4. **Customize analysis**
   - Adjust chunk sizes for performance
   - Modify density estimates for better chunking
   - Add custom filters (e.g., specific building types)
