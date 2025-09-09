"""Tests for metadata extraction and enhancement."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from photosort.metadata import MetadataExtractor, PhotoMetadata


class TestPhotoMetadata(TestCase):
    """Test PhotoMetadata class."""
    
    def setUp(self):
        """Set up test fixtures."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            self.temp_file = Path(f.name)
        self.metadata = PhotoMetadata(self.temp_file)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.temp_file.exists():
            self.temp_file.unlink()
    
    def test_init(self):
        """Test metadata initialization."""
        self.assertEqual(self.metadata.file_path, self.temp_file)
        self.assertIsInstance(self.metadata.exif_data, dict)
        self.assertIsInstance(self.metadata.inferred_data, dict)
    
    def test_datetime_taken_from_exif(self):
        """Test getting datetime from EXIF data."""
        self.metadata.exif_data['DateTime'] = '2023:12:25 14:30:00'
        dt = self.metadata.datetime_taken
        self.assertIsInstance(dt, datetime)
        self.assertEqual(dt.year, 2023)
        self.assertEqual(dt.month, 12)
        self.assertEqual(dt.day, 25)
    
    def test_datetime_taken_fallback(self):
        """Test datetime fallback to file modification time."""
        # No EXIF datetime data
        dt = self.metadata.datetime_taken
        self.assertIsInstance(dt, datetime)
    
    def test_location_from_gps(self):
        """Test getting location from GPS data."""
        self.metadata.exif_data['GPSInfo'] = {
            'GPSLatitude': (40.0, 30.0, 15.0),
            'GPSLongitude': (74.0, 0.0, 30.0),
            'GPSLatitudeRef': 'N',
            'GPSLongitudeRef': 'W'
        }
        location = self.metadata.location
        self.assertIsInstance(location, dict)
        self.assertAlmostEqual(location['latitude'], 40.504167, places=4)
        self.assertAlmostEqual(location['longitude'], -74.008333, places=4)
    
    def test_camera_info(self):
        """Test getting camera information."""
        self.metadata.exif_data['Make'] = 'Canon'
        self.metadata.exif_data['Model'] = 'EOS R5'
        camera_info = self.metadata.camera_info
        self.assertEqual(camera_info['make'], 'Canon')
        self.assertEqual(camera_info['model'], 'EOS R5')
    
    def test_add_inferred_location(self):
        """Test adding inferred location."""
        self.metadata.add_inferred_location('Paris')
        self.assertEqual(self.metadata.inferred_data['location'], 'Paris')
    
    def test_add_inferred_keywords(self):
        """Test adding inferred keywords."""
        self.metadata.add_inferred_keywords(['vacation', 'europe'])
        self.assertIn('vacation', self.metadata.inferred_data['keywords'])
        self.assertIn('europe', self.metadata.inferred_data['keywords'])
        
        # Test deduplication
        self.metadata.add_inferred_keywords(['vacation', 'beach'])
        keywords = self.metadata.inferred_data['keywords']
        self.assertEqual(keywords.count('vacation'), 1)
        self.assertIn('beach', keywords)
    
    def test_keywords_property(self):
        """Test keywords property combines EXIF and inferred data."""
        self.metadata.exif_data['Keywords'] = ['exif_keyword']
        self.metadata.add_inferred_keywords(['inferred_keyword'])
        keywords = self.metadata.keywords
        self.assertIn('exif_keyword', keywords)
        self.assertIn('inferred_keyword', keywords)


class TestMetadataExtractor(TestCase):
    """Test MetadataExtractor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.extractor = MetadataExtractor()
    
    def test_init(self):
        """Test extractor initialization."""
        self.assertIsInstance(self.extractor.available_libs, dict)
    
    def test_infer_metadata_from_path(self):
        """Test inferring metadata from file paths."""
        patterns = [
            {'pattern': r'.*/(?P<location>[^/]+)/photos/.*', 'priority': 1},
            {'pattern': r'.*/(?P<year>\d{4})/.*', 'priority': 2}
        ]
        
        file_path = Path('/Users/john/Paris/photos/IMG_001.jpg')
        inferred = self.extractor.infer_metadata_from_path(file_path, patterns)
        
        self.assertEqual(inferred.get('location'), 'Paris')
    
    def test_extract_keywords_from_path(self):
        """Test extracting keywords from file paths."""
        keyword_patterns = [
            {'pattern': r'.*/(?P<event>vacation|holiday)/.*', 'tag': 'event'},
            {'pattern': r'.*/(?P<person>[A-Z][a-z]+)/.*', 'tag': 'person'}
        ]
        
        file_path = Path('/Photos/John/vacation/IMG_001.jpg')
        keywords = self.extractor.extract_keywords_from_path(file_path, keyword_patterns)
        
        self.assertIn('event:Vacation', keywords)
        self.assertIn('person:John', keywords)
    
    @patch('photosort.metadata.PIL_AVAILABLE', False)
    @patch('photosort.metadata.EXIFREAD_AVAILABLE', False)
    def test_extract_metadata_no_libs(self):
        """Test metadata extraction when libraries are not available."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            temp_file = Path(f.name)
        
        try:
            metadata = self.extractor.extract_metadata(temp_file)
            self.assertIsInstance(metadata, PhotoMetadata)
            self.assertEqual(len(metadata.exif_data), 0)
        finally:
            temp_file.unlink()
    
    def test_extract_metadata_nonexistent_file(self):
        """Test metadata extraction for non-existent file."""
        non_existent = Path('/nonexistent/file.jpg')
        metadata = self.extractor.extract_metadata(non_existent)
        self.assertIsInstance(metadata, PhotoMetadata)
        self.assertEqual(len(metadata.exif_data), 0)