"""Utility functions for PhotoSort."""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Union


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string (e.g., "1.5 MB")
    """
    if size_bytes == 0:
        return "0 B"
    
    size_units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024 and unit_index < len(size_units) - 1:
        size /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(size)} {size_units[unit_index]}"
    else:
        return f"{size:.1f} {size_units[unit_index]}"


def safe_move_file(source: Union[str, Path], dest: Union[str, Path]) -> bool:
    """Safely move a file with error handling.
    
    Args:
        source: Source file path
        dest: Destination file path
        
    Returns:
        True if successful, False otherwise
    """
    source_path = Path(source)
    dest_path = Path(dest)
    
    try:
        # Create destination directory if needed
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Move the file
        shutil.move(str(source_path), str(dest_path))
        return True
        
    except Exception:
        return False


def safe_copy_file(source: Union[str, Path], dest: Union[str, Path]) -> bool:
    """Safely copy a file with error handling.
    
    Args:
        source: Source file path
        dest: Destination file path
        
    Returns:
        True if successful, False otherwise
    """
    source_path = Path(source)
    dest_path = Path(dest)
    
    try:
        # Create destination directory if needed
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy the file
        shutil.copy2(str(source_path), str(dest_path))
        return True
        
    except Exception:
        return False


def get_available_space(path: Union[str, Path]) -> int:
    """Get available disk space at given path.
    
    Args:
        path: Path to check
        
    Returns:
        Available space in bytes
    """
    try:
        stat = shutil.disk_usage(str(path))
        return stat.free
    except Exception:
        return 0


def validate_directory_path(path: Union[str, Path], create: bool = False) -> bool:
    """Validate that a directory path exists or can be created.
    
    Args:
        path: Directory path to validate
        create: Whether to create directory if it doesn't exist
        
    Returns:
        True if valid/created, False otherwise
    """
    path = Path(path)
    
    try:
        if path.exists():
            return path.is_dir()
        elif create:
            path.mkdir(parents=True, exist_ok=True)
            return True
        else:
            return False
    except Exception:
        return False


def clean_filename(filename: str) -> str:
    """Clean filename by removing/replacing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Cleaned filename safe for filesystem
    """
    # Characters that are problematic on various filesystems
    invalid_chars = '<>:"/\\|?*'
    
    cleaned = filename
    for char in invalid_chars:
        cleaned = cleaned.replace(char, '_')
    
    # Remove leading/trailing spaces and dots
    cleaned = cleaned.strip('. ')
    
    # Ensure we don't create empty names
    if not cleaned:
        cleaned = "unnamed"
    
    return cleaned


def find_unique_filename(directory: Union[str, Path], filename: str) -> str:
    """Find a unique filename in the given directory.
    
    Args:
        directory: Directory to check
        filename: Desired filename
        
    Returns:
        Unique filename
    """
    directory = Path(directory)
    base_path = directory / filename
    
    if not base_path.exists():
        return filename
    
    # Extract name and extension
    name_path = Path(filename)
    stem = name_path.stem
    suffix = name_path.suffix
    
    counter = 1
    while True:
        new_filename = f"{stem}_{counter:03d}{suffix}"
        new_path = directory / new_filename
        if not new_path.exists():
            return new_filename
        counter += 1


def compare_files(file1: Union[str, Path], file2: Union[str, Path]) -> bool:
    """Compare two files to see if they are identical.
    
    Args:
        file1: First file path
        file2: Second file path
        
    Returns:
        True if files are identical, False otherwise
    """
    file1_path = Path(file1)
    file2_path = Path(file2)
    
    if not (file1_path.exists() and file2_path.exists()):
        return False
    
    # Quick size check first
    if file1_path.stat().st_size != file2_path.stat().st_size:
        return False
    
    # Compare file contents
    try:
        with open(file1_path, 'rb') as f1, open(file2_path, 'rb') as f2:
            chunk_size = 8192
            while True:
                chunk1 = f1.read(chunk_size)
                chunk2 = f2.read(chunk_size)
                
                if chunk1 != chunk2:
                    return False
                
                if not chunk1:  # End of file
                    return True
                    
    except Exception:
        return False


def create_backup(file_path: Union[str, Path]) -> Optional[Path]:
    """Create a backup of a file.
    
    Args:
        file_path: Path to file to backup
        
    Returns:
        Path to backup file if successful, None otherwise
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        return None
    
    backup_path = file_path.with_suffix(file_path.suffix + '.backup')
    
    try:
        shutil.copy2(str(file_path), str(backup_path))
        return backup_path
    except Exception:
        return None


def restore_from_backup(file_path: Union[str, Path]) -> bool:
    """Restore a file from its backup.
    
    Args:
        file_path: Path to file to restore
        
    Returns:
        True if successful, False otherwise
    """
    file_path = Path(file_path)
    backup_path = file_path.with_suffix(file_path.suffix + '.backup')
    
    if not backup_path.exists():
        return False
    
    try:
        shutil.move(str(backup_path), str(file_path))
        return True
    except Exception:
        return False


def calculate_directory_size(directory: Union[str, Path]) -> int:
    """Calculate total size of all files in a directory.
    
    Args:
        directory: Directory to calculate size for
        
    Returns:
        Total size in bytes
    """
    directory = Path(directory)
    total_size = 0
    
    try:
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
    except Exception:
        pass
    
    return total_size


def get_file_stats(file_path: Union[str, Path]) -> Dict[str, any]:
    """Get comprehensive file statistics.
    
    Args:
        file_path: Path to file
        
    Returns:
        Dictionary with file statistics
    """
    file_path = Path(file_path)
    
    stats = {
        'exists': False,
        'size': 0,
        'size_formatted': '0 B',
        'created': None,
        'modified': None,
        'extension': '',
        'is_readable': False,
        'is_writable': False,
    }
    
    try:
        if file_path.exists():
            file_stat = file_path.stat()
            stats.update({
                'exists': True,
                'size': file_stat.st_size,
                'size_formatted': format_file_size(file_stat.st_size),
                'created': file_stat.st_ctime,
                'modified': file_stat.st_mtime,
                'extension': file_path.suffix.lower(),
                'is_readable': os.access(file_path, os.R_OK),
                'is_writable': os.access(file_path, os.W_OK),
            })
    except Exception:
        pass
    
    return stats


def progress_callback(current: int, total: int, description: str = "Processing") -> None:
    """Simple progress callback for operations.
    
    Args:
        current: Current progress count
        total: Total count
        description: Description of the operation
    """
    if total > 0:
        percentage = (current / total) * 100
        print(f"\r{description}: {current}/{total} ({percentage:.1f}%)", end="", flush=True)
        if current == total:
            print()  # New line when complete