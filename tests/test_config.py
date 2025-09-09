"""Tests for configuration management."""

import tempfile
from pathlib import Path
from unittest import TestCase

from photosort.config import Config, load_config


class TestConfig(TestCase):
    """Test configuration functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = Config()
    
    def test_default_config_loads(self):
        """Test that default configuration loads successfully."""
        self.assertIsInstance(self.config.directory_pattern, str)
        self.assertIsInstance(self.config.duplicate_threshold, int)
        self.assertIsInstance(self.config.supported_formats, list)
    
    def test_get_with_dot_notation(self):
        """Test getting values with dot notation."""
        threshold = self.config.get('duplicate_detection.threshold')
        self.assertIsInstance(threshold, int)
        self.assertEqual(threshold, self.config.duplicate_threshold)
    
    def test_get_with_default(self):
        """Test getting non-existent key returns default."""
        value = self.config.get('nonexistent.key', 'default_value')
        self.assertEqual(value, 'default_value')
    
    def test_set_with_dot_notation(self):
        """Test setting values with dot notation."""
        self.config.set('duplicate_detection.threshold', 5)
        self.assertEqual(self.config.duplicate_threshold, 5)
    
    def test_is_supported_format(self):
        """Test format support checking."""
        self.assertTrue(self.config.is_supported_format('photo.jpg'))
        self.assertTrue(self.config.is_supported_format('photo.JPEG'))
        self.assertFalse(self.config.is_supported_format('document.txt'))
    
    def test_location_patterns(self):
        """Test getting location patterns."""
        patterns = self.config.get_location_patterns()
        self.assertIsInstance(patterns, list)
        if patterns:
            self.assertIn('pattern', patterns[0])
    
    def test_load_config_function(self):
        """Test standalone config loading function."""
        config = load_config()
        self.assertIsInstance(config, Config)
        self.assertIsInstance(config.directory_pattern, str)


class TestConfigFile(TestCase):
    """Test configuration file handling."""
    
    def test_config_with_custom_file(self):
        """Test loading configuration from custom file."""
        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
duplicate_detection:
  threshold: 5
  algorithm: 'phash'
directory_structure:
  pattern: '{year}/{month}'
""")
            temp_path = f.name
        
        try:
            # Load config from temporary file
            config = Config(temp_path)
            self.assertEqual(config.duplicate_threshold, 5)
            self.assertEqual(config.duplicate_algorithm, 'phash')
            self.assertEqual(config.directory_pattern, '{year}/{month}')
        finally:
            # Clean up
            Path(temp_path).unlink()
    
    def test_config_with_nonexistent_file(self):
        """Test loading configuration from non-existent file."""
        config = Config('/nonexistent/config.yaml')
        # Should fall back to defaults
        self.assertIsInstance(config.directory_pattern, str)
        self.assertIsInstance(config.duplicate_threshold, int)