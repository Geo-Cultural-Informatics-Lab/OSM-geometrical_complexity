# Quick Reference Card

## 🚀 Quick Start

```bash
# Run analysis
python main.py

# Check what's been analyzed
cat geometrical_complexity_analysis.log | tail -50
```

---

## 📊 Current Status

**Last Run:** October 15, 2025
**Regions Analyzed:** London (15km, 30km), Jerusalem (15km, 30km)
**Total Buildings:** 2,451,968 polygons
**Performance:** 18-25K features/second ⭐⭐⭐⭐

**Key Finding:** Current test regions show 96-97% efficiency (very simple buildings)
**Next Step:** Validate with high-quality mapped areas (historic city centers)

---

## 📁 File Structure

```
complex-geometry-scale/
├── api_helpers.py           # API calls, logging, file ops
├── geometry_analysis.py     # Analysis functions (main module)
├── bbox_utils.py            # Bounding box generation
├── visualization.py         # Plotting functions
├── main.py                  # Main script
├── functions.py             # Legacy (backward compat)
│
├── convex-hull-analysis.csv         # Per-building results
├── convex-hull-analysis.csv_summary.csv  # Aggregated stats
│
├── completeness_dashboard_completeness.png      # 4-panel metrics
├── completeness_dashboard_area_comparison.png   # 2-panel areas
│
├── CLAUDE.md                        # Project overview (START HERE)
├── SESSION_SUMMARY_2025-10-15.md   # This session's work
├── PERFORMANCE_ANALYSIS.md         # Detailed performance
├── VISUALIZATION_IMPROVEMENTS.md   # Plot interpretation
└── REFACTORING_SUMMARY.md         # Module structure guide
```

---

## 💻 Common Operations

### Generate Bounding Box
```python
from bbox_utils import get_bbox_by_city, bbox_by_location

# By city name
bbox = get_bbox_by_city("Munich", radius_km=20)

# By coordinates
bbox = bbox_by_location(48.1351, 11.5820, radius_km=15)

# Use predefined
from bbox_utils import BBOXES
paris_bbox = BBOXES['paris']
```

### Run Analysis
```python
from geometry_analysis import get_poly_coords

summary = get_poly_coords(
    region_name="Munich",
    bounds=bbox,
    filter="type:way and building=*",
    time_param="2025-08-01",
    path="./",
    filename="convex-hull-analysis.csv"
)
```

### Visualize Results
```python
from visualization import plot_summary_dashboard
import pandas as pd

summaries = []  # List of DataFrames from get_poly_coords()
combined = pd.concat(summaries, ignore_index=True)

plot_summary_dashboard(summaries, save_path="dashboard.png")
```

---

## 🎯 Complexity Interpretation

| Ratio | Percentage | Interpretation | Example |
|-------|------------|----------------|---------|
| 0.00-0.10 | 90-100% | Very simple, box-like | Automated imports |
| 0.10-0.20 | 80-90% | Basic shapes | Standard mapping |
| 0.20-0.35 | 65-80% | Moderate complexity | Manual refinement |
| 0.35-0.50 | 50-65% | High complexity | Detailed mapping |
| 0.50+ | <50% | Very complex | Historic buildings |

**Formula:** `ratio = 1 - (actual_area / convex_hull_area)`

**Colors in plots:**
- 🟢 Green (<90%): Complex, good quality
- 🟠 Orange (90-95%): Moderate
- 🔴 Red (>95%): Simple, box-like

---

## ⚡ Performance Quick Stats

| Region | Buildings | Time | Speed | Rating |
|--------|-----------|------|-------|--------|
| Small (75K) | 75,000 | 6s | 24,560/s | ⭐⭐⭐⭐⭐ |
| Medium (122K) | 122,000 | 11s | 18,559/s | ⭐⭐⭐⭐ |
| Large (822K) | 822,000 | 68s | 20,881/s | ⭐⭐⭐⭐ |
| XL (1.4M) | 1,400,000 | 127s | 18,269/s | ⭐⭐⭐⭐ |

**Bottleneck:** Data preparation (43.6% of time)
**Optimization Potential:** 30-50% speedup possible

---

## 🔧 Troubleshooting

