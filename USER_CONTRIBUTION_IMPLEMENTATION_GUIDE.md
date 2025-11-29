# User Contribution Analysis - Implementation Guide

## Current Status

### ✅ Completed (Committed: 4e64a17)

**New API Helper Functions in `api_helpers.py`:**

1. **`get_period_user_count(bounds, filter_query, start_time, end_time)`**
   - Returns: Number of unique users active in specific time period (NOT cumulative)
   - Example: Users who contributed in 2020 only
   - Uses: `/v1/users/count` endpoint with period interval

2. **`get_contributions_count(bounds, filter_query, start_time, end_time)`**
   - Returns: Total number of contributions/edits in time period
   - Uses: `/v1/contributions/count` endpoint

3. **`analyze_user_contributions(bounds, filter_query, start_time, end_time, cache_path=None)`**
   - Returns: Detailed user statistics dictionary with:
     - `casual_mappers_count`: Users with 2-10 contributions
     - `regular_mappers_count`: Users with 11-50 contributions
     - `active_mappers_count`: Users with 51-200 contributions
     - `power_mappers_count`: Users with 200+ contributions
     - `contributions_per_user_mean`: Average contributions per user
     - `user_contributions`: Dict of {user_id: count} for distribution plots
   - Downloads geometry data with user metadata
   - **Caches results** to JSON file for fast re-use
   - Slow on first run, instant on subsequent runs

---

## Remaining Implementation Tasks

### 1. Add Configuration Options

**File: `config/defaults.yaml`**

Add new section for user analysis:

```yaml
# User Contribution Analysis (optional, slower but provides detailed insights)
user_analysis:
  enabled: false  # Set to true to enable detailed user contribution analysis
  cache_directory: ./data/user_cache  # Directory for caching user data
```

**Why configurable?**
- Downloading geometry with user metadata is slow for large regions
- Users should opt-in to this detailed analysis
- Caching makes subsequent runs fast

---

### 2. Integrate into Time Series Analysis

**File: `time_series_analysis.py`**

**Location:** In `analyze_region_time_series()` function, when processing each timestamp

**Current code** (around line 200-210):
```python
summary = get_poly_coords(
    region_name=f"{region_name}_{timestamp}",
    bounds=bbox,
    filter=filter,
    time_param=timestamp,
    path=path,
    filename=filename_ts
)
```

**Add after this:**
```python
# Add period-specific user metrics if enabled
if config.get('user_analysis', {}).get('enabled', False):
    logger.info("Collecting detailed user contribution metrics...")

    # Calculate period interval (from previous timestamp to current)
    # For first timestamp, use 1 year before
    if i == 0:
        period_start = calculate_previous_period(timestamp, interval)
    else:
        period_start = timestamps[i-1]
    period_end = timestamp

    # Get period-specific metrics
    from api_helpers import get_period_user_count, get_contributions_count, analyze_user_contributions

    active_users = get_period_user_count(bbox, filter, period_start, period_end)
    total_contribs = get_contributions_count(bbox, filter, period_start, period_end)

    # Get detailed user distribution (cached)
    cache_dir = config.get('user_analysis', {}).get('cache_directory', './data/user_cache')
    cache_file = os.path.join(cache_dir, f"{region_name}_{timestamp}_users.json")

    user_stats = analyze_user_contributions(bbox, filter, period_start, period_end, cache_path=cache_file)

    # Add to result_row
    if summary is not None:
        result_row['active_users_period'] = active_users
        result_row['total_contributions'] = total_contribs
        result_row['contributions_per_user_mean'] = total_contribs / active_users if active_users else 0

        if user_stats:
            result_row['casual_mappers_count'] = user_stats['casual_mappers_count']
            result_row['regular_mappers_count'] = user_stats['regular_mappers_count']
            result_row['active_mappers_count'] = user_stats['active_mappers_count']
            result_row['power_mappers_count'] = user_stats['power_mappers_count']
```

