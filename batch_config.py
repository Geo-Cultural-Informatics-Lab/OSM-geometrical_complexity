"""
Batch Configuration Management for OSM Analysis

This module provides dataclasses and functions for loading and validating
YAML/JSON batch configuration files.
"""

import yaml
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path
from api_helpers import logger


# ============================================================================
# Configuration Dataclasses
# ============================================================================

@dataclass
class RegionConfig:
    """Configuration for a single region/country."""
    name: str
    type: str  # 'country', 'city', 'coordinates', 'bbox', 'file'

    # Type-specific fields
    country: Optional[str] = None
    city: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    radius_km: float = 15
    bbox: Optional[str] = None

    # Optional metadata
    notes: Optional[str] = None
    priority: int = 1

    def __post_init__(self):
        """Validate region configuration."""
        if self.type not in ['country', 'city', 'coordinates', 'bbox', 'file']:
            raise ValueError(f"Invalid region type: {self.type}")

        # Validate required fields based on type
        if self.type == 'country' and not self.country:
            raise ValueError(f"Region '{self.name}' type 'country' requires 'country' field")
        elif self.type == 'city' and not self.city:
            raise ValueError(f"Region '{self.name}' type 'city' requires 'city' field")
        elif self.type == 'coordinates' and (self.lat is None or self.lon is None):
            raise ValueError(f"Region '{self.name}' type 'coordinates' requires 'lat' and 'lon' fields")
        elif self.type == 'bbox' and not self.bbox:
            raise ValueError(f"Region '{self.name}' type 'bbox' requires 'bbox' field")


@dataclass
class SnapshotConfig:
    """Configuration for snapshot analysis."""
    timestamp: str = "2025-08-01"


@dataclass
class TimeSeriesConfig:
    """Configuration for time series analysis."""
    start_year: int = 2015
    end_year: int = 2025
    interval: str = 'yearly'  # 'yearly', 'quarterly', 'monthly'

    def __post_init__(self):
        """Validate time series configuration."""
        if self.interval not in ['yearly', 'quarterly', 'monthly']:
            raise ValueError(f"Invalid interval: {self.interval}. Must be 'yearly', 'quarterly', or 'monthly'")
        if self.start_year >= self.end_year:
            raise ValueError(f"start_year ({self.start_year}) must be less than end_year ({self.end_year})")


@dataclass
class AnalysisConfig:
    """Configuration for analysis settings."""
    type: str  # 'snapshot' or 'time_series'
    snapshot: Optional[SnapshotConfig] = None
    time_series: Optional[TimeSeriesConfig] = None

    def __post_init__(self):
        """Validate analysis configuration."""
        if self.type not in ['snapshot', 'time_series']:
            raise ValueError(f"Invalid analysis type: {self.type}")

        # Ensure appropriate config is provided
        if self.type == 'snapshot' and self.snapshot is None:
            self.snapshot = SnapshotConfig()
        elif self.type == 'time_series' and self.time_series is None:
            self.time_series = TimeSeriesConfig()


@dataclass
class ProcessingConfig:
    """Configuration for processing options."""
    filter: str = "type:way and building=*"
    use_adaptive_chunking: bool = True
    chunk_size_km: int = 50
    max_features_per_chunk: int = 50000
    building_density: int = 2000
    resume: bool = True
    cleanup_chunks: bool = True


@dataclass
class OutputConfig:
    """Configuration for output settings."""
    base_dir: str = "./results"
    structure: str = "by_analysis_type"  # 'by_analysis_type' or 'by_region'
    generate_plots: bool = True
    generate_reports: bool = False
    report_format: str = "markdown"  # 'markdown', 'html', 'pdf'
    log_level: str = "INFO"  # 'DEBUG', 'INFO', 'WARNING', 'ERROR'


@dataclass
class AdvancedConfig:
    """Configuration for advanced options."""
    parallel_processing: bool = False
    max_workers: int = 2
    api_timeout: int = 300
    retry_failed: bool = True
    max_retries: int = 3


@dataclass
class BatchConfig:
    """Complete batch analysis configuration."""
    analysis: AnalysisConfig
    regions: List[RegionConfig] = field(default_factory=list)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    advanced: AdvancedConfig = field(default_factory=AdvancedConfig)

    # Optional metadata
    name: Optional[str] = None
    description: Optional[str] = None
    version: str = "1.0"


# ============================================================================
# Configuration Loading Functions
# ============================================================================

def load_yaml_config(yaml_path: str) -> Dict[str, Any]:
    """
    Load YAML configuration file.

    Args:
        yaml_path: Path to YAML file

    Returns:
        Dict with configuration data

    Raises:
        FileNotFoundError: If file doesn't exist
        yaml.YAMLError: If YAML is invalid
    """
    yaml_path = Path(yaml_path)

    if not yaml_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {yaml_path}")

    logger.info(f"Loading configuration from: {yaml_path}")

    with open(yaml_path, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)

    logger.debug(f"Configuration loaded successfully")
    return config_data


