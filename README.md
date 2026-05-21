# OSM Geometrical Complexity Analysis

Measures geometric complexity of OpenStreetMap building and road features using convex hull ratios, tracking how feature shapes evolve over time across countries. 

**Authors:** Yair Grinberger (PI), Tomer Vagenfeld, Alexander Shapira
**Affiliation:** Department of Spatial Scinece, The Hebrew University of Jerusalem

## Installation

```bash
git clone https://github.com/Geo-Cultural-Informatics-Lab/OSM-geometrical_complexity.git
cd OSM-geometrical_complexity
pip install -r requirements.txt
```

Or install as a package (required by [OSM-report](https://github.com/Geo-Cultural-Informatics-Lab/OSM-report)):
```bash
pip install -e .
```

**Requirements:** Python 3.7+, see `requirements.txt` for full dependency list.

## Quick Start

1. Create a configuration file `config.yaml`:

```yaml
analysis:
  mode: time_series          # snapshot, time_series, or batch_countries
  entity_type: building

regions:
  bangkok:
    type: city
    name: Bangkok
    radius_km: 30

time_series:
  start_year: 2015
  end_year: 2025
  interval: yearly

output:
  include_building_count: true
  export_shapefile: true
```

2. Run:
```bash
python main.py --config config.yaml
```

## Complexity Metric

**Convex hull ratio:** `complexity = 1 - (actual_area / convex_hull_area)`

| Value | Interpretation |
|-------|---------------|
| 0.00 -- 0.10 | Very simple shapes (box/automated mapping) |
| 0.10 -- 0.20 | Simple shapes (basic manual mapping) |
| 0.20 -- 0.35 | Moderate complexity (decent manual mapping) |
| 0.35 -- 0.50 | High complexity (detailed manual mapping) |
| 0.50+ | Very high complexity (excellent detail) |

A value near 0 means the feature is nearly convex (rectangular buildings); near 1 means highly irregular shapes with concavities.

## Analysis Modes

- **Snapshot**: Analyze at a single point in time
- **Time series**: Track complexity evolution over years/months
- **Batch countries**: Process multiple countries from a list

## Output

- **CSV**: Summary statistics and per-feature data
- **Shapefiles**: Individual features and country aggregates (optional)
- **Visualizations**: Dashboards, time series plots, box plots (optional)

## API

Uses the [Ohsome API](https://api.ohsome.org/) for OSM data extraction. No API key required.

## License

MIT License. See [LICENSE](LICENSE).

## Citation

> Grinberger, Y., Vagenfeld, T., & Shapira, A. (2026). *Impacts of Corporate Editors on Collective Intelligence in OpenStreetMap*. Department of Geography, The Hebrew University of Jerusalem. Commissioned by the Digital Infrastructure Insights Fund (D//F).
