"""Tests for duplicate detection functionality."""

import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from photosort.duplicates import (
    DuplicateCandidate, 
    DuplicateDetector, 
    DuplicateGroup
)


class TestDuplicateCandidate(TestCase):
    """Test DuplicateCandidate class."""
    
    def setUp(self):
        """Set up test fixtures."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            f.write(b'fake image data')
            self.temp_file = Path(f.name)
        
        self.candidate = DuplicateCandidate(
            self.temp_file, 
            file_size=1024,
            image_hash='abc123'
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.temp_file.exists():
            self.temp_file.unlink()
    
    def test_init(self):
        """Test candidate initialization."""
        self.assertEqual(self.candidate.file_path, self.temp_file)
        self.assertEqual(self.candidate.file_size, 1024)
        self.assertEqual(self.candidate.image_hash, 'abc123')
    
    def test_file_name_property(self):
        """Test file name property."""
        self.assertEqual(self.candidate.file_name, self.temp_file.name)
    
    def test_get_md5_hash(self):
        """Test MD5 hash calculation."""
        md5_hash = self.candidate.get_md5_hash()
        self.assertIsInstance(md5_hash, str)
        self.assertGreater(len(md5_hash), 0)
    
    def test_is_better_quality_than_size(self):
        """Test quality comparison based on file size."""
        other = DuplicateCandidate(self.temp_file, file_size=512, image_hash='abc124')
        self.assertTrue(self.candidate.is_better_quality_than(other))
        self.assertFalse(other.is_better_quality_than(self.candidate))
    
    @patch('photosort.duplicates.PIL_AVAILABLE', True)
    @patch('photosort.duplicates.Image')
    def test_image_dimensions(self, mock_image):
        """Test image dimensions property."""
        mock_img = Mock()
        mock_img.size = (1920, 1080)
        mock_image.open.return_value.__enter__.return_value = mock_img
        
        dimensions = self.candidate.image_dimensions
        self.assertEqual(dimensions, (1920, 1080))
    
    def test_image_area(self):
        """Test image area calculation."""
        with patch.object(self.candidate, 'image_dimensions', (1920, 1080)):
            area = self.candidate.image_area
            self.assertEqual(area, 1920 * 1080)


class TestDuplicateGroup(TestCase):
    """Test DuplicateGroup class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.candidates = [
            DuplicateCandidate(Path('file1.jpg'), file_size=1024, image_hash='abc123'),
            DuplicateCandidate(Path('file2.jpg'), file_size=2048, image_hash='abc124'),
            DuplicateCandidate(Path('file3.jpg'), file_size=512, image_hash='abc125')
        ]
        self.group = DuplicateGroup(self.candidates)
    
    def test_size_property(self):
        """Test group size property."""
        self.assertEqual(self.group.size, 3)
    
    def test_best_candidate(self):
        """Test best candidate selection."""
        best = self.group.best_candidate
        self.assertEqual(best.file_size, 2048)  # Largest file
    
    def test_duplicates_to_remove(self):
        """Test getting duplicates to remove."""
        to_remove = self.group.duplicates_to_remove
        self.assertEqual(len(to_remove), 2)  # All except best
        self.assertNotIn(self.group.best_candidate, to_remove)
    
    def test_get_total_size(self):
        """Test total size calculation."""
        total_size = self.group.get_total_size()
        self.assertEqual(total_size, 1024 + 2048 + 512)
    
    def test_get_wasted_space(self):
        """Test wasted space calculation."""
        wasted_space = self.group.get_wasted_space()
        self.assertEqual(wasted_space, 1024 + 512)  # Size of duplicates to remove


