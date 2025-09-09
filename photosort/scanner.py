"""Photo collection scanning and analysis."""

import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from .config import Config
from .duplicates import DuplicateDetector
from .metadata import MetadataExtractor, PhotoMetadata
from .utils import format_file_size, get_file_stats


class ScanResult:
    """Results from scanning a photo collection."""
    
    def __init__(self):
        """Initialize scan result."""
        self.total_files = 0
        self.supported_files = 0
        self.unsupported_files = 0
        self.total_size = 0
        self.supported_size = 0
        
        self.files_by_extension: Dict[str, int] = defaultdict(int)
        self.size_by_extension: Dict[str, int] = defaultdict(int)
        self.files_by_year: Dict[int, int] = defaultdict(int)
        self.oldest_photo: Optional[datetime] = None
        self.newest_photo: Optional[datetime] = None
        
        self.metadata_stats = {
            'with_exif': 0,
            'with_gps': 0,
            'with_camera_info': 0,
            'corrupted': 0
        }
        
        self.duplicate_stats: Optional[Dict] = None
        self.scan_errors: List[str] = []


class PhotoScanner:
    """Scanner for analyzing photo collections."""
    
    def __init__(self, config: Config):
        """Initialize photo scanner.
        
        Args:
            config: Configuration instance
        """
        self.config = config
        
        # Initialize metadata extractor with geocoding settings
        geocoding_enabled = config.get('metadata_enhancement.reverse_geocoding.enabled', True)
        cache_file = config.get('metadata_enhancement.reverse_geocoding.cache_file', None)
        if cache_file:
            cache_file = cache_file.replace('~', str(Path.home()))
        
        self.metadata_extractor = MetadataExtractor(
            enable_geocoding=geocoding_enabled,
            geocoding_cache_file=cache_file
        )
        self.duplicate_detector = None
        
        if config.get('duplicate_detection.enabled', True):
            try:
                self.duplicate_detector = DuplicateDetector(
                    algorithm=config.duplicate_algorithm,
                    threshold=config.duplicate_threshold
                )
            except (ValueError, ImportError):
                # Duplicate detection not available
                pass
    
    def scan_directory(self, directory: Union[str, Path], 
                      recursive: bool = True,
                      analyze_duplicates: bool = False) -> ScanResult:
        """Scan directory and analyze photo collection.
        
        Args:
            directory: Directory to scan
            recursive: Whether to scan recursively
            analyze_duplicates: Whether to analyze for duplicates
            
        Returns:
            ScanResult with analysis
        """
        directory = Path(directory)
        result = ScanResult()
        
        if not directory.exists():
            result.scan_errors.append(f"Directory does not exist: {directory}")
            return result
        
        if not directory.is_dir():
            result.scan_errors.append(f"Path is not a directory: {directory}")
            return result
        
        # Find all files
        pattern = "**/*" if recursive else "*"
        files = []
        
        try:
            for file_path in directory.glob(pattern):
                if file_path.is_file():
                    files.append(file_path)
        except (OSError, PermissionError) as e:
            result.scan_errors.append(f"Error scanning directory: {e}")
            return result
        
        # Analyze files
        photo_files = []
        for file_path in files:
            self._analyze_file(file_path, result)
            
            # Collect photo files for further analysis
            if self.config.is_supported_format(file_path):
                photo_files.append(file_path)
        
        # Analyze photo metadata if we have supported files
        if photo_files:
            self._analyze_metadata(photo_files, result)
        
        # Analyze duplicates if requested
        if analyze_duplicates and self.duplicate_detector and photo_files:
            try:
                self._analyze_duplicates(photo_files, result)
            except Exception as e:
                result.scan_errors.append(f"Error analyzing duplicates: {e}")
        
        return result
    
    def _analyze_file(self, file_path: Path, result: ScanResult) -> None:
        """Analyze a single file.
        
        Args:
            file_path: Path to file
            result: Result object to update
        """
        try:
            stats = get_file_stats(file_path)
            
            result.total_files += 1
            result.total_size += stats['size']
            
            extension = stats['extension']
            result.files_by_extension[extension] += 1
            result.size_by_extension[extension] += stats['size']
            
            # Check if supported format
            if self.config.is_supported_format(file_path):
                result.supported_files += 1
                result.supported_size += stats['size']
            else:
                result.unsupported_files += 1
                
        except Exception as e:
            result.scan_errors.append(f"Error analyzing {file_path}: {e}")
    
    def _analyze_metadata(self, photo_files: List[Path], result: ScanResult) -> None:
        """Analyze metadata from photo files.
        
        Args:
            photo_files: List of photo file paths
            result: Result object to update
        """
        for file_path in photo_files:
            try:
                metadata = self.metadata_extractor.extract_metadata(file_path)
                
                # Update metadata statistics
                if metadata.exif_data:
                    result.metadata_stats['with_exif'] += 1
                
                if metadata.location:
                    result.metadata_stats['with_gps'] += 1
                
                if metadata.camera_info:
                    result.metadata_stats['with_camera_info'] += 1
                
                # Track date information
                date_taken = metadata.datetime_taken
                if date_taken:
                    year = date_taken.year
                    result.files_by_year[year] += 1
                    
                    if result.oldest_photo is None or date_taken < result.oldest_photo:
                        result.oldest_photo = date_taken
                    
                    if result.newest_photo is None or date_taken > result.newest_photo:
                        result.newest_photo = date_taken
                        
            except Exception as e:
                result.metadata_stats['corrupted'] += 1
                result.scan_errors.append(f"Error extracting metadata from {file_path}: {e}")
    
    def _analyze_duplicates(self, photo_files: List[Path], result: ScanResult) -> None:
        """Analyze for duplicate photos.
        
        Args:
            photo_files: List of photo file paths
            result: Result object to update
        """
        if not self.duplicate_detector:
            return
        
        # Create duplicate candidates
        candidates = []
        for file_path in photo_files:
            try:
                stats = get_file_stats(file_path)
                image_hash = self.duplicate_detector.calculate_hash(file_path)
                
                if image_hash:
                    from .duplicates import DuplicateCandidate
                    candidate = DuplicateCandidate(file_path, stats['size'], image_hash)
                    candidates.append(candidate)
                    
            except Exception:
                # Skip files that can't be processed
                continue
        
        # Find duplicate groups
        if candidates:
            groups = self.duplicate_detector.find_duplicates(candidates)
            result.duplicate_stats = self.duplicate_detector.get_statistics(groups)
            result.duplicate_stats['groups'] = groups


