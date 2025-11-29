# Quick Start Guide

## Installation Complete! 🎉

All features have been implemented and integrated into `main.py`. The system is now production-ready.

---

## Quick Test (5 minutes)

### Step 1: Create Example Configuration

```bash
python main.py --create-config batch
```

This creates `config_batch.yaml` with example settings.

### Step 2: Edit Configuration

Open `config_batch.yaml` and modify the country list to something small for testing:

```yaml
countries:
  source: list
  iso_codes:
    - LUX  # Luxembourg (small country, fast to process)
    - MLT  # Malta (small country)
  geojson_path: ./countries_polygons/World_Countries.geojson
```

### Step 3: Run Analysis

```bash
python main.py --config config_batch.yaml
```

**Expected output:**
```
Loading configuration from: config_batch.yaml

================================================================================
OSM GEOMETRICAL COMPLEXITY ANALYSIS
Mode: BATCH_COUNTRIES
Output directory: results/batch_countries
================================================================================

BATCH COUNTRY ANALYSIS MODE
================================================================================

Processing countries: LUX, MLT
Total countries to process: 2
...
```

### Step 4: Check Results

Look in `results/batch_countries/`:
- `batch_countries_summary.csv` - Summary statistics
- `batch_dashboard.png` - Visualization dashboard
- `user_vs_complexity.png` - User correlation plot
- `shapefiles/` - GIS files (.shp, .geojson)

---

## Available Commands

### Create Configurations
```bash
# Different config types
python main.py --create-config basic        # Simple snapshot
python main.py --create-config time_series  # Time series analysis
python main.py --create-config batch        # Batch countries
python main.py --create-config full         # All options
```

### Run Analysis
```bash
# Use any config file
python main.py --config config.yaml
python main.py --config config_templates/example_snapshot.yaml
python main.py --config my_custom_config.yaml
```

---

## Example Workflows

### Workflow 1: Analyze 2-3 Cities (Snapshot)

**Create config:**
```bash
python main.py --create-config basic
# Edit config_basic.yaml
```

**Edit to:**
```yaml
analysis:
  mode: snapshot
  timestamp: "2025-08-01"

regions:
  london:
    type: city
    name: London
    radius_km: 10

  paris:
    type: city
    name: Paris
    radius_km: 10
```

**Run:**
```bash
python main.py --config config_basic.yaml
```

---

### Workflow 2: Time Series for One Region

**Create config:**
```bash
python main.py --create-config time_series
# Edit config_time_series.yaml
```

**Edit to:**
```yaml
analysis:
  mode: time_series

regions:
  heidelberg:
    type: city
    name: Heidelberg
    radius_km: 15

time_series:
  start_year: 2020
  end_year: 2025
  interval: yearly
```

**Run:**
```bash
python main.py --config config_time_series.yaml
```

---

### Workflow 3: Batch Countries

**Use existing template:**
```bash
# Edit config_templates/example_batch_countries.yaml
# Change iso_codes to desired countries
python main.py --config config_templates/example_batch_countries.yaml
```

---

## Output Structure

After running analysis, you'll get:

```
results/
├── batch_countries_summary.csv          # Summary statistics
├── batch_dashboard_completeness.png     # Complexity metrics
├── batch_dashboard_area_comparison.png  # Area analysis
├── user_vs_complexity.png               # User correlation (if enabled)
├── shapefiles/
│   ├── batch_countries_summary.shp      # Shapefile with boundaries
│   ├── batch_countries_summary.geojson  # Web-compatible GeoJSON
│   └── ...
└── [individual country files]

data/
├── time_series/                         # Time series data
│   └── [timestamp files]
└── ...

logs/
├── main_analysis.log                    # Main log
├── analysis_[region].log                # Per-region logs
└── batch_country_analysis.log           # Batch processing log
```

---

## Configuration Options Reference

### Analysis Modes
- `snapshot` - Single point in time
- `time_series` - Evolution over time
- `batch_countries` - Multiple countries

### Region Types
```yaml
regions:
  # By city name
  my_city:
    type: city
    name: "Berlin"
    radius_km: 20

  # By bbox
  my_area:
    type: bbox
    bbox: "13.3,52.5,13.5,52.6"  # min_lon,min_lat,max_lon,max_lat

  # Predefined
  my_predefined:
    type: predefined
    name: heidelberg  # From BBOXES in bbox_utils.py
```

### Country Sources
```yaml
countries:
  # Option 1: Manual list
  source: list
  iso_codes: [DEU, FRA, GBR]

  # Option 2: Load from CSV
  source: csv
  csv_path: ./World_Countries.csv
  iso_filter: [USA, CAN, MEX]  # Optional filter

  geojson_path: ./countries_polygons/World_Countries.geojson
```

---

## Troubleshooting

### "Module not found: config_loader"
**Fix:** Make sure all new Python files are in the same directory as `main.py`

### "Configuration file not found"
**Fix:** Use `--create-config` to generate a template first

### "GeoJSON file not found"
**Fix:** Ensure `countries_polygons/World_Countries.geojson` exists

### API timeout for large countries
**Fix:** The system automatically uses chunking for large areas. Check logs for progress.

### "No countries processed"
**Fix:** Check that ISO codes match exactly (case-sensitive). Use 3-letter codes like 'DEU', not 'Germany'.

---

## Performance Guidelines

### Small Test (< 5 minutes)
- 1-2 small countries (LUX, MLT, BEL)
- Single city with 10km radius
- Snapshot mode only

### Medium Test (30-60 minutes)
- 3-5 medium countries (NLD, BEL, CHE, AUT)
- 2-3 cities with time series (yearly, 2020-2025)

### Large Run (hours)
- 10+ countries
- Large countries (DEU, FRA, GBR, USA)
- Monthly time series over 5+ years

**Note:** Use `resume: true` in config for large runs. If interrupted, simply run again with the same config.

---

## Features Summary

✅ **Actual building counts** from API (not estimates)
✅ **User/contributor tracking** with correlation analysis
✅ **Country batch processing** from CSV or manual list
✅ **Time series analysis** (yearly/monthly/quarterly)
✅ **YAML configuration** - easy to customize
✅ **Box plot visualizations** - see distribution
✅ **Shapefile/GeoJSON export** - use in QGIS/ArcGIS
✅ **Resume capability** - continue interrupted runs
✅ **Automatic chunking** - handles large regions
✅ **Comprehensive logging** - track progress

---

## Next Steps

1. **Test with small dataset** (recommended above)
2. **Review output visualizations**
3. **Load shapefiles in QGIS** to explore spatially
4. **Run larger analysis** for your research
5. **Analyze correlations** between users and complexity

For detailed documentation, see:
- `README.md` - User guide
- `COMPLETED_IMPLEMENTATION_SUMMARY.md` - Technical details
- `IMPLEMENTATION_STATUS.md` - What was implemented

---

## Getting Help

All features are documented inline in the code. To understand any function:
```python
help(get_poly_coords)
help(analyze_countries_batch)
help(plot_users_vs_complexity)
```

Check logs for detailed execution information:
```
logs/main_analysis.log
logs/batch_country_analysis.log
```

Happy analyzing! 🗺️📊
