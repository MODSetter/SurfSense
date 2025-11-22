"""
Verification script for is_public field migration.

This script verifies that:
1. The is_public column exists on searchspaces table
2. All existing spaces have is_public set (no NULL values)
3. The required indexes exist

Run this after applying migration 43.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import async_session_maker


async def verify_migration():
    """Verify the is_public migration was successful"""
    async with async_session_maker() as session:
        try:
            print("Starting migration verification...")

            # Check if column exists
            print("\n1. Checking if is_public column exists...")
            result = await session.execute(
                text("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'searchspaces'
                    AND column_name = 'is_public'
                """)
            )
            column_info = result.fetchone()

            if not column_info:
                print("❌ FAILED: is_public column does not exist!")
                return False

            print(f"✓ Column exists: {column_info}")
            print(f"  - Data type: {column_info[1]}")
            print(f"  - Nullable: {column_info[2]}")
            print(f"  - Default: {column_info[3]}")

            # Check for NULL values
            print("\n2. Checking for NULL values in is_public...")
            result = await session.execute(
                text("SELECT COUNT(*) FROM searchspaces WHERE is_public IS NULL")
            )
            null_count = result.scalar()

            if null_count > 0:
                print(f"❌ FAILED: Found {null_count} rows with NULL is_public value!")
                return False

            print(f"✓ No NULL values found")

            # Check total count
            result = await session.execute(
                text("SELECT COUNT(*) FROM searchspaces")
            )
            total_count = result.scalar()
            print(f"  - Total search spaces: {total_count}")

            # Check distribution
            result = await session.execute(
                text("""
                    SELECT is_public, COUNT(*) as count
                    FROM searchspaces
                    GROUP BY is_public
                """)
            )
            distribution = result.fetchall()
            print(f"  - Distribution:")
            for is_public, count in distribution:
                status = "Public" if is_public else "Private"
                print(f"    - {status}: {count}")

            # Check if indexes exist
            print("\n3. Checking if indexes exist...")
            result = await session.execute(
                text("""
                    SELECT indexname
                    FROM pg_indexes
                    WHERE tablename = 'searchspaces'
                    AND indexname IN ('ix_searchspaces_is_public', 'ix_searchspaces_user_public')
                """)
            )
            indexes = [row[0] for row in result.fetchall()]

            expected_indexes = ['ix_searchspaces_is_public', 'ix_searchspaces_user_public']
            for idx in expected_indexes:
                if idx in indexes:
                    print(f"✓ Index exists: {idx}")
                else:
                    print(f"❌ FAILED: Index missing: {idx}")
                    return False

            print("\n" + "="*60)
            print("✓ Migration verified successfully!")
            print("="*60)
            return True

        except Exception as e:
            print(f"\n❌ Error during verification: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    success = await verify_migration()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
