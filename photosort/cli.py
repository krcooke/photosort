"""Command Line Interface for PhotoSort."""

import sys
from pathlib import Path
from typing import Optional

try:
    import typer
    from rich.console import Console
    from rich.progress import Progress
    from rich import print as rich_print
    RICH_AVAILABLE = True
except ImportError:
    # Fallback without rich/typer
    RICH_AVAILABLE = False
    typer = None
    Console = None

from .config import load_config


# Initialize console for rich output
if RICH_AVAILABLE:
    console = Console()
    app = typer.Typer(
        name="photosort",
        help="A command line tool to help sort photos into configurable directory structures with duplicate detection",
        no_args_is_help=True,
        rich_markup_mode="rich"
    )
else:
    # Fallback CLI without typer
    app = None


def _print_message(message: str, style: Optional[str] = None) -> None:
    """Print message with optional styling."""
    if RICH_AVAILABLE and console:
        console.print(message, style=style)
    else:
        print(message)


def _print_error(message: str) -> None:
    """Print error message."""
    if RICH_AVAILABLE:
        console.print(f"[red]Error:[/red] {message}")
    else:
        print(f"Error: {message}", file=sys.stderr)


def _print_warning(message: str) -> None:
    """Print warning message."""
    if RICH_AVAILABLE:
        console.print(f"[yellow]Warning:[/yellow] {message}")
    else:
        print(f"Warning: {message}")


def _print_success(message: str) -> None:
    """Print success message."""
    if RICH_AVAILABLE:
        console.print(f"[green]Success:[/green] {message}")
    else:
        print(f"Success: {message}")


