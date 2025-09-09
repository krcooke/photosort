"""Duplicate photo detection using perceptual hashing."""

import hashlib
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None

try:
    import imagehash
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False
    imagehash = None


class DuplicateCandidate:
    """Represents a potential duplicate photo."""
    
    def __init__(self, file_path: Union[str, Path], file_size: int = 0, 
                 image_hash: Optional[str] = None):
        """Initialize duplicate candidate.
        
        Args:
            file_path: Path to the image file
            file_size: Size of the file in bytes
            image_hash: Perceptual hash of the image
        """
        self.file_path = Path(file_path)
        self.file_size = file_size
        self.image_hash = image_hash
        self.md5_hash: Optional[str] = None
        self._image_dimensions: Optional[Tuple[int, int]] = None
        
        # Quality metrics (calculated lazily)
        self._quality_metrics: Optional[Dict[str, float]] = None
    
    @property
    def file_name(self) -> str:
        """Get the file name."""
        return self.file_path.name
    
    @property
    def image_dimensions(self) -> Optional[Tuple[int, int]]:
        """Get image dimensions (width, height)."""
        if self._image_dimensions is None and PIL_AVAILABLE:
            try:
                with Image.open(self.file_path) as img:
                    self._image_dimensions = img.size
            except Exception:
                self._image_dimensions = (0, 0)
        return self._image_dimensions
    
    @property
    def image_area(self) -> int:
        """Get total image area in pixels."""
        if self.image_dimensions:
            return self.image_dimensions[0] * self.image_dimensions[1]
        return 0
    
    def get_md5_hash(self) -> str:
        """Calculate MD5 hash of the file."""
        if self.md5_hash is None:
            try:
                with open(self.file_path, 'rb') as f:
                    self.md5_hash = hashlib.md5(f.read()).hexdigest()
            except Exception:
                self.md5_hash = ""
        return self.md5_hash
    
    @property
    def quality_metrics(self) -> Dict[str, float]:
        """Get quality metrics for the image."""
        if self._quality_metrics is None:
            self._quality_metrics = self._calculate_quality_metrics()
        return self._quality_metrics
    
    def _calculate_quality_metrics(self) -> Dict[str, float]:
        """Calculate image quality metrics."""
        if not PIL_AVAILABLE:
            return {'sharpness': 0, 'brightness': 0, 'contrast': 0, 'color_richness': 0}
        
        try:
            with Image.open(self.file_path) as img:
                # Convert to RGB if needed
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize to smaller image for faster analysis (max 512x512)
                max_size = 512
                if img.size[0] > max_size or img.size[1] > max_size:
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # Convert to numpy array for analysis
                img_array = np.array(img)
                
                # Calculate sharpness using Laplacian variance
                sharpness = self._calculate_sharpness(img_array)
                
                # Calculate brightness (average luminance)
                brightness = self._calculate_brightness(img_array)
                
                # Calculate contrast (std deviation of luminance)
                contrast = self._calculate_contrast(img_array)
                
                # Calculate color richness (color histogram spread)
                color_richness = self._calculate_color_richness(img_array)
                
                return {
                    'sharpness': sharpness,
                    'brightness': brightness,
                    'contrast': contrast,
                    'color_richness': color_richness
                }
        except Exception:
            # Return default values if analysis fails
            return {'sharpness': 0, 'brightness': 0, 'contrast': 0, 'color_richness': 0}
    
    def _calculate_sharpness(self, img_array: np.ndarray) -> float:
        """Calculate image sharpness using gradient magnitude."""
        try:
            # Convert to grayscale
            gray = np.dot(img_array[...,:3], [0.2989, 0.5870, 0.1140])
            
            # Calculate gradients using numpy (much faster than manual convolution)
            grad_x = np.abs(np.diff(gray, axis=1))
            grad_y = np.abs(np.diff(gray, axis=0))
            
            # Calculate mean gradient magnitude as sharpness measure
            sharpness = float(np.mean(grad_x) + np.mean(grad_y))
            return sharpness
        except Exception:
            return 0.0
    
    def _calculate_brightness(self, img_array: np.ndarray) -> float:
        """Calculate average brightness (luminance)."""
        try:
            # Convert to grayscale and get mean
            gray = np.dot(img_array[...,:3], [0.2989, 0.5870, 0.1140])
            return float(np.mean(gray))
        except Exception:
            return 0.0
    
    def _calculate_contrast(self, img_array: np.ndarray) -> float:
        """Calculate contrast (standard deviation of luminance)."""
        try:
            # Convert to grayscale and get std deviation
            gray = np.dot(img_array[...,:3], [0.2989, 0.5870, 0.1140])
            return float(np.std(gray))
        except Exception:
            return 0.0
    
    def _calculate_color_richness(self, img_array: np.ndarray) -> float:
        """Calculate color richness (color histogram spread)."""
        try:
            # Calculate histograms for each RGB channel
            hist_r = np.histogram(img_array[:,:,0], bins=64, range=(0, 255))[0]
            hist_g = np.histogram(img_array[:,:,1], bins=64, range=(0, 255))[0]
            hist_b = np.histogram(img_array[:,:,2], bins=64, range=(0, 255))[0]
            
            # Calculate entropy-like measure of color distribution
            total_pixels = img_array.shape[0] * img_array.shape[1]
            
            entropy = 0.0
            for hist in [hist_r, hist_g, hist_b]:
                for count in hist:
                    if count > 0:
                        p = count / total_pixels
                        entropy -= p * np.log2(p + 1e-10)  # Add small epsilon to avoid log(0)
            
            return float(entropy / 3)  # Average across RGB channels
        except Exception:
            return 0.0
    
    def is_better_quality_than(self, other: 'DuplicateCandidate') -> bool:
        """Determine if this image is better quality than another.
        
        Args:
            other: Other duplicate candidate to compare with
            
        Returns:
            True if this image is considered better quality
        """
        # Get quality metrics for both images
        self_metrics = self.quality_metrics
        other_metrics = other.quality_metrics
        
        # Calculate weighted quality scores
        self_score = self._calculate_quality_score(self_metrics)
        other_score = self._calculate_quality_score(other_metrics)
        
        # If quality scores are significantly different, use quality
        if abs(self_score - other_score) > 0.1:  # 10% difference threshold
            return self_score > other_score
        
        # Fall back to file size (usually indicates less compression)
        if abs(self.file_size - other.file_size) > 1024:  # 1KB threshold
            return self.file_size > other.file_size
        
        # Fall back to image dimensions
        self_area = self.image_area
        other_area = other.image_area
        if abs(self_area - other_area) > 10000:  # 100x100 pixel threshold
            return self_area > other_area
        
        # Final fallback: prefer by name (arbitrary but consistent)
        return str(self.file_path) < str(other.file_path)
    
    def _calculate_quality_score(self, metrics: Dict[str, float]) -> float:
        """Calculate overall quality score from individual metrics.
        
        Args:
            metrics: Dictionary of quality metrics
            
        Returns:
            Overall quality score (0-1, higher is better)
        """
        # Normalize and weight different metrics
        
        # Sharpness is the most important for detecting blur (weight: 40%)
        # Higher sharpness = better
        sharpness_norm = min(metrics['sharpness'] / 50.0, 1.0)  # Normalize to 0-1 (adjusted for gradient method)
        
        # Contrast is important for image quality (weight: 25%)
        # Higher contrast = better (but not too high)
        contrast_norm = min(metrics['contrast'] / 100.0, 1.0)  # Normalize to 0-1
        
        # Brightness should be balanced - not too dark, not too bright (weight: 15%)
        # Optimal brightness around 100-150 (out of 255)
        brightness = metrics['brightness']
        if brightness < 50:  # Too dark
            brightness_norm = brightness / 50.0
        elif brightness > 200:  # Too bright
            brightness_norm = (255 - brightness) / 55.0
        else:  # Good range
            brightness_norm = 1.0
        
        # Color richness indicates a vibrant image (weight: 20%)
        # Higher entropy = more colorful
        color_norm = min(metrics['color_richness'] / 8.0, 1.0)  # Normalize to 0-1
        
        # Calculate weighted score
        quality_score = (
            0.40 * sharpness_norm +
            0.25 * contrast_norm + 
            0.15 * brightness_norm +
            0.20 * color_norm
        )
        
        return quality_score


