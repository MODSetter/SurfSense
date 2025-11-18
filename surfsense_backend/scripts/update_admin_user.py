#!/usr/bin/env python3
"""
Utility script to update admin user password and status.

This script should be run on the VPS after deployment to:
1. Update the admin user's password
2. Ensure is_superuser, is_active, is_verified are all True

Usage:
    cd /path/to/SurfSense/surfsense_backend
    source venv/bin/activate  # or your virtual environment

    # Set environment variables (REQUIRED - never commit passwords!)
    export ADMIN_EMAIL="admin@example.com"
    export ADMIN_NEW_PASSWORD="your-secure-password-here"

    python scripts/update_admin_user.py

Note: Make sure the .env file is properly configured with DATABASE_URL

SECURITY WARNING:
    - NEVER hardcode passwords in this script
    - NEVER commit passwords to version control
    - Always use environment variables for sensitive data
"""

import asyncio
import os
import sys

# Add the parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import bcrypt
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


def get_admin_credentials():
    """Get admin credentials from environment variables."""
    admin_email = os.getenv("ADMIN_EMAIL")
    new_password = os.getenv("ADMIN_NEW_PASSWORD")

    if not admin_email:
        print("ERROR: ADMIN_EMAIL environment variable not set")
        print("Please set it before running this script:")
        print('  export ADMIN_EMAIL="admin@example.com"')
        sys.exit(1)

    if not new_password:
        print("ERROR: ADMIN_NEW_PASSWORD environment variable not set")
        print("Please set it before running this script:")
        print('  export ADMIN_NEW_PASSWORD="your-secure-password"')
        sys.exit(1)

    # Validate password strength
    if len(new_password) < 12:
        print("WARNING: Password should be at least 12 characters for security")

    return admin_email, new_password


def hash_password(password: str) -> str:
    """Hash password using bcrypt directly (same as FastAPI-Users)."""
    # Encode to bytes and truncate to 72 bytes (bcrypt limit)
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')


async def update_admin_user():
    """Update admin user password and status."""

    # Get credentials from environment
    admin_email, new_password = get_admin_credentials()

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

    print("Connecting to database...")

    # Create async engine
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Hash the new password
            hashed_password = hash_password(new_password)

            # Update the user
            result = await session.execute(
                update(UserTable)
                .where(UserTable.email == admin_email)
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
                print(f"\n[OK] Successfully updated user: {admin_email}")
                print(f"   - User ID: {updated_user.id}")
                print("   - Password: Updated to new value")
                print("   - is_superuser: True")
                print("   - is_active: True")
                print("   - is_verified: True")
            else:
                print(f"\n[ERROR] User not found: {admin_email}")
                print("   Make sure the email address is correct")

                # List existing users for debugging
                from sqlalchemy import text
                users_result = await session.execute(
                    text('SELECT email FROM "user" LIMIT 10')
                )
                users = users_result.fetchall()
                if users:
                    print("\n   Existing users in database:")
                    for user in users:
                        print(f"   - {user[0]}")

        except Exception as e:
            print(f"\n[ERROR] Error updating user: {e}")
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

    # Get and display target (without showing password)
    admin_email = os.getenv("ADMIN_EMAIL", "NOT SET")
    has_password = bool(os.getenv("ADMIN_NEW_PASSWORD"))

    print(f"\nTarget user: {admin_email}")
    print(f"New password: {'[SET]' if has_password else '[NOT SET]'}")
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
    print("\nSECURITY REMINDER: Clear your shell history if you used inline env vars")
    print("  history -c  # bash")
    print("  fc -p       # zsh")