class TestDuplicateDetector(TestCase):
    """Test DuplicateDetector class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.detector = DuplicateDetector(algorithm='dhash', threshold=10)
    
    def test_init(self):
        """Test detector initialization."""
        self.assertEqual(self.detector.algorithm, 'dhash')
        self.assertEqual(self.detector.threshold, 10)
    
    def test_init_invalid_algorithm(self):
        """Test initialization with invalid algorithm."""
        with patch.object(DuplicateDetector, '_get_available_algorithms', return_value={'dhash': Mock()}):
            with self.assertRaises(ValueError):
                DuplicateDetector(algorithm='invalid')
    
    @patch('photosort.duplicates.IMAGEHASH_AVAILABLE', True)
    @patch('photosort.duplicates.imagehash')
    def test_get_available_algorithms(self, mock_imagehash):
        """Test getting available algorithms."""
        mock_imagehash.dhash = Mock()
        mock_imagehash.phash = Mock()
        mock_imagehash.average_hash = Mock()
        mock_imagehash.whash = Mock()
        
        detector = DuplicateDetector()
        algorithms = detector._get_available_algorithms()
        
        self.assertIn('dhash', algorithms)
        self.assertIn('phash', algorithms)
        self.assertIn('ahash', algorithms)
        self.assertIn('whash', algorithms)
    
    def test_calculate_hamming_distance(self):
        """Test Hamming distance calculation."""
        hash1 = 'abc123'
        hash2 = 'abc124'  # Differs by 1 bit in the last hex digit
        distance = self.detector.calculate_hamming_distance(hash1, hash2)
        self.assertIsInstance(distance, int)
        self.assertGreaterEqual(distance, 0)
    
    def test_calculate_hamming_distance_invalid(self):
        """Test Hamming distance with invalid hashes."""
        distance = self.detector.calculate_hamming_distance('invalid', 'hash')
        self.assertEqual(distance, float('inf'))
        
        distance = self.detector.calculate_hamming_distance('abc', 'abcdef')
        self.assertEqual(distance, float('inf'))
    
    def test_are_similar(self):
        """Test similarity checking."""
        # Mock the distance calculation
        with patch.object(self.detector, 'calculate_hamming_distance', return_value=5):
            self.assertTrue(self.detector.are_similar('hash1', 'hash2'))
        
        with patch.object(self.detector, 'calculate_hamming_distance', return_value=15):
            self.assertFalse(self.detector.are_similar('hash1', 'hash2'))
    
    def test_scan_directory_nonexistent(self):
        """Test scanning non-existent directory."""
        candidates = self.detector.scan_directory(
            Path('/nonexistent'), 
            ['.jpg'], 
            recursive=True
        )
        self.assertEqual(len(candidates), 0)
    
    def test_find_duplicates_empty(self):
        """Test finding duplicates with empty candidate list."""
        groups = self.detector.find_duplicates([])
        self.assertEqual(len(groups), 0)
    
    def test_find_exact_duplicates(self):
        """Test finding exact duplicates."""
        candidates = [
            DuplicateCandidate(Path('file1.jpg'), file_size=1024),
            DuplicateCandidate(Path('file2.jpg'), file_size=1024),
            DuplicateCandidate(Path('file3.jpg'), file_size=2048)
        ]
        
        # Mock MD5 hash calculation
        candidates[0].get_md5_hash = Mock(return_value='same_hash')
        candidates[1].get_md5_hash = Mock(return_value='same_hash')
        candidates[2].get_md5_hash = Mock(return_value='different_hash')
        
        groups = self.detector.find_exact_duplicates(candidates)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].size, 2)
    
    def test_get_statistics(self):
        """Test getting statistics."""
        candidates = [
            DuplicateCandidate(Path('file1.jpg'), file_size=1024),
            DuplicateCandidate(Path('file2.jpg'), file_size=2048),
            DuplicateCandidate(Path('file3.jpg'), file_size=512)
        ]
        group = DuplicateGroup(candidates)
        
        stats = self.detector.get_statistics([group])
        
        self.assertEqual(stats['duplicate_groups'], 1)
        self.assertEqual(stats['total_files_in_groups'], 3)
        self.assertEqual(stats['duplicate_files'], 2)  # All except best
        self.assertEqual(stats['original_files'], 1)   # Best candidate
        self.assertGreater(stats['total_size_bytes'], 0)
        self.assertGreater(stats['wasted_space_bytes'], 0)