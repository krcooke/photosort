"""Configuration management for PhotoSort."""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import yaml
except ImportError:
    # Fallback if yaml not available
    yaml = None


class Config:
    """Configuration manager for PhotoSort."""
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """Initialize configuration.
        
        Args:
            config_path: Path to configuration file. If None, uses default config.
        """
        self._config: Dict[str, Any] = {}
        self._load_config(config_path)
    
    def _load_config(self, config_path: Optional[Union[str, Path]] = None) -> None:
        """Load configuration from file or use defaults."""
        if config_path is None:
            # Use default config
            default_config_path = Path(__file__).parent.parent / "config" / "default_config.yaml"
            config_path = default_config_path
        
        config_path = Path(config_path)
        
        if config_path.exists():
            if yaml is not None:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f) or {}
            else:
                # Fallback: load a minimal default config
                self._config = self._get_minimal_default_config()
        else:
            # Use minimal default if file doesn't exist
            self._config = self._get_minimal_default_config()
    
    def _get_minimal_default_config(self) -> Dict[str, Any]:
        """Get minimal default configuration when YAML is not available."""
        return {
            'directory_structure': {
                'pattern': '{year}/{month:02d}-{month_name}/{day:02d}',
                'fallback_pattern': 'unsorted/{year}/{month:02d}',
                'date_source': ['exif_datetime', 'exif_datetime_original', 'file_mtime'],
                'location_inference': [
                    {'pattern': '.*/(?P<location>[^/]+)/.*photos?.*', 'priority': 1},
                    {'pattern': '.*/(?P<location>[^/]+)/?$', 'priority': 2},
                ]
            },
            'duplicate_detection': {
                'algorithm': 'dhash',
                'threshold': 10,
                'quarantine_folder': 'duplicates',
                'action': 'move',
                'keep_best_quality': True
            },
            'metadata_enhancement': {
                'write_location_to_exif': True,
                'write_keywords_to_exif': True,
                'backup_originals': True,
            },
            'file_processing': {
                'supported_formats': ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp', '.heic'],
                'min_file_size': 1024,
                'max_file_size': 0,
                'max_workers': 4,
                'verify_operations': True
            },
            'output': {
                'verbosity': 1,
                'show_progress': True,
                'log_file': '',
                'dry_run': False
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.
        
        Args:
            key: Configuration key in dot notation (e.g., 'duplicate_detection.threshold')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value using dot notation.
        
        Args:
            key: Configuration key in dot notation
            value: Value to set
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    @property
    def directory_pattern(self) -> str:
        """Get directory structure pattern."""
        return self.get('directory_structure.pattern', '{year}/{month:02d}')
    
    @property
    def fallback_pattern(self) -> str:
        """Get fallback directory pattern."""
        return self.get('directory_structure.fallback_pattern', 'unsorted/{year}')
    
    @property
    def date_sources(self) -> List[str]:
        """Get list of date sources in priority order."""
        return self.get('directory_structure.date_source', ['exif_datetime', 'file_mtime'])
    
    @property
    def duplicate_algorithm(self) -> str:
        """Get duplicate detection algorithm."""
        return self.get('duplicate_detection.algorithm', 'dhash')
    
    @property
    def duplicate_threshold(self) -> int:
        """Get duplicate detection threshold."""
        return self.get('duplicate_detection.threshold', 10)
    
    @property
    def quarantine_folder(self) -> str:
        """Get quarantine folder name."""
        return self.get('duplicate_detection.quarantine_folder', 'duplicates')
    
    @property
    def supported_formats(self) -> List[str]:
        """Get list of supported file formats."""
        return self.get('file_processing.supported_formats', ['.jpg', '.jpeg', '.png'])
    
    @property
    def max_workers(self) -> int:
        """Get maximum number of worker threads."""
        return self.get('file_processing.max_workers', 4)
    
    @property
    def verbosity(self) -> int:
        """Get verbosity level."""
        return self.get('output.verbosity', 1)
    
    @property
    def dry_run(self) -> bool:
        """Get dry run mode."""
        return self.get('output.dry_run', False)
    
    @property
    def show_progress(self) -> bool:
        """Get show progress setting."""
        return self.get('output.show_progress', True)
    
    def get_location_patterns(self) -> List[Dict[str, Any]]:
        """Get location inference patterns."""
        patterns = self.get('directory_structure.location_inference', [])
        # Sort by priority (lower number = higher priority)
        return sorted(patterns, key=lambda x: x.get('priority', 999))
    
    def get_keyword_patterns(self) -> List[Dict[str, Any]]:
        """Get keyword extraction patterns."""
        return self.get('metadata_enhancement.keyword_patterns', [])
    
    def is_supported_format(self, file_path: Union[str, Path]) -> bool:
        """Check if file format is supported.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if format is supported
        """
        suffix = Path(file_path).suffix.lower()
        return suffix in self.supported_formats
    
    def save_config(self, config_path: Union[str, Path]) -> None:
        """Save current configuration to file.
        
        Args:
            config_path: Path to save configuration
        """
        if yaml is None:
            raise RuntimeError("PyYAML not available for saving configuration")
        
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)


def load_config(config_path: Optional[Union[str, Path]] = None) -> Config:
    """Load configuration from file or use defaults.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration instance
    """
    return Config(config_path)