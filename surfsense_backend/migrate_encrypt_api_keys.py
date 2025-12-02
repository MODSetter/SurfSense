#!/usr/bin/env python3
"""
Migration Script: Encrypt Existing API Keys
Encrypts all plaintext API keys in the llm_configs table
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import async_session_maker, LLMConfig
from app.services.encryption_service import encryption_service
from sqlalchemy import select, update


async def migrate_encrypt_api_keys():
    """Migrate all plaintext API keys to encrypted format"""

    print("Starting API key encryption migration...")
    print("-" * 60)

    encrypted_count = 0
    already_encrypted_count = 0
    total_count = 0

    async with async_session_maker() as session:
        # Fetch all LLM configs
        result = await session.execute(select(LLMConfig))
        llm_configs = result.scalars().all()

        total_count = len(llm_configs)
        print(f"Found {total_count} LLM configurations")

        if total_count == 0:
            print("No LLM configurations found. Migration complete.")
            return

        print("\nProcessing API keys...")

        for config in llm_configs:
            # Check if API key is already encrypted
            if encryption_service.is_encrypted(config.api_key):
                already_encrypted_count += 1
                print(f"  ✓ {config.name} (ID: {config.id}) - Already encrypted")
            else:
                # Encrypt the API key
                encrypted_key = encryption_service.encrypt(config.api_key)

                # Update directly in database to bypass event listeners
                await session.execute(
                    update(LLMConfig)
                    .where(LLMConfig.id == config.id)
                    .values(api_key=encrypted_key)
                )

                encrypted_count += 1
                print(f"  ✓ {config.name} (ID: {config.id}) - Encrypted")

        # Commit all changes
        await session.commit()

    print("\n" + "-" * 60)
    print("Migration Summary:")
    print(f"  Total LLM configs: {total_count}")
    print(f"  Newly encrypted: {encrypted_count}")
    print(f"  Already encrypted: {already_encrypted_count}")
    print("\nAPI key encryption migration completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(migrate_encrypt_api_keys())
    except Exception as e:
        print(f"\nError during migration: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