**Helper function to add:**
```python
def calculate_previous_period(timestamp, interval):
    """Calculate the start of the period based on interval."""
    from datetime import datetime, timedelta

    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

    if interval == 'yearly':
        prev = dt.replace(year=dt.year - 1)
    elif interval == 'monthly':
        if dt.month == 1:
            prev = dt.replace(year=dt.year - 1, month=12)
        else:
            prev = dt.replace(month=dt.month - 1)
    elif interval == 'quarterly':
        prev = dt - timedelta(days=90)

    return prev.strftime('%Y-%m-%d')
```

---

### 3. Update CSV Output Columns

**File: `time_series_analysis.py`**

**Current columns:**
- region, bbox, building_count, user_count, convex hull metrics, timestamp, year

**New columns to add** (when user_analysis enabled):
- `active_users_period`: Period-specific active users
- `total_contributions`: Total edits in period
- `contributions_per_user_mean`: Average contributions per user
- `casual_mappers_count`: Users with 2-10 contributions
- `regular_mappers_count`: Users with 11-50 contributions
- `active_mappers_count`: Users with 51-200 contributions
- `power_mappers_count`: Users with 200+ contributions

**Note:** Keep existing `user_count` column for backwards compatibility (cumulative count)

---

### 4. Create Distribution Histogram Visualization

**File: `visualization.py`**

**New function:**

```python
def plot_user_contribution_distribution(user_contributions_dict, region_name, save_path=None):
    """
    Create histogram showing distribution of contributions per user.

    Args:
        user_contributions_dict: Dict of {user_id: contribution_count}
        region_name: Name of region for title
        save_path: Optional path to save plot

    Returns:
        matplotlib figure
    """
    import matplotlib.pyplot as plt
    import numpy as np

    if not user_contributions_dict:
        logger.warning("No user contribution data for histogram")
        return None

    contribution_counts = list(user_contributions_dict.values())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Histogram 1: Full distribution
    ax1.hist(contribution_counts, bins=50, edgecolor='black', alpha=0.7)
    ax1.set_xlabel('Contributions per User', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Number of Users', fontsize=12, fontweight='bold')
    ax1.set_title(f'User Contribution Distribution - {region_name}', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)

    # Add statistics
    mean_contrib = np.mean(contribution_counts)
    median_contrib = np.median(contribution_counts)
    ax1.axvline(mean_contrib, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_contrib:.1f}')
    ax1.axvline(median_contrib, color='green', linestyle='--', linewidth=2, label=f'Median: {median_contrib:.1f}')
    ax1.legend()

    # Histogram 2: Log scale (better for skewed distributions)
    ax2.hist(contribution_counts, bins=50, edgecolor='black', alpha=0.7)
    ax2.set_xlabel('Contributions per User', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Number of Users (log scale)', fontsize=12, fontweight='bold')
    ax2.set_title(f'User Contribution Distribution (Log Scale) - {region_name}', fontsize=14, fontweight='bold')
    ax2.set_yscale('log')
    ax2.grid(True, alpha=0.3)

    # Add category boundaries
    categories = [
        (2, 'Casual (2-10)', 'blue'),
        (11, 'Regular (11-50)', 'orange'),
        (51, 'Active (51-200)', 'green'),
        (200, 'Power (200+)', 'red')
    ]

    for boundary, label, color in categories:
        ax2.axvline(boundary, color=color, linestyle=':', linewidth=1.5, alpha=0.6, label=label)

    ax2.legend(loc='upper right')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"User contribution distribution saved to {save_path}")

    return fig
```

**Add to visualization section in main.py:**

```python
# After time series plots, if user analysis is enabled
if config.get('user_analysis', {}).get('enabled', False):
    for region_name, ts_data in time_series_results.items():
        # Load cached user contribution data for most recent period
        cache_dir = config.get('user_analysis', {}).get('cache_directory', './data/user_cache')
        latest_timestamp = ts_data['timestamp'].iloc[-1]
        cache_file = os.path.join(cache_dir, f"{region_name}_{latest_timestamp}_users.json")

        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                user_stats = json.load(f)

            if 'user_contributions' in user_stats:
                hist_path = output_dir / f"{region_name}_user_distribution.png"
                plot_user_contribution_distribution(
                    user_stats['user_contributions'],
                    region_name.replace('_', ' ').title(),
                    save_path=str(hist_path)
                )
                print(f"✓ User distribution histogram: {hist_path.name}")
```

