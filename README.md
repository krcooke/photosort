# PhotoSort

A command line tool to help sort photos into configurable directory structures with duplicate detection and metadata enhancement.

## Features

- **Configurable Directory Structure**: Organize photos using patterns like `{year}/{month}-{location}` based on EXIF data and directory inference
- **Duplicate Detection**: Find duplicate photos using perceptual hashing with configurable similarity thresholds
- **Metadata Enhancement**: Automatically extract location and keyword information from directory names and add to photo metadata
- **Multiple Hashing Algorithms**: Support for dHash, pHash, aHash, wHash, and color hashing
- **Dry Run Mode**: Preview operations before making changes
- **Comprehensive Format Support**: Handle JPEG, TIFF, PNG, WebP, HEIC, RAW, and more

## Installation

### From Source

```bash
git clone https://github.com/photosort/photosort.git
cd photosort
pip install -e .
```

### Dependencies

PhotoSort requires Python 3.8+ and the following packages:

- `typer[all]` - Modern CLI framework
- `pillow` - Image processing
- `exifread` - EXIF metadata extraction
- `imagehash` - Perceptual hashing for duplicate detection
- `piexif` - EXIF metadata writing
- `pyyaml` - Configuration file support
- `rich` - Rich terminal output

## Quick Start

1. **Scan a directory** to analyze your photo collection:
   ```bash
   photosort scan /path/to/photos --recursive
   ```

2. **Sort photos** into organized directory structure:
   ```bash
   photosort sort /source/path /destination/path
   ```

3. **Find duplicates** in your collection:
   ```bash
   photosort duplicates /path/to/photos --threshold 10
   ```

4. **Enhance metadata** by extracting location from directory names:
   ```bash
   photosort enhance-metadata /path/to/photos
   ```

## Configuration

PhotoSort uses YAML configuration files. Create a default configuration:

```bash
photosort config --create-default
```

### Configuration Example

```yaml
# Directory structure pattern
directory_structure:
  pattern: "{year}/{month:02d}-{month_name}/{day:02d}"
  fallback_pattern: "unsorted/{year}/{month:02d}"

# Duplicate detection settings
duplicate_detection:
  algorithm: "dhash"        # dhash, phash, ahash, whash, colorhash
  threshold: 10             # Hamming distance (0-64, lower = stricter)
  quarantine_folder: "duplicates"
  keep_best_quality: true

# Metadata enhancement
metadata_enhancement:
  write_location_to_exif: true
  write_keywords_to_exif: true
  backup_originals: true
  
  # Extract keywords from directory paths
  keyword_patterns:
    - pattern: ".*/(?P<event>vacation|holiday|wedding|party)/.*"
      tag: "event"
    - pattern: ".*/(?P<location>[A-Z][a-z]+)/.*"
      tag: "location"

# File processing
file_processing:
  supported_formats: [".jpg", ".jpeg", ".png", ".tiff", ".heic", ".raw"]
  min_file_size: 1024       # Skip files smaller than 1KB
  max_workers: 4            # Parallel processing threads
```

## Commands

### scan

Analyze a photo collection and provide statistics:

```bash
photosort scan /path/to/photos [OPTIONS]
```

Options:
- `--config, -c`: Path to configuration file
- `--recursive/--no-recursive, -r`: Scan directories recursively (default: true)
- `--duplicates, -d`: Show duplicate detection results
- `--verbose, -v`: Enable verbose output

### sort

Sort and organize photos into directory structure:

```bash
photosort sort SOURCE DESTINATION [OPTIONS]
```

Options:
- `--config, -c`: Path to configuration file
- `--dry-run, -n`: Preview operations without making changes
- `--copy`: Copy files instead of moving them
- `--verbose, -v`: Enable verbose output

### duplicates

Find and handle duplicate photos:

```bash
photosort duplicates /path/to/photos [OPTIONS]
```

