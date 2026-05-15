"""Default safe-by-construction allowlist for self-gated approvals.

Tools listed here mirror the safety profile of ``write_file`` against the
SurfSense KB: each call creates exactly one artifact in the user's own
workspace with no external visibility (drafts aren't sent; new files aren't
shared unless the user shares them later). Auto-approving them lets the agent
seed scratch artifacts without firing a popup on every call.

Members still flow through :func:`request_approval` — the function returns
immediately with ``decision_type="auto_approved"`` and the original params
untouched. This keeps tool bodies (logging, metadata fetches, account
fallbacks) symmetrical with the prompted path; the only behavior change is
"no interrupt fires".

Per-search-space ``agent_permission_rules`` (when wired) take precedence and
can re-enable prompting for any of these.
"""

from __future__ import annotations

DEFAULT_AUTO_APPROVED_TOOLS: frozenset[str] = frozenset(
    {
        "create_gmail_draft",
        "update_gmail_draft",
        "create_calendar_event",
        "create_notion_page",
        "create_confluence_page",
        "create_google_drive_file",
        "create_dropbox_file",
        "create_onedrive_file",
    }
)


__all__ = ["DEFAULT_AUTO_APPROVED_TOOLS"]
