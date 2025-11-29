# Configuration System Migration Guide

## What Changed

The configuration system has been refactored to eliminate hardcoded values and improve user experience.

### Before
- Hardcoded "London" as default city in multiple places in Python code
- Configuration defaults scattered throughout `config_loader.py`
- Difficult to understand what settings were being used
- Config templates in `config_templates/` directory

### After
- All defaults in `config/defaults.yaml` (version controlled)
- User settings in `config/user_config.yaml` (gitignored)
- Clear separation between system defaults and user preferences
- Test configs in `config/test_configs/`

## New Directory Structure

```
config/
├── defaults.yaml              # System defaults (DO NOT EDIT)
├── user_config.example.yaml   # Example user config (copy this)
├── user_config.yaml           # Your personal config (gitignored)
└── test_configs/              # Test configurations
    ├── basic_config.yaml
    ├── test_single_city.yaml
    └── ...
```

## Quick Start

### 1. Create Your User Config

```bash
cp config/user_config.example.yaml config/user_config.yaml
```

### 2. Edit Your Settings

Edit `config/user_config.yaml`:

```yaml
analysis:
  mode: snapshot

regions:
  my_city:
    type: city
    name: Heidelberg, Germany  # Your city here
    radius_km: 15
```

### 3. Run Analysis

```bash
# Uses config/user_config.yaml automatically
python main.py

# Or specify a config file
python main.py config/user_config.yaml
```

## Key Changes

### No More Hardcoded Locations

Previously, changing the default city required editing Python code in multiple places:
- `config_loader.py:116` - get_default_config()
- `config_loader.py:202` - basic template
- `config_loader.py:217` - time_series template

Now, no locations are hardcoded. All settings come from YAML files.

### System Defaults

All system defaults are now in `config/defaults.yaml`:
- Analysis options (filters, thresholds)
- Output directories
- Visualization settings
- Time series defaults
- Country analysis defaults

### User Config Override

Your `config/user_config.yaml` only needs to specify what you want to change:

```yaml
# Minimal config - everything else uses defaults
analysis:
  mode: snapshot

regions:
  my_region:
    type: city
    name: Your City
    radius_km: 15
```

## Migration Steps for Existing Configs

If you have existing config files:

1. Move them to `config/test_configs/` if they're test configs
2. Copy values you care about to `config/user_config.yaml`
3. Delete old `config.yaml` files (they're replaced by the new system)

## Backwards Compatibility

Old functions are deprecated but still work:
- `get_default_config()` - use `load_defaults()` instead
- `merge_with_defaults()` - use `load_config()` instead

## Benefits

1. **No hardcoded values** - All configuration in YAML files
2. **Clear defaults** - See all system defaults in one file
3. **Simple user config** - Only specify what you want to change
4. **Version control friendly** - User config is gitignored
5. **Better UX** - Easier to understand and use

## Troubleshooting

### "No regions defined" error

Make sure your user config has a `regions` section:

```yaml
regions:
  my_city:
    type: city
    name: Your City
    radius_km: 15
```

### Changes not taking effect

1. Check you're editing `config/user_config.yaml` (not the example)
2. Verify the file is valid YAML (proper indentation)
3. Check the logs for which config file was loaded

### Want to see all settings

Run with validation to see merged config:

```python
from config_loader import load_config
import json

config = load_config('config/user_config.yaml')
print(json.dumps(config, indent=2))
```
