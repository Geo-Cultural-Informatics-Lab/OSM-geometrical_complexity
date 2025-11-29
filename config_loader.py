"""
Configuration Loader for OSM Geometrical Complexity Analysis

This module provides functions to load and validate YAML configuration files.
"""

import yaml
from pathlib import Path
from api_helpers import logger


def load_config(config_path):
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Dictionary with configuration parameters or None on error
    """
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        logger.info(f"Loaded configuration from {config_path}")
        return config

    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        return None
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML configuration: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error loading configuration: {str(e)}")
        return None


def validate_config(config):
    """
    Validate configuration parameters.

    Args:
        config: Configuration dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not config:
        return False, "Configuration is empty"

    # Check required top-level keys
    if 'analysis' not in config:
        return False, "Missing required 'analysis' section"

    mode = config['analysis'].get('mode')
    if not mode:
        return False, "Missing 'analysis.mode'"

    valid_modes = ['snapshot', 'time_series', 'batch_countries']
    if mode not in valid_modes:
        return False, f"Invalid analysis mode: {mode}. Must be one of {valid_modes}"

    # Mode-specific validation
    if mode == 'time_series':
        if 'time_series' not in config:
            return False, "time_series mode requires 'time_series' configuration section"

        ts_config = config['time_series']
        required = ['start_year', 'end_year', 'interval']
        for key in required:
            if key not in ts_config:
                return False, f"Missing required time_series parameter: {key}"

        valid_intervals = ['yearly', 'monthly', 'quarterly']
        if ts_config['interval'] not in valid_intervals:
            return False, f"Invalid interval: {ts_config['interval']}. Must be one of {valid_intervals}"

    elif mode == 'batch_countries':
        if 'countries' not in config:
            return False, "batch_countries mode requires 'countries' configuration section"

        # Check for country list
        countries = config.get('countries')
        if isinstance(countries, dict):
            # New format with source specification
            if 'source' in countries and countries['source'] == 'csv':
                if 'csv_path' not in countries:
                    return False, "CSV source requires 'countries.csv_path'"
        elif not isinstance(countries, list) or len(countries) == 0:
            return False, "Countries must be a list of ISO codes or a configuration dict"

    else:  # snapshot or default
        if 'regions' not in config and 'countries' not in config:
            return False, "snapshot mode requires either 'regions' or 'countries' configuration"

    return True, None


def get_default_config():
    """
    Get default configuration template.

    Returns:
        Dictionary with default configuration values
    """
    return {
        'analysis': {
            'mode': 'snapshot',
            'timestamp': '2025-08-01'
        },
        'regions': {
            'test_region': {
                'type': 'city',
                'name': 'London',
                'radius_km': 15
            }
        },
        'time_series': {
            'start_year': 2015,
            'end_year': 2025,
            'interval': 'yearly'
        },
        'countries': {
            'source': 'list',  # or 'csv'
            'iso_codes': ['DEU', 'GBR', 'FRA'],
            'csv_path': './World_Countries.csv',
            'geojson_path': './countries_polygons/World_Countries.geojson'
        },
        'analysis_options': {
            'filter': 'type:way and building=*',
            'chunked_threshold_km2': 5000,
            'include_building_count': True,
            'include_user_count': True,
            'resume': True
        },
        'output': {
            'directory': './results',
            'data_directory': './data',
            'logs_directory': './logs',
            'export_shapefile': True,
            'export_individual_buildings': False,
            'sample_complex_buildings': 10
        },
        'visualization': {
            'create_dashboards': True,
            'create_time_series_plots': True,
            'create_user_correlation_plot': True,
            'create_box_plots': True,
            'create_qualitative_samples': True,
            'dpi': 300
        }
    }


def merge_with_defaults(config):
    """
    Merge user configuration with default values.

    Args:
        config: User configuration dictionary

    Returns:
        Merged configuration with defaults filled in
    """
    defaults = get_default_config()

    def deep_merge(base, override):
        """Recursively merge dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    return deep_merge(defaults, config)


def save_config_template(output_path, config_type='basic'):
    """
    Save configuration template to file.

    Args:
        output_path: Path where to save the template
        config_type: Type of template ('basic', 'time_series', 'batch', 'full')

    Returns:
        Boolean indicating success
    """
    templates = {
        'basic': {
            'analysis': {
                'mode': 'snapshot',
                'timestamp': '2025-08-01'
            },
            'regions': {
                'london': {
                    'type': 'city',
                    'name': 'London',
                    'radius_km': 15
                }
            },
            'output': {
                'directory': './results'
            }
        },
        'time_series': {
            'analysis': {
                'mode': 'time_series'
            },
            'regions': {
                'london': {
                    'type': 'city',
                    'name': 'London',
                    'radius_km': 15
                }
            },
            'time_series': {
                'start_year': 2015,
                'end_year': 2025,
                'interval': 'yearly'
            },
            'output': {
                'directory': './results',
                'data_directory': './data/time_series'
            }
        },
        'batch': {
            'analysis': {
                'mode': 'batch_countries'
            },
            'countries': {
                'source': 'list',
                'iso_codes': ['DEU', 'GBR', 'FRA', 'USA', 'ITA']
            },
            'time_series': {
                'enabled': False
            },
            'output': {
                'directory': './results/batch_countries',
                'export_shapefile': True
            }
        },
        'full': get_default_config()
    }

    config = templates.get(config_type, templates['basic'])

    try:
        with open(output_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, indent=2)

        logger.info(f"Saved {config_type} configuration template to {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error saving configuration template: {str(e)}")
        return False
