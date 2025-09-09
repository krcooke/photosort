"""Photo sorting and organization engine."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from .config import Config
from .metadata import MetadataExtractor, PhotoMetadata


class SortingRule:
    """Represents a rule for organizing photos."""
    
    def __init__(self, pattern: str, fallback_pattern: str = "unsorted/{year}"):
        """Initialize sorting rule.
        
        Args:
            pattern: Directory pattern with placeholders like {year}, {month}, etc.
            fallback_pattern: Pattern to use when metadata is insufficient
        """
        self.pattern = pattern
        self.fallback_pattern = fallback_pattern
    
    def generate_path(self, metadata: PhotoMetadata, base_path: Path) -> Path:
        """Generate destination path for a photo based on its metadata.
        
        Args:
            metadata: Photo metadata
            base_path: Base directory for sorting
            
        Returns:
            Destination path for the photo
        """
        try:
            return self._apply_pattern(metadata, base_path, self.pattern)
        except (KeyError, ValueError, TypeError):
            # Fallback to simpler pattern
            try:
                return self._apply_pattern(metadata, base_path, self.fallback_pattern)
            except (KeyError, ValueError, TypeError):
                # Ultimate fallback
                return base_path / "unsorted"
    
    def _apply_pattern(self, metadata: PhotoMetadata, base_path: Path, pattern: str) -> Path:
        """Apply a pattern to generate path.
        
        Args:
            metadata: Photo metadata
            base_path: Base directory
            pattern: Pattern string with placeholders
            
        Returns:
            Generated path
        """
        # Get date information
        dt = metadata.datetime_taken
        if not dt:
            # Try to get date from file modification time as fallback
            if metadata.file_path.exists():
                dt = datetime.fromtimestamp(metadata.file_path.stat().st_mtime)
            else:
                dt = datetime.now()  # Ultimate fallback
        
        # Prepare format variables
        format_vars = {
            'year': dt.year,
            'month': dt.month,
            'month_name': dt.strftime('%B'),
            'month_short': dt.strftime('%b'),
            'day': dt.day,
            'hour': dt.hour,
            'minute': dt.minute,
        }
        
        # Add location if available
        if metadata.location:
            # Format location coordinates
            lat = metadata.location['latitude']
            lon = metadata.location['longitude']
            format_vars['lat'] = f"{lat:.4f}"
            format_vars['lon'] = f"{lon:.4f}"
            format_vars['location'] = f"{lat:.2f}_{lon:.2f}"
        
        # Add location (GPS-based has priority over directory-inferred)
        if 'gps_location_name' in metadata.inferred_data:
            format_vars['location'] = self._clean_directory_name(metadata.inferred_data['gps_location_name'])
        elif 'location' in metadata.inferred_data:
            format_vars['location'] = self._clean_directory_name(metadata.inferred_data['location'])
        
        # Add event from keywords if available
        event_keywords = []
        for keyword in metadata.keywords:
            if keyword.startswith('event:'):
                event_keywords.append(keyword.split(':', 1)[1])
        format_vars['event'] = event_keywords[0] if event_keywords else 'general'
        
        # Add camera info
        camera_info = metadata.camera_info
        if 'make' in camera_info:
            format_vars['camera_make'] = self._clean_directory_name(camera_info['make'])
        if 'model' in camera_info:
            format_vars['camera_model'] = self._clean_directory_name(camera_info['model'])
        
        # Apply the pattern
        try:
            relative_path = pattern.format(**format_vars)
            return base_path / relative_path
        except KeyError as e:
            # Missing required variable, try with defaults
            missing_key = str(e).strip("'\"")
            default_values = {
                'location': 'unknown-location',
                'event': 'general',
                'camera_make': 'unknown-camera',
                'camera_model': 'unknown-model',
            }
            format_vars[missing_key] = default_values.get(missing_key, 'unknown')
            relative_path = pattern.format(**format_vars)
            return base_path / relative_path
    
    def _clean_directory_name(self, name: str) -> str:
        """Clean a string to be safe for use as directory name.
        
        Args:
            name: String to clean
            
        Returns:
            Cleaned string safe for filesystem with original capitalization
        """
        import re
        # Remove/replace problematic characters
        cleaned = re.sub(r'[<>:"/\\|?*]', '_', name)
        # Replace spaces with hyphens, preserve capitalization
        cleaned = re.sub(r'\s+', '-', cleaned.strip())
        return cleaned or 'unknown'


class PhotoSorter:
    """Main photo sorting engine."""
    
    def __init__(self, config: Config):
        """Initialize photo sorter.
        
        Args:
            config: Configuration object
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
        
        self.sorting_rule = SortingRule(
            pattern=config.directory_pattern,
            fallback_pattern=config.fallback_pattern
        )
        
        # Statistics
        self.stats = {
            'processed': 0,
            'moved': 0,
            'copied': 0,
            'skipped': 0,
            'errors': 0,
            'enhanced_metadata': 0
        }
    
    def sort_photos(self, source_path: Union[str, Path], 
                   dest_path: Union[str, Path],
                   copy_mode: bool = False,
                   recursive: bool = True) -> Dict[str, int]:
        """Sort photos from source to destination.
        
        Args:
            source_path: Source directory containing photos
            dest_path: Destination directory for sorted photos
            copy_mode: If True, copy files instead of moving them
            recursive: If True, scan source directory recursively
            
        Returns:
            Dictionary with sorting statistics
        """
        source_path = Path(source_path)
        dest_path = Path(dest_path)
        
        if not source_path.exists():
            raise ValueError(f"Source path does not exist: {source_path}")
        
        # Create destination directory if it doesn't exist
        dest_path.mkdir(parents=True, exist_ok=True)
        
        # Find all photo files
        photo_files = self._find_photo_files(source_path, recursive)
        
        for file_path in photo_files:
            try:
                self._process_single_photo(file_path, dest_path, copy_mode)
                self.stats['processed'] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.config.verbosity >= 2:
                    print(f"Error processing {file_path}: {e}")
        
        return self.stats.copy()
    
    def _find_photo_files(self, source_path: Path, recursive: bool = True) -> List[Path]:
        """Find all photo files in source directory.
        
        Args:
            source_path: Directory to scan
            recursive: Whether to scan recursively
            
        Returns:
            List of photo file paths
        """
        photo_files = []
        supported_formats = self.config.supported_formats
        
        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"
        
        for file_path in source_path.glob(pattern):
            if (file_path.is_file() and 
                file_path.suffix.lower() in supported_formats):
                
                # Check file size constraints
                file_size = file_path.stat().st_size
                min_size = self.config.get('file_processing.min_file_size', 0)
                max_size = self.config.get('file_processing.max_file_size', 0)
                
                if file_size < min_size:
                    continue
                
                if max_size > 0 and file_size > max_size * 1024 * 1024:  # Convert MB to bytes
                    continue
                
                photo_files.append(file_path)
        
        return photo_files
    
    def _process_single_photo(self, file_path: Path, dest_base: Path, copy_mode: bool) -> None:
        """Process a single photo file.
        
        Args:
            file_path: Path to photo file
            dest_base: Base destination directory
            copy_mode: Whether to copy instead of move
        """
        if self.config.dry_run:
            self._dry_run_process(file_path, dest_base, copy_mode)
            return
        
        # Extract metadata
        metadata = self.metadata_extractor.extract_metadata(file_path)
        
        # Enhance metadata with directory information
        self._enhance_metadata_from_path(metadata)
        
        # Generate destination path
        dest_dir = self.sorting_rule.generate_path(metadata, dest_base)
        dest_path = dest_dir / file_path.name
        
        # Handle filename conflicts
        dest_path = self._resolve_filename_conflict(dest_path)
        
        # Create destination directory
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Move or copy the file
        if copy_mode:
            shutil.copy2(file_path, dest_path)
            self.stats['copied'] += 1
        else:
            shutil.move(str(file_path), str(dest_path))
            self.stats['moved'] += 1
        
        # Write enhanced metadata if requested
        if (self.config.get('metadata_enhancement.write_location_to_exif', True) or
            self.config.get('metadata_enhancement.write_keywords_to_exif', True)):
            
            backup = self.config.get('metadata_enhancement.backup_originals', True)
            if self.metadata_extractor.write_metadata_to_file(dest_path, metadata, backup):
                self.stats['enhanced_metadata'] += 1
        
        if self.config.verbosity >= 2:
            action = "Copied" if copy_mode else "Moved"
            print(f"{action}: {file_path} -> {dest_path}")
    
    def _enhance_metadata_from_path(self, metadata: PhotoMetadata) -> None:
        """Enhance metadata with information inferred from file path.
        
        Args:
            metadata: Metadata object to enhance
        """
        # Get location inference patterns
        location_patterns = self.config.get_location_patterns()
        inferred_data = self.metadata_extractor.infer_metadata_from_path(
            metadata.file_path, location_patterns
        )
        
        # Add inferred location
        if 'location' in inferred_data:
            metadata.add_inferred_location(inferred_data['location'])
        
        # Extract keywords from path
        keyword_patterns = self.config.get_keyword_patterns()
        keywords = self.metadata_extractor.extract_keywords_from_path(
            metadata.file_path, keyword_patterns
        )
        
        if keywords:
            metadata.add_inferred_keywords(keywords)
    
    def _resolve_filename_conflict(self, dest_path: Path) -> Path:
        """Resolve filename conflicts by adding numbers.
        
        Args:
            dest_path: Desired destination path
            
        Returns:
            Path that doesn't conflict with existing files
        """
        if not dest_path.exists():
            return dest_path
        
        stem = dest_path.stem
        suffix = dest_path.suffix
        parent = dest_path.parent
        counter = 1
        
        while True:
            new_name = f"{stem}_{counter:03d}{suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1
    
    def _dry_run_process(self, file_path: Path, dest_base: Path, copy_mode: bool) -> None:
        """Process file in dry run mode (show what would be done).
        
        Args:
            file_path: Source file path
            dest_base: Destination base directory
            copy_mode: Whether copying or moving
        """
        # Extract metadata
        metadata = self.metadata_extractor.extract_metadata(file_path)
        
        # Enhance metadata with directory information
        self._enhance_metadata_from_path(metadata)
        
        # Generate destination path
        dest_dir = self.sorting_rule.generate_path(metadata, dest_base)
        dest_path = dest_dir / file_path.name
        
        # Show what would be done
        action = "COPY" if copy_mode else "MOVE"
        print(f"[DRY RUN] {action}: {file_path} -> {dest_path}")
        
        if metadata.inferred_data:
            print(f"  Inferred data: {metadata.inferred_data}")
        
        self.stats['processed'] += 1
    
    def scan_photos(self, source_path: Union[str, Path], 
                   recursive: bool = True) -> Dict[str, any]:
        """Scan directory and return information about photos.
        
        Args:
            source_path: Directory to scan
            recursive: Whether to scan recursively
            
        Returns:
            Dictionary with scan results
        """
        source_path = Path(source_path)
        
        if not source_path.exists():
            raise ValueError(f"Source path does not exist: {source_path}")
        
        # Find all photo files
        photo_files = self._find_photo_files(source_path, recursive)
        
        # Analyze files
        analysis = {
            'total_files': len(photo_files),
            'total_size_bytes': 0,
            'file_types': {},
            'date_range': {'earliest': None, 'latest': None},
            'has_gps': 0,
            'has_camera_info': 0,
            'inferred_locations': set(),
            'sample_files': []
        }
        
        for i, file_path in enumerate(photo_files):
            try:
                file_size = file_path.stat().st_size
                analysis['total_size_bytes'] += file_size
                
                # Count file types
                ext = file_path.suffix.lower()
                analysis['file_types'][ext] = analysis['file_types'].get(ext, 0) + 1
                
                # Extract metadata for detailed analysis (sample only for performance)
                if i < 100:  # Only analyze first 100 files in detail
                    metadata = self.metadata_extractor.extract_metadata(file_path)
                    self._enhance_metadata_from_path(metadata)
                    
                    # Date range
                    if metadata.datetime_taken:
                        if not analysis['date_range']['earliest']:
                            analysis['date_range']['earliest'] = metadata.datetime_taken
                            analysis['date_range']['latest'] = metadata.datetime_taken
                        else:
                            if metadata.datetime_taken < analysis['date_range']['earliest']:
                                analysis['date_range']['earliest'] = metadata.datetime_taken
                            if metadata.datetime_taken > analysis['date_range']['latest']:
                                analysis['date_range']['latest'] = metadata.datetime_taken
                    
                    # GPS and camera info
                    if metadata.location:
                        analysis['has_gps'] += 1
                    
                    if metadata.camera_info:
                        analysis['has_camera_info'] += 1
                    
                    # Inferred locations
                    if 'location' in metadata.inferred_data:
                        analysis['inferred_locations'].add(metadata.inferred_data['location'])
                    
                    # Sample files
                    if len(analysis['sample_files']) < 10:
                        analysis['sample_files'].append({
                            'path': str(file_path),
                            'size': file_size,
                            'datetime': metadata.datetime_taken.isoformat() if metadata.datetime_taken else None,
                            'inferred_location': metadata.inferred_data.get('location')
                        })
                
            except Exception as e:
                if self.config.verbosity >= 2:
                    print(f"Error analyzing {file_path}: {e}")
        
        # Convert set to list for JSON serialization
        analysis['inferred_locations'] = list(analysis['inferred_locations'])
        
        return analysis