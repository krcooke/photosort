"""PhotoSort - A command line tool for organizing and managing photo collections."""

__version__ = "0.1.0"
__author__ = "PhotoSort Contributors"
__description__ = "A command line tool to help sort photos into configurable directory structures with duplicate detection"

from .cli import app

__all__ = ["app"]