#!/usr/bin/env python
"""
Seed Surfsense documentation into the database.

CLI wrapper for the seed_surfsense_docs function.
Can be run manually for debugging or re-indexing.

Usage:
    python scripts/seed_surfsense_docs.py
"""

import asyncio
import sys
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tasks.surfsense_docs_indexer import seed_surfsense_docs


def main():
    """CLI entry point for seeding Surfsense docs."""
    print("=" * 50)
    print("  Surfsense Documentation Seeding")
    print("=" * 50)

    created, updated, skipped, deleted = asyncio.run(seed_surfsense_docs())

    print()
    print("Results:")
    print(f"  Created: {created}")
    print(f"  Updated: {updated}")
    print(f"  Skipped: {skipped}")
    print(f"  Deleted: {deleted}")
    print("=" * 50)


if __name__ == "__main__":
    main()
