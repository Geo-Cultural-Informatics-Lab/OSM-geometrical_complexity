"""
Configuration Loader for OSM Geometrical Complexity Analysis

This module provides functions to load and validate YAML configuration files.
Uses a layered configuration approach:
1. System defaults (config/defaults.yaml)
2. User config (config/user_config.yaml or provided path)
"""

import yaml
from pathlib import Path
from api_helpers import logger


def load_yaml_file(file_path):
    """
    Load a YAML file and return its contents.

    Args:
        file_path: Path to YAML file

    Returns:
        Dictionary with file contents or None on error
    """
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {file_path}")
        return None
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error loading file: {str(e)}")
        return None


def load_defaults():
    """
    Load system defaults from config/defaults.yaml

    Returns:
        Dictionary with default configuration values
    """
    defaults_path = Path(__file__).parent / 'config' / 'defaults.yaml'

    if not defaults_path.exists():
        logger.warning(f"Defaults file not found at {defaults_path}, using minimal defaults")
        return {
            'analysis': {'mode': 'snapshot', 'timestamp': '2025-08-01'},
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
                'logs_directory': './logs'
            }
        }

    defaults = load_yaml_file(defaults_path)
    if defaults:
        logger.info(f"Loaded system defaults from {defaults_path}")
    return defaults or {}


def load_config(config_path=None):
    """
    Load configuration by layering user config over system defaults.

    Args:
        config_path: Path to user YAML configuration file
                    If None, tries config/user_config.yaml

    Returns:
        Dictionary with merged configuration parameters
    """
    # Load system defaults first
    config = load_defaults()

    # Determine user config path
    if config_path is None:
        user_config_path = Path(__file__).parent / 'config' / 'user_config.yaml'
        if not user_config_path.exists():
            logger.warning("No user config found, using defaults only")
            logger.info("Create config/user_config.yaml to customize settings")
            return config
    else:
        user_config_path = Path(config_path)

    # Load and merge user config
    user_config = load_yaml_file(user_config_path)
    if user_config:
        logger.info(f"Loaded user configuration from {user_config_path}")
        config = merge_configs(config, user_config)

    return config


def merge_configs(base, override):
    """
    Recursively merge two configuration dictionaries.
    Override values take precedence over base values.

    Args:
        base: Base configuration dictionary
        override: Configuration to overlay on top

    Returns:
        Merged configuration dictionary
    """
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override

    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value

    return result


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

    else:  # snapshot mode
        if 'regions' not in config and 'countries' not in config:
            return False, "snapshot mode requires either 'regions' or 'countries' configuration"

    return True, None


# Deprecated functions kept for backwards compatibility
def get_default_config():
    """
    DEPRECATED: Use load_defaults() instead.
    Get default configuration template.

    Returns:
        Dictionary with default configuration values
    """
    logger.warning("get_default_config() is deprecated, use load_defaults() instead")
    return load_defaults()


def merge_with_defaults(config):
    """
    DEPRECATED: Use merge_configs(load_defaults(), config) instead.
    Merge user configuration with default values.

    Args:
        config: User configuration dictionary

    Returns:
        Merged configuration with defaults filled in
    """
    logger.warning("merge_with_defaults() is deprecated, use load_config() instead")
    return merge_configs(load_defaults(), config)


def save_config_template(output_path, config_type='basic'):
    """
    Save configuration template to file.

    Args:
        output_path: Path where to save the template
        config_type: Type of template ('basic', 'time_series', 'batch', 'full')

    Returns:
        Boolean indicating success
    """
    # Use the example user config as the template
    example_path = Path(__file__).parent / 'config' / 'user_config.example.yaml'

    if not example_path.exists():
        logger.error(f"Example config not found at {example_path}")
        return False

    try:
        # Just copy the example file
        import shutil
        shutil.copy(example_path, output_path)
        logger.info(f"Saved configuration template to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving configuration template: {str(e)}")
        return False