def load_json_config(json_path: str) -> Dict[str, Any]:
    """
    Load JSON configuration file.

    Args:
        json_path: Path to JSON file

    Returns:
        Dict with configuration data

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If JSON is invalid
    """
    json_path = Path(json_path)

    if not json_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {json_path}")

    logger.info(f"Loading configuration from: {json_path}")

    with open(json_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)

    logger.debug(f"Configuration loaded successfully")
    return config_data


def load_config_file(config_path: str) -> Dict[str, Any]:
    """
    Auto-detect file type and load configuration.

    Args:
        config_path: Path to YAML or JSON file

    Returns:
        Dict with configuration data
    """
    config_path = Path(config_path)
    suffix = config_path.suffix.lower()

    if suffix in ['.yaml', '.yml']:
        return load_yaml_config(str(config_path))
    elif suffix == '.json':
        return load_json_config(str(config_path))
    else:
        raise ValueError(f"Unsupported config file format: {suffix}. Must be .yaml, .yml, or .json")


def parse_batch_config(config_data: Dict[str, Any]) -> BatchConfig:
    """
    Parse dictionary into BatchConfig dataclass.

    Args:
        config_data: Dict with configuration data

    Returns:
        BatchConfig instance

    Raises:
        ValueError: If configuration is invalid
    """
    logger.debug("Parsing batch configuration")

    # Parse analysis config
    analysis_data = config_data.get('analysis', {})
    analysis_type = analysis_data.get('type', 'snapshot')

    snapshot_config = None
    timeseries_config = None

    if analysis_type == 'snapshot':
        snapshot_data = analysis_data.get('snapshot', {})
        snapshot_config = SnapshotConfig(**snapshot_data)
    elif analysis_type == 'time_series':
        ts_data = analysis_data.get('time_series', {})
        timeseries_config = TimeSeriesConfig(**ts_data)

    analysis_config = AnalysisConfig(
        type=analysis_type,
        snapshot=snapshot_config,
        time_series=timeseries_config
    )

    # Parse regions
    regions_data = config_data.get('regions', [])
    regions = [RegionConfig(**region) for region in regions_data]

    # Parse processing config
    processing_data = config_data.get('processing', {})
    processing_config = ProcessingConfig(**processing_data)

    # Parse output config
    output_data = config_data.get('output', {})
    output_config = OutputConfig(**output_data)

    # Parse advanced config
    advanced_data = config_data.get('advanced', {})
    advanced_config = AdvancedConfig(**advanced_data)

    # Create batch config
    batch_config = BatchConfig(
        analysis=analysis_config,
        regions=regions,
        processing=processing_config,
        output=output_config,
        advanced=advanced_config,
        name=config_data.get('name'),
        description=config_data.get('description'),
        version=config_data.get('version', '1.0')
    )

    logger.info(f"Configuration parsed: {len(regions)} regions")
    return batch_config


def load_batch_config(config_path: str) -> BatchConfig:
    """
    Load and parse batch configuration file.

    Args:
        config_path: Path to YAML or JSON configuration file

    Returns:
        BatchConfig instance

    Example:
        >>> config = load_batch_config("batch_analysis.yaml")
        >>> print(f"Analysis type: {config.analysis.type}")
        >>> print(f"Regions: {len(config.regions)}")
    """
    config_data = load_config_file(config_path)
    batch_config = parse_batch_config(config_data)
    return batch_config


# ============================================================================
# Configuration Validation
# ============================================================================