Options:
- `--config, -c`: Path to configuration file
- `--threshold, -t`: Override duplicate detection threshold (0-64)
- `--action, -a`: Action for duplicates: `report`, `move`, `delete`
- `--verbose, -v`: Enable verbose output

### enhance-metadata

Extract and write metadata from directory structure:

```bash
photosort enhance-metadata /path/to/photos [OPTIONS]
```

Options:
- `--config, -c`: Path to configuration file
- `--dry-run, -n`: Preview operations without making changes
- `--backup/--no-backup`: Create backups of original files (default: true)
- `--verbose, -v`: Enable verbose output

### config

Manage PhotoSort configuration:

```bash
photosort config [OPTIONS]
```

Options:
- `--show`: Display current configuration
- `--create-default`: Create default configuration file

## Directory Patterns

PhotoSort supports flexible directory patterns using Python string formatting:

### Available Variables

- `{year}`, `{month}`, `{day}` - Date components
- `{month_name}`, `{month_short}` - Month names (e.g., "January", "Jan")
- `{hour}`, `{minute}` - Time components
- `{location}` - GPS location or inferred from directory
- `{camera_make}`, `{camera_model}` - Camera information
- `{lat}`, `{lon}` - GPS coordinates

### Pattern Examples

```yaml
# By date
pattern: "{year}/{month:02d}-{month_name}"
# Result: 2023/12-December

# By location and date  
pattern: "{year}/{location}/{month:02d}-{day:02d}"
# Result: 2023/Paris/12-25

# By camera and date
pattern: "{camera_make}/{year}/{month:02d}"
# Result: Canon/2023/12
```

## Metadata Enhancement

PhotoSort can extract information from your existing directory structure and add it to photo metadata:

### Location Extraction

Configure patterns to extract location from directory paths:

```yaml
location_inference:
  - pattern: ".*/(?P<location>[^/]+)/photos/.*"
    priority: 1
  - pattern: ".*/(?P<location>[^/]+)/?$"
    priority: 2
```

### Keyword Extraction

Extract keywords based on directory names:

```yaml
keyword_patterns:
  - pattern: ".*/(?P<event>vacation|holiday|trip)/.*"
    tag: "event"
  - pattern: ".*/(?P<person>[A-Z][a-z]+)/.*" 
    tag: "person"
```

## Duplicate Detection

PhotoSort uses perceptual hashing to find visually similar images:

### Algorithms

- **dHash (default)**: Difference hash, good balance of speed and accuracy
- **pHash**: Perceptual hash, more accurate but slower  
- **aHash**: Average hash, fastest but less accurate
- **wHash**: Wavelet hash, good for detecting crops and rotations
- **colorHash**: Color histogram hash, detects color similarity

### Thresholds

Hamming distance threshold (0-64):
- **0-5**: Nearly identical images
- **6-10**: Very similar (default: 10)
- **11-15**: Somewhat similar
- **16+**: Likely different images

## Examples

### Basic Photo Organization

```bash
# Scan and analyze photos
photosort scan ~/Pictures --recursive --verbose

# Sort photos by date (dry run first)
photosort sort ~/Pictures ~/Pictures/Organized --dry-run

# Actually sort the photos
photosort sort ~/Pictures ~/Pictures/Organized
```

### Duplicate Management

```bash
# Find duplicates with strict threshold
photosort duplicates ~/Pictures --threshold 5

# Move duplicates to quarantine folder
photosort duplicates ~/Pictures --action move
```

### Metadata Enhancement

```bash
# Extract location from directory structure
photosort enhance-metadata ~/Pictures/Travel --verbose

# Preview metadata enhancement
photosort enhance-metadata ~/Pictures --dry-run
```

## Development

### Setting up Development Environment

```bash
git clone https://github.com/photosort/photosort.git
cd photosort
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
pytest --cov=photosort  # With coverage
```

### Code Formatting

```bash
black photosort tests
isort photosort tests
```

### Type Checking

```bash
mypy photosort
```

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.