def format_scan_report(result: ScanResult, verbose: bool = False) -> str:
    """Format scan result as a human-readable report.
    
    Args:
        result: ScanResult to format
        verbose: Whether to include verbose details
        
    Returns:
        Formatted report string
    """
    lines = []
    
    # Header
    lines.append("=== Photo Collection Scan Report ===")
    lines.append("")
    
    # Overall statistics
    lines.append("📊 Overall Statistics:")
    lines.append(f"  Total files: {result.total_files:,}")
    lines.append(f"  Supported photos: {result.supported_files:,}")
    lines.append(f"  Unsupported files: {result.unsupported_files:,}")
    lines.append(f"  Total size: {format_file_size(result.total_size)}")
    lines.append(f"  Photos size: {format_file_size(result.supported_size)}")
    lines.append("")
    
    # File types
    if result.files_by_extension:
        lines.append("📁 File Types:")
        sorted_extensions = sorted(result.files_by_extension.items(), 
                                 key=lambda x: x[1], reverse=True)
        for ext, count in sorted_extensions:
            size = result.size_by_extension[ext]
            ext_name = ext.upper()[1:] if ext else "No extension"
            lines.append(f"  {ext_name}: {count:,} files ({format_file_size(size)})")
        lines.append("")
    
    # Date range
    if result.oldest_photo and result.newest_photo:
        lines.append("📅 Date Range:")
        lines.append(f"  Oldest photo: {result.oldest_photo.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"  Newest photo: {result.newest_photo.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if result.files_by_year:
            lines.append("  Photos by year:")
            sorted_years = sorted(result.files_by_year.items())
            for year, count in sorted_years:
                lines.append(f"    {year}: {count:,} photos")
        lines.append("")
    
    # Metadata statistics
    if result.metadata_stats:
        lines.append("🏷️  Metadata Analysis:")
        lines.append(f"  Photos with EXIF data: {result.metadata_stats['with_exif']:,}")
        lines.append(f"  Photos with GPS location: {result.metadata_stats['with_gps']:,}")
        lines.append(f"  Photos with camera info: {result.metadata_stats['with_camera_info']:,}")
        if result.metadata_stats['corrupted'] > 0:
            lines.append(f"  Corrupted/unreadable: {result.metadata_stats['corrupted']:,}")
        lines.append("")
    
    # Duplicate analysis
    if result.duplicate_stats:
        stats = result.duplicate_stats
        lines.append("🔍 Duplicate Analysis:")
        lines.append(f"  Duplicate groups found: {stats.get('duplicate_groups', 0):,}")
        lines.append(f"  Total files in groups: {stats.get('total_files_in_groups', 0):,}")
        lines.append(f"  Duplicate files: {stats.get('duplicate_files', 0):,}")
        lines.append(f"  Potential space savings: {format_file_size(stats.get('wasted_space_bytes', 0))}")
        if stats.get('space_savings_percent', 0) > 0:
            lines.append(f"  Space savings: {stats['space_savings_percent']:.1f}%")
        lines.append("")
    
    # Errors
    if result.scan_errors:
        lines.append("⚠️  Scan Errors:")
        for error in result.scan_errors[:10]:  # Limit to first 10 errors
            lines.append(f"  {error}")
        if len(result.scan_errors) > 10:
            lines.append(f"  ... and {len(result.scan_errors) - 10} more errors")
        lines.append("")
    
    # Verbose details
    if verbose and result.duplicate_stats and 'groups' in result.duplicate_stats:
        lines.append("🔍 Duplicate Groups (Top 10):")
        groups = result.duplicate_stats['groups']
        for i, group in enumerate(sorted(groups, key=lambda g: g.size, reverse=True)[:10], 1):
            lines.append(f"  Group {i}: {group.size} files, {format_file_size(group.get_total_size())}")
            for candidate in group.candidates[:3]:  # Show first 3 files
                lines.append(f"    - {candidate.file_path.name} ({format_file_size(candidate.file_size)})")
            if group.size > 3:
                lines.append(f"    - ... and {group.size - 3} more files")
        lines.append("")
    
    return "\n".join(lines)