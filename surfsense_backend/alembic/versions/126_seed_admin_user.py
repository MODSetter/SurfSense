"""126_seed_admin_user

Revision ID: 126
Revises: 125
Create Date: 2026-04-15

Seeds one admin user on fresh installs (no-op if any user already exists).
Credentials are overridable via env vars:
  ADMIN_EMAIL    (default: admin@surfsense.local)
  ADMIN_PASSWORD (default: Admin@SurfSense1)

Admin is created with:
  - is_superuser = TRUE, is_active = TRUE, is_verified = TRUE
  - subscription_status = 'active', plan_id = 'pro_yearly'
  - monthly_token_limit = 1_000_000, pages_limit = 5000
  - A default search space, roles, membership, and prompt defaults
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "126"
down_revision: str | None = "125"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _hash_password(password: str) -> str:
    """Hash password using argon2-cffi (installed as a fastapi-users dependency)."""
    from argon2 import PasswordHasher

    ph = PasswordHasher()
    return ph.hash(password)


def upgrade() -> None:
    conn = op.get_bind()

    # Only seed when the database is empty
    result = conn.execute(sa.text('SELECT 1 FROM "user" LIMIT 1'))
    if result.fetchone() is not None:
        return  # Users already exist — skip seed

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@surfsense.local")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin@SurfSense1")
    if not os.environ.get("ADMIN_PASSWORD"):
        print(
            "\n⚠️  WARNING: ADMIN_PASSWORD env var not set. "
            "Using default password 'Admin@SurfSense1'. "
            "Change this immediately after first login!\n"
        )
    hashed_pw = _hash_password(admin_password)
    admin_id = str(uuid.uuid4())

    # 1. Insert admin user
    conn.execute(
        sa.text(
            """
            INSERT INTO "user" (
                id, email, hashed_password,
                is_active, is_superuser, is_verified,
                subscription_status, plan_id,
                monthly_token_limit, pages_limit, pages_used,
                tokens_used_this_month
            ) VALUES (
                :id, :email, :hashed_password,
                TRUE, TRUE, TRUE,
                'active', 'pro_yearly',
                1000000, 5000, 0,
                0
            )
            """
        ),
        {
            "id": admin_id,
            "email": admin_email,
            "hashed_password": hashed_pw,
        },
    )

    # 2. Insert default search space for admin (only required columns; defaults handle the rest)
    search_space_result = conn.execute(
        sa.text(
            """
            INSERT INTO searchspaces (name, description, citations_enabled, user_id, created_at)
            VALUES ('My Search Space', 'Your personal search space', TRUE, :user_id, now())
            RETURNING id
            """
        ),
        {"user_id": admin_id},
    )
    search_space_id = search_space_result.fetchone()[0]

    # 3. Insert default roles for the search space
    owner_role_result = conn.execute(
        sa.text(
            """
            INSERT INTO search_space_roles
                (name, description, permissions, is_default, is_system_role, search_space_id, created_at)
            VALUES (
                'Owner', 'Full access to all search space resources and settings',
                ARRAY['*'], FALSE, TRUE, :ss_id, now()
            )
            RETURNING id
            """
        ),
        {"ss_id": search_space_id},
    )
    owner_role_id = owner_role_result.fetchone()[0]

    conn.execute(
        sa.text(
            """
            INSERT INTO search_space_roles
                (name, description, permissions, is_default, is_system_role, search_space_id, created_at)
            VALUES
            (
                'Editor',
                'Can create and update content (no delete, role management, or settings access)',
                ARRAY[
                    'documents:create','documents:read','documents:update',
                    'chats:create','chats:read','chats:update',
                    'comments:create','comments:read',
                    'llm_configs:create','llm_configs:read','llm_configs:update',
                    'podcasts:create','podcasts:read','podcasts:update',
                    'video_presentations:create','video_presentations:read','video_presentations:update',
                    'image_generations:create','image_generations:read',
                    'vision_configs:create','vision_configs:read',
                    'connectors:create','connectors:read','connectors:update',
                    'logs:read', 'members:invite'
                ],
                TRUE, TRUE, :ss_id, now()
            ),
            (
                'Viewer', 'Read-only access to search space resources',
                ARRAY[
                    'documents:read','chats:read','comments:read',
                    'llm_configs:read','podcasts:read','video_presentations:read',
                    'image_generations:read','vision_configs:read','connectors:read','logs:read'
                ],
                FALSE, TRUE, :ss_id, now()
            )
            """
        ),
        {"ss_id": search_space_id},
    )

    # 4. Insert owner membership
    conn.execute(
        sa.text(
            """
            INSERT INTO search_space_memberships
                (user_id, search_space_id, role_id, is_owner, joined_at, created_at)
            VALUES (:user_id, :ss_id, :role_id, TRUE, now(), now())
            """
        ),
        {"user_id": admin_id, "ss_id": search_space_id, "role_id": owner_role_id},
    )

    # 5. Insert default prompts (same as migration 114 but just for admin)
    conn.execute(
        sa.text(
            """
            INSERT INTO prompts
                (user_id, default_prompt_slug, name, prompt, mode, version, is_public, created_at)
            VALUES
                (:uid, 'fix-grammar', 'Fix grammar',
                 'Fix the grammar and spelling in the following text. Return only the corrected text, nothing else.\n\n{selection}',
                 'transform'::prompt_mode, 1, false, now()),
                (:uid, 'make-shorter', 'Make shorter',
                 'Make the following text more concise while preserving its meaning. Return only the shortened text, nothing else.\n\n{selection}',
                 'transform'::prompt_mode, 1, false, now()),
                (:uid, 'translate', 'Translate',
                 'Translate the following text to English. If it is already in English, translate it to French. Return only the translation, nothing else.\n\n{selection}',
                 'transform'::prompt_mode, 1, false, now()),
                (:uid, 'rewrite', 'Rewrite',
                 'Rewrite the following text to improve clarity and readability. Return only the rewritten text, nothing else.\n\n{selection}',
                 'transform'::prompt_mode, 1, false, now()),
                (:uid, 'summarize', 'Summarize',
                 'Summarize the following text concisely. Return only the summary, nothing else.\n\n{selection}',
                 'transform'::prompt_mode, 1, false, now()),
                (:uid, 'explain', 'Explain',
                 'Explain the following text in simple terms:\n\n{selection}',
                 'explore'::prompt_mode, 1, false, now()),
                (:uid, 'ask-knowledge-base', 'Ask my knowledge base',
                 'Search my knowledge base for information related to:\n\n{selection}',
                 'explore'::prompt_mode, 1, false, now()),
                (:uid, 'look-up-web', 'Look up on the web',
                 'Search the web for information about:\n\n{selection}',
                 'explore'::prompt_mode, 1, false, now())
            ON CONFLICT (user_id, default_prompt_slug) DO NOTHING
            """
        ),
        {"uid": admin_id},
    )


def downgrade() -> None:
    # Intentional no-op: never delete users on downgrade
    pass
