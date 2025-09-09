"""Main entry point for PhotoSort when run as python -m photosort."""

from .cli import app, main

if __name__ == "__main__":
    try:
        app()
    except SystemExit:
        raise
    except Exception:
        main()  # Fallback if typer not available