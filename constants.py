from __future__ import annotations

from .app import run_app


def main() -> int:
    """Application entry point."""
    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
