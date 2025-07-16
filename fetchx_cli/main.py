"""Main entry point for FETCHX IDM."""

import sys


def main():
    """Main entry point for the application."""
    try:
        from fetchx_cli.cli.commands import main as cli_main

        cli_main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