class DuplicateGroup:
    """Group of duplicate photos."""
    
    def __init__(self, candidates: List[DuplicateCandidate]):
        """Initialize duplicate group.
        
        Args:
            candidates: List of duplicate candidates
        """
        self.candidates = candidates
        self._best_candidate: Optional[DuplicateCandidate] = None
    
    @property
    def size(self) -> int:
        """Number of duplicates in this group."""
        return len(self.candidates)
    
    @property
    def best_candidate(self) -> DuplicateCandidate:
        """Get the best quality candidate from the group."""
        if self._best_candidate is None:
            self._best_candidate = max(self.candidates, 
                                     key=lambda c: (c.file_size, c.image_area))
        return self._best_candidate
    
    @property
    def duplicates_to_remove(self) -> List[DuplicateCandidate]:
        """Get list of duplicate candidates that should be removed."""
        best = self.best_candidate
        return [c for c in self.candidates if c != best]
    
    def get_total_size(self) -> int:
        """Get total size of all files in the group."""
        return sum(c.file_size for c in self.candidates)
    
    def get_wasted_space(self) -> int:
        """Get amount of space that could be saved by removing duplicates."""
        return sum(c.file_size for c in self.duplicates_to_remove)


class DuplicateDetector:
    """Detect duplicate photos using perceptual hashing."""
    
    def __init__(self, algorithm: str = 'dhash', threshold: int = 10):
        """Initialize duplicate detector.
        
        Args:
            algorithm: Hashing algorithm ('dhash', 'phash', 'ahash', 'whash', 'colorhash')
            threshold: Hamming distance threshold for considering images similar
        """
        self.algorithm = algorithm.lower()
        self.threshold = threshold
        self.available_algorithms = self._get_available_algorithms()
        
        if self.algorithm not in self.available_algorithms:
            raise ValueError(f"Algorithm '{algorithm}' not available. "
                           f"Available: {list(self.available_algorithms.keys())}")
    
    def _get_available_algorithms(self) -> Dict[str, callable]:
        """Get available hashing algorithms."""
        algorithms = {}
        
        if IMAGEHASH_AVAILABLE and imagehash:
            algorithms.update({
                'dhash': imagehash.dhash,
                'phash': imagehash.phash,
                'ahash': imagehash.average_hash,
                'whash': imagehash.whash,
            })
            
            # ColorHash might not be available in all imagehash versions
            if hasattr(imagehash, 'colorhash'):
                algorithms['colorhash'] = imagehash.colorhash
        
        return algorithms
    
    def calculate_hash(self, image_path: Union[str, Path]) -> Optional[str]:
        """Calculate perceptual hash for an image.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Hash string or None if failed
        """
        if not IMAGEHASH_AVAILABLE or not PIL_AVAILABLE:
            return None
        
        try:
            with Image.open(image_path) as img:
                hash_func = self.available_algorithms[self.algorithm]
                img_hash = hash_func(img)
                return str(img_hash)
        except Exception:
            return None
    
    def calculate_hamming_distance(self, hash1: str, hash2: str) -> int:
        """Calculate Hamming distance between two hashes.
        
        Args:
            hash1: First hash string
            hash2: Second hash string
            
        Returns:
            Hamming distance (number of different bits)
        """
        if not hash1 or not hash2 or len(hash1) != len(hash2):
            return float('inf')
        
        try:
            # Convert hex strings to integers and XOR them
            int1 = int(hash1, 16)
            int2 = int(hash2, 16)
            xor_result = int1 ^ int2
            
            # Count number of 1s in binary representation
            return bin(xor_result).count('1')
        except (ValueError, TypeError):
            return float('inf')
    
    def are_similar(self, hash1: str, hash2: str) -> bool:
        """Check if two hashes represent similar images.
        
        Args:
            hash1: First hash string
            hash2: Second hash string
            
        Returns:
            True if images are considered similar
        """
        distance = self.calculate_hamming_distance(hash1, hash2)
        return distance <= self.threshold
    
    def scan_directory(self, directory: Union[str, Path], 
                      supported_formats: List[str],
                      recursive: bool = True) -> List[DuplicateCandidate]:
        """Scan directory for image files and create candidates.
        
        Args:
            directory: Directory to scan
            supported_formats: List of supported file extensions
            recursive: Whether to scan recursively
            
        Returns:
            List of duplicate candidates
        """
        directory = Path(directory)
        candidates = []
        
        if not directory.exists():
            return candidates
        
        # Get pattern for supported formats
        pattern = "**/*" if recursive else "*"
        
        for file_path in directory.glob(pattern):
            if not file_path.is_file():
                continue
            
            if file_path.suffix.lower() not in supported_formats:
                continue
            
            try:
                file_size = file_path.stat().st_size
                image_hash = self.calculate_hash(file_path)
                
                if image_hash:  # Only add if we could calculate hash
                    candidate = DuplicateCandidate(file_path, file_size, image_hash)
                    candidates.append(candidate)
                    
            except Exception:
                # Skip files that can't be processed
                continue
        
        return candidates
    
    def find_duplicates(self, candidates: List[DuplicateCandidate]) -> List[DuplicateGroup]:
        """Find duplicate groups among candidates.
        
        Args:
            candidates: List of duplicate candidates to analyze
            
        Returns:
            List of duplicate groups
        """
        groups = []
        processed: Set[int] = set()
        
        for i, candidate1 in enumerate(candidates):
            if i in processed or not candidate1.image_hash:
                continue
            
            # Find all similar images to this candidate
            group_candidates = [candidate1]
            processed.add(i)
            
            for j, candidate2 in enumerate(candidates[i + 1:], i + 1):
                if j in processed or not candidate2.image_hash:
                    continue
                
                if self.are_similar(candidate1.image_hash, candidate2.image_hash):
                    group_candidates.append(candidate2)
                    processed.add(j)
            
            # Only create group if we have actual duplicates
            if len(group_candidates) > 1:
                groups.append(DuplicateGroup(group_candidates))
        
        return groups
    
    def find_exact_duplicates(self, candidates: List[DuplicateCandidate]) -> List[DuplicateGroup]:
        """Find exact duplicate files based on MD5 hash.
        
        Args:
            candidates: List of duplicate candidates to analyze
            
        Returns:
            List of exact duplicate groups
        """
        hash_to_candidates: Dict[str, List[DuplicateCandidate]] = {}
        
        for candidate in candidates:
            md5_hash = candidate.get_md5_hash()
            if md5_hash:
                if md5_hash not in hash_to_candidates:
                    hash_to_candidates[md5_hash] = []
                hash_to_candidates[md5_hash].append(candidate)
        
        # Only keep groups with multiple files
        groups = []
        for candidates_list in hash_to_candidates.values():
            if len(candidates_list) > 1:
                groups.append(DuplicateGroup(candidates_list))
        
        return groups
    
    def get_statistics(self, groups: List[DuplicateGroup]) -> Dict[str, any]:
        """Get statistics about duplicate detection results.
        
        Args:
            groups: List of duplicate groups
            
        Returns:
            Dictionary with statistics
        """
        total_files = sum(group.size for group in groups)
        total_duplicates = sum(len(group.duplicates_to_remove) for group in groups)
        total_size = sum(group.get_total_size() for group in groups)
        wasted_space = sum(group.get_wasted_space() for group in groups)
        
        return {
            'duplicate_groups': len(groups),
            'total_files_in_groups': total_files,
            'duplicate_files': total_duplicates,
            'original_files': total_files - total_duplicates,
            'total_size_bytes': total_size,
            'wasted_space_bytes': wasted_space,
            'space_savings_percent': (wasted_space / total_size * 100) if total_size > 0 else 0
        }