#!/usr/bin/env python3
"""
Utility script to update admin user password and status.

This script should be run on the VPS after deployment to:
1. Update the admin user's password
2. Ensure is_superuser, is_active, is_verified are all True

Usage:
    cd /path/to/SurfSense/surfsense_backend
    source venv/bin/activate  # or your virtual environment
    python scripts/update_admin_user.py

Note: Make sure the .env file is properly configured with DATABASE_URL
"""

import asyncio
import os
import sys

# Add the parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Password hashing context (same as FastAPI-Users uses)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configuration
ADMIN_EMAIL = "ojars@kapteinis.lv"
NEW_PASSWORD = "^&U0yXLK1ypZOwLDGFeLT35kCrblITYyAVdVmF3!iJ%kkY1Nl^IS!P"


async def update_admin_user():
    """Update admin user password and status."""

    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment variables")
        print("Make sure your .env file is configured correctly")
        sys.exit(1)

    # Convert postgres:// to postgresql+asyncpg:// if needed
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    print(f"Connecting to database...")

    # Create async engine
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Hash the new password
            hashed_password = pwd_context.hash(NEW_PASSWORD)

            # Update the user
            result = await session.execute(
                update(UserTable)
                .where(UserTable.email == ADMIN_EMAIL)
                .values(
                    hashed_password=hashed_password,
                    is_superuser=True,
                    is_active=True,
                    is_verified=True
                )
                .returning(UserTable.id, UserTable.email)
            )

            updated_user = result.first()

            if updated_user:
                await session.commit()
                print(f"\n✅ Successfully updated user: {ADMIN_EMAIL}")
                print(f"   - User ID: {updated_user.id}")
                print(f"   - Password: Updated to new value")
                print(f"   - is_superuser: True")
                print(f"   - is_active: True")
                print(f"   - is_verified: True")
            else:
                print(f"\n❌ User not found: {ADMIN_EMAIL}")
                print("   Make sure the email address is correct")

                # List existing users for debugging
                from sqlalchemy import text
                users_result = await session.execute(
                    text("SELECT email FROM \"user\" LIMIT 10")
                )
                users = users_result.fetchall()
                if users:
                    print("\n   Existing users in database:")
                    for user in users:
                        print(f"   - {user[0]}")

        except Exception as e:
            print(f"\n❌ Error updating user: {e}")
            await session.rollback()
            raise
        finally:
            await engine.dispose()


# Import the User model after environment is loaded
# We need to do this here to ensure DATABASE_URL is available
if __name__ == "__main__":
    print("=" * 50)
    print("Admin User Update Script")
    print("=" * 50)
    print(f"\nTarget user: {ADMIN_EMAIL}")
    print(f"New password: {'*' * 10} (hidden)")
    print()

    # Now import the User model
    try:
        from app.db import User as UserTable
    except ImportError:
        # Try alternative import if running from different directory
        try:
            from surfsense_backend.app.db import User as UserTable
        except ImportError:
            print("ERROR: Could not import User model")
            print("Make sure you're running this script from the surfsense_backend directory")
            sys.exit(1)

    # Run the async update
    asyncio.run(update_admin_user())

    print("\n" + "=" * 50)
    print("Done!")
    print("=" * 50)
