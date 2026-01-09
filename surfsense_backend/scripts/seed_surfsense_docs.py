#!/usr/bin/env python
"""
Seed Surfsense documentation into the database.
Run this script after migrations to index MDX documentation files.

Usage:
    python scripts/seed_surfsense_docs.py
"""

import sys
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import config
from app.tasks.surfsense_docs_indexer import index_surfsense_docs


def main():
    """Main entry point for seeding Surfsense docs."""
    print("Starting Surfsense docs seeding...")
    
    # Create sync engine from database URL
    # Convert async URL to sync if needed
    database_url = config.DATABASE_URL
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    engine = create_engine(database_url)
    
    with Session(engine) as session:
        created, updated, skipped, deleted = index_surfsense_docs(session)
        
        print(f"\nSurfsense docs seeding complete:")
        print(f"  Created: {created}")
        print(f"  Updated: {updated}")
        print(f"  Skipped: {skipped}")
        print(f"  Deleted: {deleted}")


if __name__ == "__main__":
    main()

