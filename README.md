# OSM Geometrical Complexity Analysis

Analyze OpenStreetMap building geometry completeness using convex hull ratios to detect automated vs. manual mapping quality.

## Features

- **Building Complexity Metrics**: Analyze convex hull ratios, multipolygon counts, inner rings
- **Country-Scale Analysis**: Process entire countries with automatic spatial chunking
- **Time Series Analysis**: Track mapping quality evolution over time
- **Batch Processing**: Analyze multiple countries from CSV list
- **User/Contributor Tracking**: Correlate mapping quality with mapper activity
- **Rich Visualizations**: Dashboards, time series plots, box plots, qualitative samples
- **GIS Export**: Export results as Shapefiles and GeoJSON

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Basic Usage

1. **Create a configuration file** `config.yaml`:

```yaml
analysis:
  mode: snapshot  # or time_series, batch_countries

regions:
  london_30km:
    type: city
    name: London
    radius_km: 30

time_series:
  start_year: 2015
  end_year: 2025
  interval: yearly

output:
  include_building_count: true
  include_user_count: true
  export_shapefile: true
```

2. **Run analysis**:

```bash
python main.py --config config.yaml
```

## Analysis Modes

### Snapshot Analysis
Analyze regions at a single point in time:
```yaml
analysis:
  mode: snapshot
  timestamp: "2025-01-01"
```

### Time Series Analysis
Track complexity evolution over time:
```yaml
analysis:
  mode: time_series
time_series:
  start_year: 2015
  end_year: 2025
  interval: yearly  # or monthly, quarterly
```

### Batch Country Analysis
Process multiple countries:
```yaml
analysis:
  mode: batch_countries
countries:
  - DEU  # ISO code
  - FRA
  - GBR
```

## Output Files

- **CSV**: Summary statistics and detailed building data
- **Shapefiles**: `*_buildings.shp` (individual buildings), `*_summary.shp` (country aggregates)
- **Visualizations**: PNG dashboards, time series plots, box plots
- **Logs**: Detailed processing logs in `logs/` directory

## Complexity Metrics

**Convex Hull Ratio**: `1 - (actual_area / convex_hull_area)`
- **0.00-0.10**: Very simple (likely automated/box mapping)
- **0.10-0.20**: Simple shapes (basic manual mapping)
- **0.20-0.35**: Moderate complexity (decent manual mapping)
- **0.35-0.50**: High complexity (detailed manual mapping)
- **0.50+**: Very high complexity (excellent detailed mapping)

## Project Structure

```
├── api_helpers.py           # API calls and logging
├── geometry_analysis.py     # Core analysis functions
├── bbox_utils.py            # Bounding box generation
├── chunking_utils.py        # Spatial chunking for large regions
├── time_series_analysis.py  # Time series processing
├── visualization.py         # Plotting functions
├── qualitative_viz.py       # Individual polygon visualization
├── batch_country_analysis.py # Country batch processing
├── config_loader.py         # YAML configuration parsing
├── main.py                  # Main entry point
├── config.yaml              # User configuration
└── config_templates/        # Example configurations
```

## Performance

- **Processing Speed**: 18,000-25,000 features/second
- **Scalability**: Linear O(n) with automatic chunking for large regions
- **Country-Scale**: Handles entire countries with resume capability

## API

Uses the [Ohsome API](https://api.ohsome.org/) for OSM data extraction:
- Element counts, areas, lengths
- Full geometry retrieval
- User/contributor statistics
- Time-based queries

## License

See LICENSE file for details.

## Citation

If you use this tool in research, please cite accordingly.
