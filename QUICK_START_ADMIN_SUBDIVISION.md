# Quick Start: Admin Subdivision Analysis

## Run Thailand Districts in 2 Steps

### Step 1: Run Analysis
```bash
python main.py --config config/thailand_districts_example.yaml
```

### Step 2: Check Results
```bash
# View combined data
cat results/thailand_districts/th/th_admin_level_6_combined.csv

# View summary
cat results/thailand_districts/th/th_admin_level_6_summary.json

# List all districts
ls results/thailand_districts/th/admin_6/
```

## Expected Output

```
results/thailand_districts/
└── th/
    ├── admin_6/
    │   ├── bangkok/
    │   ├── chiang_mai/
    │   └── ... (927 more)
    ├── th_admin_level_6_boundaries.csv (929 districts)
    ├── th_admin_level_6_combined.csv (all buildings)
    └── th_admin_level_6_summary.json
```

## Customize for Different Country

Edit `config/thailand_districts_example.yaml`:

```yaml
countries:
  iso_codes: ['DE']  # Change TH to DE for Germany
  admin_level: 6     # Keep 6 for districts
```

Run:
```bash
python main.py --config config/thailand_districts_example.yaml
```

## Customize Admin Level

**For provinces instead of districts:**

```yaml
countries:
  iso_codes: ['TH']
  admin_level: 4  # 4 = provinces (77 regions)
```

## Monitor Progress

```bash
# Watch log file
tail -f results/thailand_districts/th/th_admin_level_6_analysis.log

# Count completed districts
ls results/thailand_districts/th/admin_6/ | wc -l
```

## Performance

**Thailand Districts (929 regions)**:
- First run: ~3-15 hours
- Subsequent runs with resume: continues from last completed

**Thailand Provinces (77 regions)**:
- First run: ~1-3 hours
- Faster but less granular

## Get District Names & Bboxes

```bash
# Query and save all districts
python test_thailand_districts.py

# Output: countries_polygons/thailand_districts.csv
```

## Compare: With vs Without Admin Subdivision

### Without (Traditional)
```yaml
countries:
  iso_codes: ['TH']
  subdivide_by_admin_level: false  # or omit
```
→ Single output: `th_buildings.csv`

### With Admin Subdivision
```yaml
countries:
  iso_codes: ['TH']
  subdivide_by_admin_level: true
  admin_level: 6
```
→ Per-district outputs + combined: `admin_6/bangkok/`, `admin_6/chiang_mai/`, etc.

## Troubleshooting

**"No boundaries found"**
- Check ISO code is correct
- Verify admin level exists for country

**Timeout errors**
- Increase: `overpass_timeout: 300`

**Slow performance**
- Use provinces (admin_level=4) instead
- Verify cache is enabled: `cache_boundaries: true`

## Full Documentation

- `ADMIN_SUBDIVISION_GUIDE.md` - Complete guide
- `ADMIN_SUBDIVISION_SUMMARY.md` - Implementation summary
- `THAILAND_DISTRICTS_GUIDE.md` - Thailand-specific guide
