"""Photo metadata extraction and enhancement."""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    TAGS = {}
    GPSTAGS = {}

try:
    import exifread
    EXIFREAD_AVAILABLE = True
except ImportError:
    EXIFREAD_AVAILABLE = False
    exifread = None

try:
    import piexif
    PIEXIF_AVAILABLE = True
except ImportError:
    PIEXIF_AVAILABLE = False
    piexif = None


class ReverseGeocoder:
    """Reverse geocoding service for GPS coordinates."""
    
    def __init__(self, cache_file: Optional[str] = None, rate_limit: float = 1.0):
        """Initialize reverse geocoder.
        
        Args:
            cache_file: Path to cache file for storing results
            rate_limit: Minimum seconds between API calls
        """
        self.rate_limit = rate_limit
        self.last_request_time = 0
        self.cache_file = cache_file
        self.cache: Dict[str, str] = {}
        
        if cache_file:
            self._load_cache()
    
    def _load_cache(self) -> None:
        """Load cache from file."""
        if self.cache_file and Path(self.cache_file).exists():
            try:
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.cache = {}
    
    def _save_cache(self) -> None:
        """Save cache to file."""
        if self.cache_file:
            try:
                cache_path = Path(self.cache_file)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                with open(cache_path, 'w') as f:
                    json.dump(self.cache, f, indent=2)
            except IOError:
                pass  # Silent failure for cache save
    
    def _rate_limit_wait(self) -> None:
        """Wait if necessary to respect rate limits."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()
    
    def lookup_location(self, latitude: float, longitude: float) -> Optional[str]:
        """Look up location name for GPS coordinates.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Location name (city, town, etc.) or None if lookup fails
        """
        # Create cache key (rounded to ~1km precision for better cache hits)
        cache_key = f"{latitude:.2f},{longitude:.2f}"
        
        # Check cache first
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # Rate limiting
            self._rate_limit_wait()
            
            # Use OpenStreetMap Nominatim service (free, no API key required)
            params = {
                'lat': latitude,
                'lon': longitude,
                'format': 'json',
                'zoom': 10,  # City/town level
                'addressdetails': 1
            }
            
            url = f"https://nominatim.openstreetmap.org/reverse?{urlencode(params)}"
            
            with urlopen(url, timeout=10) as response:
                if response.getcode() == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    location = self._extract_location_name(data)
                    
                    # Cache the result
                    self.cache[cache_key] = location
                    self._save_cache()
                    
                    return location
                    
        except (URLError, HTTPError, json.JSONDecodeError, KeyError) as e:
            # Silent failure for geocoding - just return None
            pass
        
        # Cache negative results to avoid repeated failed lookups
        self.cache[cache_key] = None
        self._save_cache()
        return None
    
    def _extract_location_name(self, geocode_data: Dict[str, Any]) -> Optional[str]:
        """Extract the best location name from geocoding response.
        
        Args:
            geocode_data: Response data from geocoding service
            
        Returns:
            Best location name found
        """
        if 'address' not in geocode_data:
            return None
        
        address = geocode_data['address']
        
        # Priority order for location names (most specific to least)
        location_fields = [
            'city', 'town', 'village', 'hamlet',
            'municipality', 'county', 'state_district',
            'state', 'region', 'country'
        ]
        
        for field in location_fields:
            if field in address and address[field]:
                return address[field].strip()
        
        return None


class PhotoMetadata:
    """Container for photo metadata information."""
    
    def __init__(self, file_path: Union[str, Path]):
        """Initialize metadata container.
        
        Args:
            file_path: Path to the photo file
        """
        self.file_path = Path(file_path)
        self.exif_data: Dict[str, Any] = {}
        self.inferred_data: Dict[str, Any] = {}
        self._raw_exif: Dict[str, Any] = {}
    
    @property
    def datetime_taken(self) -> Optional[datetime]:
        """Get the datetime when photo was taken."""
        # Try various EXIF datetime fields
        for field in ['DateTime', 'DateTimeOriginal', 'DateTimeDigitized']:
            if field in self.exif_data:
                try:
                    return datetime.strptime(self.exif_data[field], '%Y:%m:%d %H:%M:%S')
                except (ValueError, TypeError):
                    continue
        
        # Fall back to file modification time
        if self.file_path.exists():
            return datetime.fromtimestamp(self.file_path.stat().st_mtime)
        
        return None
    
    @property
    def location(self) -> Optional[Dict[str, float]]:
        """Get GPS location data."""
        # Try PIL format first (structured GPSInfo)
        if 'GPSInfo' in self.exif_data and isinstance(self.exif_data['GPSInfo'], dict):
            gps_info = self.exif_data['GPSInfo']
            
            def convert_to_degrees(value: Tuple[float, float, float]) -> float:
                """Convert GPS coordinates to decimal degrees."""
                d, m, s = value
                return d + (m / 60.0) + (s / 3600.0)
            
            try:
                lat = convert_to_degrees(gps_info.get('GPSLatitude', (0, 0, 0)))
                lon = convert_to_degrees(gps_info.get('GPSLongitude', (0, 0, 0)))
                
                if gps_info.get('GPSLatitudeRef') == 'S':
                    lat = -lat
                if gps_info.get('GPSLongitudeRef') == 'W':
                    lon = -lon
                
                return {'latitude': lat, 'longitude': lon}
            except (KeyError, TypeError, ValueError):
                pass
        
        # Try ExifRead format (individual GPS tags as strings)
        elif ('GPSLatitude' in self.exif_data and 
              'GPSLongitude' in self.exif_data):
            
            def parse_gps_string(gps_str: str) -> Tuple[float, float, float]:
                """Parse GPS coordinate string format like '[50, 40, 781617/25000]'."""
                # Remove brackets and split
                coords = gps_str.strip('[]').split(', ')
                d = float(coords[0])
                m = float(coords[1])
                # Handle fraction format for seconds
                if '/' in coords[2]:
                    num, den = coords[2].split('/')
                    s = float(num) / float(den)
                else:
                    s = float(coords[2])
                return d, m, s
            
            def convert_to_degrees(dms: Tuple[float, float, float]) -> float:
                """Convert GPS coordinates to decimal degrees."""
                d, m, s = dms
                return d + (m / 60.0) + (s / 3600.0)
            
            try:
                lat_dms = parse_gps_string(self.exif_data['GPSLatitude'])
                lon_dms = parse_gps_string(self.exif_data['GPSLongitude'])
                
                lat = convert_to_degrees(lat_dms)
                lon = convert_to_degrees(lon_dms)
                
                if self.exif_data.get('GPSLatitudeRef') == 'S':
                    lat = -lat
                if self.exif_data.get('GPSLongitudeRef') == 'W':
                    lon = -lon
                
                return {'latitude': lat, 'longitude': lon}
            except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
                pass
        
        return None
    
    @property
    def gps_location_name(self) -> Optional[str]:
        """Get location name from GPS coordinates if available."""
        return self.inferred_data.get('gps_location_name')
    
    @property
    def camera_info(self) -> Dict[str, str]:
        """Get camera information."""
        info = {}
        for field in ['Make', 'Model', 'LensMake', 'LensModel']:
            if field in self.exif_data:
                info[field.lower()] = str(self.exif_data[field])
        return info
    
    @property
    def keywords(self) -> List[str]:
        """Get keywords/tags from metadata and inferred data."""
        keywords = []
        
        # From EXIF
        if 'Keywords' in self.exif_data:
            keywords.extend(self.exif_data['Keywords'])
        
        # From inferred data
        if 'keywords' in self.inferred_data:
            keywords.extend(self.inferred_data['keywords'])
        
        return list(set(keywords))  # Remove duplicates
    
    def add_inferred_location(self, location: str) -> None:
        """Add inferred location information.
        
        Args:
            location: Location name inferred from directory structure
        """
        self.inferred_data['location'] = location
    
    def add_inferred_keywords(self, keywords: List[str]) -> None:
        """Add inferred keywords.
        
        Args:
            keywords: Keywords inferred from directory structure
        """
        if 'keywords' not in self.inferred_data:
            self.inferred_data['keywords'] = []
        self.inferred_data['keywords'].extend(keywords)
        self.inferred_data['keywords'] = list(set(self.inferred_data['keywords']))


class MetadataExtractor:
    """Extract and enhance photo metadata."""
    
    def __init__(self, enable_geocoding: bool = True, geocoding_cache_file: Optional[str] = None):
        """Initialize metadata extractor.
        
        Args:
            enable_geocoding: Whether to enable reverse geocoding for GPS coordinates
            geocoding_cache_file: Path to cache file for geocoding results
        """
        self.available_libs = {
            'pil': PIL_AVAILABLE,
            'exifread': EXIFREAD_AVAILABLE,
            'piexif': PIEXIF_AVAILABLE
        }
        
        self.enable_geocoding = enable_geocoding
        self.geocoder = None
        
        if enable_geocoding:
            cache_file = geocoding_cache_file or str(Path.home() / '.photosort_geocoding_cache.json')
            self.geocoder = ReverseGeocoder(cache_file=cache_file)
    
    def extract_metadata(self, file_path: Union[str, Path]) -> PhotoMetadata:
        """Extract metadata from photo file.
        
        Args:
            file_path: Path to photo file
            
        Returns:
            PhotoMetadata object with extracted data
        """
        metadata = PhotoMetadata(file_path)
        file_path = Path(file_path)
        
        if not file_path.exists():
            return metadata
        
        # Try PIL first (most common)
        if PIL_AVAILABLE:
            try:
                metadata.exif_data = self._extract_with_pil(file_path)
            except Exception:
                pass
        
        # Always try ExifRead as well (better GPS support)
        if EXIFREAD_AVAILABLE:
            try:
                exif_dict = self._extract_with_exifread(file_path)
                # Merge ExifRead data with PIL data (ExifRead takes priority for GPS)
                for key, value in exif_dict.items():
                    if key not in metadata.exif_data or 'GPS' in key:
                        metadata.exif_data[key] = value
            except Exception:
                pass
        
        # Perform reverse geocoding if GPS coordinates are available
        if self.enable_geocoding and self.geocoder and metadata.location:
            try:
                location_name = self.geocoder.lookup_location(
                    metadata.location['latitude'],
                    metadata.location['longitude']
                )
                if location_name:
                    metadata.inferred_data['gps_location_name'] = location_name
            except Exception:
                # Silent failure for geocoding
                pass
        
        return metadata
    
    def _extract_with_pil(self, file_path: Path) -> Dict[str, Any]:
        """Extract EXIF data using PIL.
        
        Args:
            file_path: Path to image file
            
        Returns:
            Dictionary of EXIF data
        """
        if not PIL_AVAILABLE:
            return {}
        
        exif_dict = {}
        
        try:
            with Image.open(file_path) as img:
                exif = img.getexif()
                
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    
                    # Handle GPS info specially
                    if tag == 'GPSInfo':
                        gps_dict = {}
                        for gps_tag_id, gps_value in value.items():
                            gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                            gps_dict[gps_tag] = gps_value
                        exif_dict[tag] = gps_dict
                    else:
                        exif_dict[tag] = value
                        
        except Exception:
            # Silent failure, return empty dict
            pass
        
        return exif_dict
    
    def _extract_with_exifread(self, file_path: Path) -> Dict[str, Any]:
        """Extract EXIF data using ExifRead.
        
        Args:
            file_path: Path to image file
            
        Returns:
            Dictionary of EXIF data
        """
        if not EXIFREAD_AVAILABLE:
            return {}
        
        exif_dict = {}
        
        try:
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)
                
                for tag_name, tag_value in tags.items():
                    if tag_name not in ['JPEGThumbnail', 'TIFFThumbnail', 'Filename']:
                        # Convert tag name to PIL-style
                        clean_name = tag_name.split()[-1] if ' ' in tag_name else tag_name
                        exif_dict[clean_name] = str(tag_value)
                        
        except Exception:
            # Silent failure, return empty dict
            pass
        
        return exif_dict
    
    def infer_metadata_from_path(self, file_path: Union[str, Path], 
                                patterns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Infer metadata from file path using regex patterns.
        
        Args:
            file_path: Path to analyze
            patterns: List of pattern dictionaries with 'pattern' and 'priority' keys
            
        Returns:
            Dictionary of inferred metadata
        """
        file_path = Path(file_path)
        inferred = {}
        
        # Sort patterns by priority (lower number = higher priority)
        sorted_patterns = sorted(patterns, key=lambda x: x.get('priority', 999))
        
        for pattern_dict in sorted_patterns:
            pattern = pattern_dict.get('pattern', '')
            
            try:
                match = re.search(pattern, str(file_path), re.IGNORECASE)
                if match:
                    groups = match.groupdict()
                    for key, value in groups.items():
                        if value and key not in inferred:  # Don't overwrite higher priority matches
                            inferred[key] = value
            except re.error:
                # Skip invalid regex patterns
                continue
        
        return inferred
    
    def extract_keywords_from_path(self, file_path: Union[str, Path],
                                 keyword_patterns: List[Dict[str, Any]]) -> List[str]:
        """Extract keywords from file path using patterns.
        
        Args:
            file_path: Path to analyze
            keyword_patterns: List of keyword pattern dictionaries
            
        Returns:
            List of extracted keywords
        """
        file_path = Path(file_path)
        keywords = []
        
        for pattern_dict in keyword_patterns:
            pattern = pattern_dict.get('pattern', '')
            tag_type = pattern_dict.get('tag', 'general')
            
            try:
                match = re.search(pattern, str(file_path), re.IGNORECASE)
                if match:
                    groups = match.groupdict()
                    for key, value in groups.items():
                        if value:
                            # Clean up the value
                            clean_value = re.sub(r'[_\-]', ' ', value).strip().title()
                            if clean_value:
                                keywords.append(f"{tag_type}:{clean_value}")
            except re.error:
                # Skip invalid regex patterns
                continue
        
        return keywords
    
    def write_metadata_to_file(self, file_path: Union[str, Path], 
                             metadata: PhotoMetadata,
                             backup: bool = True) -> bool:
        """Write enhanced metadata back to photo file.
        
        Args:
            file_path: Path to photo file
            metadata: PhotoMetadata with enhanced data
            backup: Whether to create backup of original file
            
        Returns:
            True if successful, False otherwise
        """
        if not PIEXIF_AVAILABLE:
            return False
        
        file_path = Path(file_path)
        
        if backup:
            backup_path = file_path.with_suffix(file_path.suffix + '.backup')
            try:
                backup_path.write_bytes(file_path.read_bytes())
            except Exception:
                return False
        
        try:
            # Load existing EXIF data
            exif_dict = piexif.load(str(file_path))
            
            # Add inferred location as keywords if no GPS data
            if metadata.inferred_data.get('location') and not metadata.location:
                location = metadata.inferred_data['location']
                if '0th' not in exif_dict:
                    exif_dict['0th'] = {}
                
                # Add location as a keyword/tag
                existing_keywords = exif_dict['0th'].get(piexif.ImageIFD.XPKeywords, b'')
                if existing_keywords:
                    keywords = existing_keywords.decode('utf-16le', errors='ignore')
                    keywords += f'; {location}'
                else:
                    keywords = location
                
                exif_dict['0th'][piexif.ImageIFD.XPKeywords] = keywords.encode('utf-16le')
            
            # Add other inferred keywords
            if metadata.inferred_data.get('keywords'):
                if '0th' not in exif_dict:
                    exif_dict['0th'] = {}
                
                existing_keywords = exif_dict['0th'].get(piexif.ImageIFD.XPKeywords, b'')
                if existing_keywords:
                    keywords = existing_keywords.decode('utf-16le', errors='ignore')
                else:
                    keywords = ''
                
                for keyword in metadata.inferred_data['keywords']:
                    if keyword not in keywords:
                        keywords += f'; {keyword}' if keywords else keyword
                
                exif_dict['0th'][piexif.ImageIFD.XPKeywords] = keywords.encode('utf-16le')
            
            # Write back to file
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, str(file_path))
            
            return True
            
        except Exception:
            # Restore backup if write failed
            if backup:
                backup_path = file_path.with_suffix(file_path.suffix + '.backup')
                if backup_path.exists():
                    try:
                        file_path.write_bytes(backup_path.read_bytes())
                        backup_path.unlink()
                    except Exception:
                        pass
            return False