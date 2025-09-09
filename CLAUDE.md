# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PhotoSort is a command line tool built in Python for organizing and managing photo collections. It provides configurable directory structures, duplicate detection using perceptual hashing, and metadata enhancement capabilities.

## Architecture

### Core Components

- **photosort/cli.py**: Main CLI interface using Typer framework with rich output
- **photosort/config.py**: Configuration management with YAML support and dot notation access
- **photosort/metadata.py**: Photo metadata extraction using PIL/ExifRead and enhancement with piexif
- **photosort/duplicates.py**: Duplicate detection using imagehash with multiple algorithms (dhash, phash, ahash, whash, colorhash)
- **photosort/sorter.py**: Core photo sorting engine with configurable directory patterns
- **photosort/utils.py**: Utility functions for file operations, formatting, and validation

### Configuration System

The application uses YAML configuration files with hierarchical structure. Key configuration sections:
- `directory_structure`: Patterns for organizing photos with date/location/camera variables
- `duplicate_detection`: Algorithm selection, thresholds, and handling options
- `metadata_enhancement`: Rules for extracting location/keywords from directory paths
- `file_processing`: Supported formats, size limits, and processing constraints

### Dependencies

The project gracefully handles missing optional dependencies:
- Falls back to minimal functionality when PIL, ExifRead, ImageHash, or PyYAML are unavailable
- Uses mock implementations and simplified interfaces as fallbacks

## Development Commands

### Setup and Installation
```bash
pip install -e .                    # Install in development mode
pip install -e ".[dev]"            # Install with development dependencies
```

### Testing
```bash
pytest                              # Run all tests
pytest --cov=photosort             # Run tests with coverage
pytest tests/test_config.py        # Run specific test module
```

### Code Quality
```bash
black photosort tests              # Format code
isort photosort tests              # Sort imports
mypy photosort                     # Type checking
```

### Running the CLI
```bash
python -m photosort --help         # Show CLI help
photosort scan /path/to/photos     # Scan photos (if installed)
photosort config --show            # Show current configuration
```

## Key Design Patterns

### Error Handling
- Graceful degradation when optional libraries are missing
- Try/except blocks with silent failures for file operations
- Fallback patterns for missing metadata or configuration

### Configuration Access
- Dot notation for nested configuration access: `config.get('duplicate_detection.threshold')`
- Property-based access for common settings: `config.duplicate_threshold`
- Validation and type checking for configuration values

### Metadata Processing
- Multiple extraction methods with fallback chain (PIL → ExifRead → file stats)
- Inference patterns using regex for extracting data from directory paths
- Priority-based location and keyword extraction

### CLI Design
- Typer-based modern CLI with rich output formatting
- Comprehensive help text and option documentation
- Dry-run mode for preview operations
- Verbose logging levels for debugging

## Testing Strategy

- Unit tests for each major component with mocking for external dependencies
- Configuration tests with temporary files
- Metadata extraction tests with mock EXIF data
- Duplicate detection tests with controlled hash scenarios
- Error handling tests for missing files and invalid inputs

## Extension Points

- New hashing algorithms can be added to `duplicates.py`
- Additional metadata extraction sources in `metadata.py`
- Custom directory patterns through configuration
- New CLI commands by extending the Typer app in `cli.py`