def validate_config(config: BatchConfig) -> List[str]:
    """
    Validate configuration and return list of errors.

    Args:
        config: BatchConfig instance

    Returns:
        List of error messages (empty if valid)

    Example:
        >>> config = load_batch_config("batch.yaml")
        >>> errors = validate_config(config)
        >>> if errors:
        ...     print("Configuration errors:")
        ...     for error in errors:
        ...         print(f"  - {error}")
    """
    errors = []

    # Validate regions
    if not config.regions:
        errors.append("No regions defined in configuration")

    # Validate region names are unique
    region_names = [r.name for r in config.regions]
    duplicates = [name for name in region_names if region_names.count(name) > 1]
    if duplicates:
        errors.append(f"Duplicate region names found: {set(duplicates)}")

    # Validate output directory is writable
    try:
        output_dir = Path(config.output.base_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        errors.append(f"Cannot create output directory '{config.output.base_dir}': {str(e)}")

    # Validate chunk size is reasonable
    if config.processing.chunk_size_km < 10 or config.processing.chunk_size_km > 200:
        errors.append(f"Chunk size {config.processing.chunk_size_km} km is outside recommended range (10-200 km)")

    # Validate parallel processing settings
    if config.advanced.parallel_processing:
        if config.advanced.max_workers < 1 or config.advanced.max_workers > 8:
            errors.append(f"max_workers {config.advanced.max_workers} is outside valid range (1-8)")

    return errors


# ============================================================================
# Configuration Template Generation
# ============================================================================

def save_config_template(output_path: str, template_type: str = 'basic'):
    """
    Save configuration template file.

    Args:
        output_path: Path to save template
        template_type: 'basic', 'advanced', or 'full'

    Example:
        >>> save_config_template("my_config.yaml", "basic")
    """
    output_path = Path(output_path)

    if template_type == 'basic':
        template = """# OSM Geometrical Complexity Batch Analysis Configuration
name: basic_analysis
description: Basic batch analysis configuration

analysis:
  type: snapshot  # 'snapshot' or 'time_series'

  snapshot:
    timestamp: "2025-08-01"

regions:
  - name: example_country
    type: country
    country: Israel

  - name: example_city
    type: city
    city: Jerusalem
    radius_km: 30

processing:
  filter: "type:way and building=*"
  use_adaptive_chunking: true
  resume: true

output:
  base_dir: "./results"
  generate_plots: true
  log_level: INFO
"""

    elif template_type == 'timeseries':
        template = """# Time Series Analysis Configuration
name: time_series_analysis
description: Analyze complexity evolution over time

analysis:
  type: time_series

  time_series:
    start_year: 2015
    end_year: 2025
    interval: yearly  # 'yearly', 'quarterly', 'monthly'

regions:
  - name: israel
    type: country
    country: Israel

  - name: palestine
    type: country
    country: Palestine

processing:
  filter: "type:way and building=*"
  use_adaptive_chunking: true
  chunk_size_km: 50
  resume: true

output:
  base_dir: "./results/time_series"
  generate_plots: true
  log_level: INFO
"""

    elif template_type == 'full':
        template = """# Complete Configuration Template
name: full_analysis
description: Complete configuration with all options
version: "1.0"

analysis:
  type: snapshot  # or 'time_series'

  snapshot:
    timestamp: "2025-08-01"

  time_series:
    start_year: 2015
    end_year: 2025
    interval: yearly

regions:
  # Country-level analysis
  - name: israel
    type: country
    country: Israel
    notes: "Full country analysis"

  # City-level analysis
  - name: jerusalem
    type: city
    city: Jerusalem
    radius_km: 30

  # Custom coordinates
  - name: west_bank
    type: coordinates
    lat: 31.9
    lon: 35.2
    radius_km: 40

  # Custom bounding box
  - name: custom_area
    type: bbox
    bbox: "34.5,31.0,35.5,32.5"

processing:
  filter: "type:way and building=*"
  use_adaptive_chunking: true
  chunk_size_km: 50
  max_features_per_chunk: 50000
  building_density: 2000
  resume: true
  cleanup_chunks: true

output:
  base_dir: "./results"
  structure: by_analysis_type
  generate_plots: true
  generate_reports: false
  report_format: markdown
  log_level: INFO

advanced:
  parallel_processing: false
  max_workers: 2
  api_timeout: 300
  retry_failed: true
  max_retries: 3
"""

    else:
        raise ValueError(f"Invalid template type: {template_type}. Must be 'basic', 'timeseries', or 'full'")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(template)

    logger.info(f"Configuration template saved to: {output_path}")


def print_config_summary(config: BatchConfig):
    """
    Print human-readable summary of configuration.

    Args:
        config: BatchConfig instance
    """
    print("\n" + "=" * 80)
    print("BATCH CONFIGURATION SUMMARY")
    print("=" * 80)

    if config.name:
        print(f"Name: {config.name}")
    if config.description:
        print(f"Description: {config.description}")

    print(f"\nAnalysis Type: {config.analysis.type}")

    if config.analysis.type == 'snapshot' and config.analysis.snapshot:
        print(f"  Timestamp: {config.analysis.snapshot.timestamp}")
    elif config.analysis.type == 'time_series' and config.analysis.time_series:
        ts = config.analysis.time_series
        print(f"  Time Range: {ts.start_year}-{ts.end_year}")
        print(f"  Interval: {ts.interval}")

    print(f"\nRegions: {len(config.regions)}")
    for region in config.regions:
        print(f"  - {region.name} ({region.type})")

    print(f"\nProcessing:")
    print(f"  Filter: {config.processing.filter}")
    print(f"  Adaptive Chunking: {config.processing.use_adaptive_chunking}")
    print(f"  Chunk Size: {config.processing.chunk_size_km} km")
    print(f"  Resume: {config.processing.resume}")

    print(f"\nOutput:")
    print(f"  Base Directory: {config.output.base_dir}")
    print(f"  Generate Plots: {config.output.generate_plots}")
    print(f"  Log Level: {config.output.log_level}")

    print("=" * 80 + "\n")