---

### 5. Update Scatter Plot

**File: `visualization.py`**

**Modify `plot_users_vs_complexity()`** to optionally show contribution metrics:

Add parameter:
```python
def plot_users_vs_complexity(summary_df, save_path=None, show_labels=True,
                            contribution_metric='active_users_period'):
```

Update to use the new column if available:
```python
# Check which user metric to use
user_col = contribution_metric if contribution_metric in df.columns else 'user_count'

scatter = ax.scatter(
    df[user_col],  # Use active_users_period if available
    df['mean_ratio'],
    ...
)

ax.set_xlabel(f'Number of {contribution_metric.replace("_", " ").title()}', ...)
```

---

## Testing Checklist

### Phase 1: API Functions
- [ ] Test `get_period_user_count()` with small region
- [ ] Test `get_contributions_count()` with small region
- [ ] Test `analyze_user_contributions()` with small region
- [ ] Verify cache is created and reused
- [ ] Check user categorization makes sense

### Phase 2: Integration
- [ ] Add config options to defaults.yaml
- [ ] Update time_series_analysis.py
- [ ] Run single region time series with user_analysis enabled
- [ ] Verify new columns appear in CSV output
- [ ] Check cache files are created

### Phase 3: Visualization
- [ ] Add distribution histogram function
- [ ] Test histogram with sample data
- [ ] Update scatter plot to use new metrics
- [ ] Verify both plots are generated

### Phase 4: Full Test
- [ ] Run multi-region time series
- [ ] Check all metrics are collected
- [ ] Verify caching works (second run should be fast)
- [ ] Review output CSV has all columns
- [ ] Check all visualizations are correct

---

## Performance Notes

### First Run (with user_analysis enabled):
- **Slow**: Downloads geometry data for each time period
- Time: ~30-60 seconds per region per time period
- Example: 4 cities × 6 years = 24 API calls = 20-40 minutes

### Subsequent Runs:
- **Fast**: Loads from cache
- Time: <1 second per region per time period
- Example: Same 24 periods = ~30 seconds total

### Recommendation:
- Start with 1-2 cities and 2-3 years
- Test the feature works
- Then enable for full dataset
- Cache persists, so you can add cities incrementally

---

## Example Usage

### Enable in config:
```yaml
# config/user_config.yaml
user_analysis:
  enabled: true
  cache_directory: ./data/user_cache
```

### Run analysis:
```bash
python main.py config/user_config.yaml
```

### Output will include:
1. CSV with new columns
2. Distribution histograms per region
3. Updated correlation plots using period-specific metrics

---

## Files to Modify

1. ✅ `api_helpers.py` - **DONE** (committed)
2. ⏳ `config/defaults.yaml` - Add user_analysis section
3. ⏳ `time_series_analysis.py` - Integrate metric collection
4. ⏳ `visualization.py` - Add histogram function
5. ⏳ `main.py` - Add visualization calls

---

## Questions & Decisions

### Q: What about snapshot mode (non-time-series)?
**A:** Can add later. Focus on time series first since it's more valuable for tracking contributor patterns over time.

### Q: Should we show one-time contributors (1 edit)?
**A:** Currently excluded from categories. Can add as `one_time_contributors_count` if needed.

### Q: How to handle very large regions?
**A:** The `analyze_user_contributions()` function downloads all geometry. For huge regions, may hit API limits or timeout. Could add sampling in future.

### Q: What if cache gets stale?
**A:** User can delete cache files to force refresh. Could add `--force-refresh` flag in future.

---

## Next Session Plan

1. Add config options (5 min)
2. Integrate into time_series_analysis.py (20 min)
3. Add histogram visualization (15 min)
4. Update main.py visualization section (10 min)
5. Test with 1 city, 2 years (15 min)
6. Fix any bugs (10 min)
7. Commit and test full run (10 min)

**Total estimated time:** 1.5 hours

---

## Git Status

**Current branch:** eager-carson (worktree)

**Last commit:** 4e64a17 - Add detailed user contribution analysis functions

**Ready to continue when you are!**