if RICH_AVAILABLE:
    @app.command()
    def scan(
        source_path: str = typer.Argument(..., help="Source directory to scan for photos"),
        config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Path to configuration file"),
        recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r", help="Scan directories recursively"),
        show_duplicates: bool = typer.Option(False, "--duplicates", "-d", help="Show duplicate detection results"),
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
    ) -> None:
        """Scan source directory and analyze photo collection."""
        try:
            config = load_config(config_file)
            
            if verbose:
                config.set('output.verbosity', 2)
            
            source = Path(source_path)
            if not source.exists():
                _print_error(f"Source path does not exist: {source_path}")
                raise typer.Exit(1)
            
            if not source.is_dir():
                _print_error(f"Source path is not a directory: {source_path}")
                raise typer.Exit(1)
            
            _print_message(f"[blue]Scanning:[/blue] {source_path}")
            _print_message(f"[blue]Recursive:[/blue] {recursive}")
            if show_duplicates:
                _print_message(f"[blue]Analyzing duplicates:[/blue] {show_duplicates}")
            
            # Initialize scanner
            from .scanner import PhotoScanner, format_scan_report
            scanner = PhotoScanner(config)
            
            # Show progress
            if config.show_progress:
                _print_message("\n[yellow]Scanning directory...[/yellow]")
            
            # Perform scan
            result = scanner.scan_directory(
                directory=source,
                recursive=recursive,
                analyze_duplicates=show_duplicates
            )
            
            # Generate and display report
            report = format_scan_report(result, verbose=verbose)
            _print_message(f"\n{report}")
            
            # Show any errors
            if result.scan_errors and not verbose:
                _print_warning(f"Encountered {len(result.scan_errors)} errors during scan. Use --verbose to see details.")
            
        except Exception as e:
            _print_error(f"Failed to scan: {str(e)}")
            raise typer.Exit(1)


    @app.command()
    def sort(
        source_path: str = typer.Argument(..., help="Source directory containing photos"),
        dest_path: str = typer.Argument(..., help="Destination directory for sorted photos"),
        config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Path to configuration file"),
        dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be done without making changes"),
        copy_mode: bool = typer.Option(False, "--copy", help="Copy files instead of moving them"),
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
    ) -> None:
        """Sort photos from source to destination using configured directory structure."""
        try:
            config = load_config(config_file)
            
            if verbose:
                config.set('output.verbosity', 2)
            if dry_run:
                config.set('output.dry_run', True)
            
            source = Path(source_path)
            dest = Path(dest_path)
            
            if not source.exists():
                _print_error(f"Source path does not exist: {source_path}")
                raise typer.Exit(1)
            
            if not source.is_dir():
                _print_error(f"Source path is not a directory: {source_path}")
                raise typer.Exit(1)
            
            _print_message(f"[blue]Source:[/blue] {source_path}")
            _print_message(f"[blue]Destination:[/blue] {dest_path}")
            _print_message(f"[blue]Mode:[/blue] {'Copy' if copy_mode else 'Move'}")
            _print_message(f"[blue]Dry run:[/blue] {dry_run}")
            _print_message(f"[blue]Directory pattern:[/blue] {config.directory_pattern}")
            
            # Initialize sorter
            from .sorter import PhotoSorter
            sorter = PhotoSorter(config)
            
            # Show progress
            if config.show_progress:
                _print_message("\n[yellow]Processing photos...[/yellow]")
            
            # Perform sorting
            stats = sorter.sort_photos(
                source_path=source,
                dest_path=dest,
                copy_mode=copy_mode,
                recursive=True
            )
            
            # Display results
            _print_message("\n[green]✓ Sorting completed![/green]")
            _print_message(f"[blue]Files processed:[/blue] {stats['processed']}")
            
            if copy_mode:
                _print_message(f"[blue]Files copied:[/blue] {stats['copied']}")
            else:
                _print_message(f"[blue]Files moved:[/blue] {stats['moved']}")
            
            if stats['skipped'] > 0:
                _print_message(f"[yellow]Files skipped:[/yellow] {stats['skipped']}")
            
            if stats['errors'] > 0:
                _print_warning(f"Errors encountered: {stats['errors']}")
            
            if stats['enhanced_metadata'] > 0:
                _print_message(f"[blue]Metadata enhanced:[/blue] {stats['enhanced_metadata']}")
            
        except Exception as e:
            _print_error(f"Failed to sort: {str(e)}")
            raise typer.Exit(1)


    @app.command()
    def duplicates(
        source_path: str = typer.Argument(..., help="Directory to scan for duplicate photos"),
        config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Path to configuration file"),
        threshold: Optional[int] = typer.Option(None, "--threshold", "-t", help="Duplicate detection threshold (0-64)"),
        action: str = typer.Option("report", "--action", "-a", help="Action for duplicates: report, move, delete"),
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
    ) -> None:
        """Find and handle duplicate photos."""
        try:
            config = load_config(config_file)
            
            if verbose:
                config.set('output.verbosity', 2)
            if threshold is not None:
                config.set('duplicate_detection.threshold', threshold)
            
            source = Path(source_path)
            if not source.exists():
                _print_error(f"Source path does not exist: {source_path}")
                raise typer.Exit(1)
            
            if not source.is_dir():
                _print_error(f"Source path is not a directory: {source_path}")
                raise typer.Exit(1)
            
            _print_message(f"[blue]Scanning for duplicates in:[/blue] {source_path}")
            _print_message(f"[blue]Threshold:[/blue] {config.duplicate_threshold}")
            _print_message(f"[blue]Action:[/blue] {action}")
            
            # Initialize duplicate detector
            from .duplicates import DuplicateDetector
            from .utils import format_file_size
            
            try:
                detector = DuplicateDetector(
                    algorithm=config.duplicate_algorithm,
                    threshold=config.duplicate_threshold
                )
            except (ValueError, ImportError) as e:
                _print_error(f"Duplicate detection not available: {e}")
                raise typer.Exit(1)
            
            # Show progress
            if config.show_progress:
                _print_message("\n[yellow]Scanning for photo files...[/yellow]")
            
            # Scan for candidates
            candidates = detector.scan_directory(
                directory=source,
                supported_formats=config.supported_formats,
                recursive=True
            )
            
            if not candidates:
                _print_message("[yellow]No supported photo files found.[/yellow]")
                return
            
            _print_message(f"Found {len(candidates)} photos to analyze.")
            
            if config.show_progress:
                _print_message("\n[yellow]Finding duplicate groups...[/yellow]")
            
            # Find duplicate groups
            groups = detector.find_duplicates(candidates)
            
            if not groups:
                _print_success("No duplicates found!")
                return
            
            # Get statistics
            stats = detector.get_statistics(groups)
            
            # Display results
            _print_message("\n[red]📸 Duplicate Detection Results[/red]")
            _print_message(f"[blue]Duplicate groups found:[/blue] {stats['duplicate_groups']}")
            _print_message(f"[blue]Total files in groups:[/blue] {stats['total_files_in_groups']}")
            _print_message(f"[blue]Duplicate files:[/blue] {stats['duplicate_files']}")
            _print_message(f"[blue]Potential space savings:[/blue] {format_file_size(stats['wasted_space_bytes'])}")
            if stats['space_savings_percent'] > 0:
                _print_message(f"[blue]Space savings:[/blue] {stats['space_savings_percent']:.1f}%")
            
            # Show detailed results if verbose or action is report
            if verbose or action == "report":
                _print_message(f"\n[yellow]📋 Duplicate Groups (Top 10):[/yellow]")
                for i, group in enumerate(sorted(groups, key=lambda g: g.size, reverse=True)[:10], 1):
                    _print_message(f"\n[cyan]Group {i}:[/cyan] {group.size} files, {format_file_size(group.get_total_size())}")
                    
                    # Show quality information for the best candidate
                    best = group.best_candidate
                    quality = best.quality_metrics
                    quality_score = best._calculate_quality_score(quality)
                    _print_message(f"  [green]Keep:[/green] {best.file_path.name} ({format_file_size(best.file_size)}) - Quality: {quality_score:.2f}")
                    if verbose:
                        _print_message(f"    Sharpness: {quality['sharpness']:.1f}, Contrast: {quality['contrast']:.1f}, Brightness: {quality['brightness']:.1f}")
                    
                    if len(group.duplicates_to_remove) > 0:
                        _print_message(f"  [red]Remove:[/red]")
                        for dup in group.duplicates_to_remove[:3]:  # Show first 3
                            dup_quality = dup.quality_metrics
                            dup_score = dup._calculate_quality_score(dup_quality)
                            _print_message(f"    - {dup.file_path.name} ({format_file_size(dup.file_size)}) - Quality: {dup_score:.2f}")
                            if verbose:
                                _print_message(f"      Sharpness: {dup_quality['sharpness']:.1f}, Contrast: {dup_quality['contrast']:.1f}, Brightness: {dup_quality['brightness']:.1f}")
                        if len(group.duplicates_to_remove) > 3:
                            _print_message(f"    - ... and {len(group.duplicates_to_remove) - 3} more files")
            
            # Handle actions
            if action == "move":
                quarantine_folder = source / config.quarantine_folder
                _print_warning(f"Moving duplicates to quarantine folder: {quarantine_folder}")
                # TODO: Implement move action
                _print_warning("Move action not yet implemented")
            elif action == "delete":
                _print_warning("Delete action would remove duplicate files permanently")
                # TODO: Implement delete action  
                _print_warning("Delete action not yet implemented")
            elif action == "report":
                _print_message(f"\n[green]✓ Duplicate scan complete![/green] Use --action move or --action delete to handle duplicates.")
            
        except Exception as e:
            _print_error(f"Failed to find duplicates: {str(e)}")
            raise typer.Exit(1)


    @app.command("enhance-metadata")
    def enhance_metadata(
        source_path: str = typer.Argument(..., help="Directory containing photos to enhance"),
        config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Path to configuration file"),
        dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be done without making changes"),
        backup: bool = typer.Option(True, "--backup/--no-backup", help="Create backups of original files"),
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
    ) -> None:
        """Enhance photo metadata by extracting information from directory structure."""
        try:
            config = load_config(config_file)
            
            if verbose:
                config.set('output.verbosity', 2)
            if dry_run:
                config.set('output.dry_run', True)
            if not backup:
                config.set('metadata_enhancement.backup_originals', False)
            
            source = Path(source_path)
            if not source.exists():
                _print_error(f"Source path does not exist: {source_path}")
                raise typer.Exit(1)
            
            if not source.is_dir():
                _print_error(f"Source path is not a directory: {source_path}")
                raise typer.Exit(1)
            
            _print_message(f"[blue]Enhancing metadata in:[/blue] {source_path}")
            _print_message(f"[blue]Dry run:[/blue] {dry_run}")
            _print_message(f"[blue]Backup originals:[/blue] {backup}")
            
            # TODO: Implement actual metadata enhancement logic
            _print_warning("Metadata enhancement functionality not yet implemented")
            
        except Exception as e:
            _print_error(f"Failed to enhance metadata: {str(e)}")
            raise typer.Exit(1)


    @app.command()
    def config(
        show: bool = typer.Option(False, "--show", help="Show current configuration"),
        config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Path to configuration file"),
        create_default: bool = typer.Option(False, "--create-default", help="Create default configuration file")
    ) -> None:
        """Manage PhotoSort configuration."""
        try:
            if create_default:
                default_config_path = Path("photosort_config.yaml")
                config = load_config()
                config.save_config(default_config_path)
                _print_success(f"Created default configuration: {default_config_path}")
                return
            
            config = load_config(config_file)
            
            if show:
                _print_message("[blue]Current Configuration:[/blue]")
                _print_message(f"Directory pattern: {config.directory_pattern}")
                _print_message(f"Duplicate algorithm: {config.duplicate_algorithm}")
                _print_message(f"Duplicate threshold: {config.duplicate_threshold}")
                _print_message(f"Supported formats: {', '.join(config.supported_formats)}")
                _print_message(f"Max workers: {config.max_workers}")
                _print_message(f"Verbosity: {config.verbosity}")
            else:
                _print_message("Use --show to display current configuration")
                _print_message("Use --create-default to create a default configuration file")
            
        except Exception as e:
            _print_error(f"Failed to manage configuration: {str(e)}")
            raise typer.Exit(1)


    @app.callback()
    def main(
        version: bool = typer.Option(False, "--version", help="Show version and exit")
    ) -> None:
        """PhotoSort - A command line tool for organizing and managing photo collections."""
        if version:
            from . import __version__
            _print_message(f"PhotoSort {__version__}")
            raise typer.Exit()


else:
    # Fallback CLI implementation without typer
    def main() -> None:
        """Main entry point when typer is not available."""
        print("PhotoSort CLI")
        print("Error: Required dependencies (typer, rich) are not available.")
        print("Please install them with: pip install typer[all] rich")
        sys.exit(1)
    
    # Create a mock app for compatibility
    class MockApp:
        def __call__(self):
            main()
    
    app = MockApp()


if __name__ == "__main__":
    if RICH_AVAILABLE:
        app()
    else:
        main()