### "Time parameter not within timeframe"
Ohsome API data only up to 2025-08-20. Use `time_param="2025-08-01"`.

### Slow performance
- Datasets >1M buildings: 100-150s normal
- Check log for API call times
- Network issues? Retry API calls

### Very low complexity scores
- Expected for suburban/automated imports
- Test historic city centers for validation
- Check: Venice, Prague, Old Jerusalem

### Memory errors
- Estimate: ~2MB per 1000 buildings
- Split large regions into smaller chunks
- Use `del` to free memory between runs

---

## 📋 Next Session TODO

**Priority 1: Metric Validation**
- [ ] Test Venice (expect high complexity)
- [ ] Test Prague Old Town (expect high)
- [ ] Test US suburbs (expect low)
- [ ] Compare results, validate metric works

**Priority 2: Performance**
- [ ] Implement `gpd.from_features()` (20-30% faster)
- [ ] Switch to `orjson` (10-15% faster)
- [ ] Add progress bars

**Priority 3: Features**
- [ ] Distribution plots (histograms)
- [ ] Statistical significance tests
- [ ] Type hints + unit tests
- [ ] API response caching

---

## 🐛 Known Issues

1. **Ohsome data cutoff:** August 20, 2025
2. **Low complexity in test regions:** Need validation with diverse areas
3. **JSON parsing slow:** For >800K buildings, parse time > network time
4. **No caching:** Repeated queries hit API every time

---

## 📞 Getting Help

**Documentation:**
- `CLAUDE.md` - Complete project overview
- `REFACTORING_SUMMARY.md` - Module structure
- `PERFORMANCE_ANALYSIS.md` - Performance details
- `VISUALIZATION_IMPROVEMENTS.md` - Plot guide

**Logs:**
```bash
# View recent activity
tail -100 geometrical_complexity_analysis.log

# Search for errors
grep ERROR geometrical_complexity_analysis.log

# Check API timing
grep "API call" geometrical_complexity_analysis.log
```

**Check results:**
```bash
# View summary stats
head convex-hull-analysis.csv_summary.csv

# Count buildings analyzed
wc -l convex-hull-analysis.csv

# View latest images
ls -lt *.png | head
```

---

## 🧪 Testing Checklist

Before production use:
- [ ] Validate metric with high-quality areas
- [ ] Test error handling (invalid bbox, API timeout)
- [ ] Verify results match manual inspection
- [ ] Document typical values for different region types
- [ ] Add unit tests for core functions

---

## ⚙️ Configuration

**Main settings in `main.py`:**
```python
# Regions to analyze
comparison_regions = {
    'london_15km': get_bbox_by_city("London", radius_km=15),
    'jerusalem_15km': get_bbox_by_city("Jerusalem", radius_km=15),
}

# Output settings
output_dir = Path(__file__).parent
output_file = "convex-hull-analysis.csv"

# Filter and time
filter = "type:way and building=*"
time_param = "2025-08-01"
```

**Logging level:**
```python
# In api_helpers.py
setup_logging(log_level=logging.DEBUG, console_level=logging.INFO)
```

---

## 📈 Sample Workflow

```python
# 1. Import modules
from geometry_analysis import get_poly_coords
from bbox_utils import get_bbox_by_city
from visualization import plot_summary_dashboard, print_completeness_summary
import pandas as pd

# 2. Define regions
regions = {
    'venice': get_bbox_by_city("Venice", radius_km=10),
    'phoenix': get_bbox_by_city("Phoenix", radius_km=10),
}

# 3. Analyze
summaries = []
for name, bbox in regions.items():
    print(f"Analyzing {name}...")
    summary = get_poly_coords(name, bbox, time_param="2025-08-01")
    summaries.append(summary)

# 4. Visualize
combined = pd.concat(summaries, ignore_index=True)
plot_summary_dashboard(summaries, save_path="comparison.png")
print_completeness_summary(combined)

# 5. Review results
print(combined[['region', 'mean_ratio', 'mean_area', 'multipolygon_ratio']])
```

---

**Last Updated:** October 15, 2025
**Version:** 1.0 (Post-refactoring)
**Status:** ✅ Production-ready, needs validation
