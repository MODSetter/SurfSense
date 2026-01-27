from fastapi import APIRouter

from .airtable_add_connector_route import (
    router as airtable_add_connector_router,
)
from .chat_comments_routes import router as chat_comments_router
from .circleback_webhook_route import router as circleback_webhook_router
from .clickup_add_connector_route import router as clickup_add_connector_router
from .composio_routes import router as composio_router
from .confluence_add_connector_route import router as confluence_add_connector_router
from .discord_add_connector_route import router as discord_add_connector_router
from .documents_routes import router as documents_router
from .editor_routes import router as editor_router
from .google_calendar_add_connector_route import (
    router as google_calendar_add_connector_router,
)
from .google_drive_add_connector_route import (
    router as google_drive_add_connector_router,
)
from .google_gmail_add_connector_route import (
    router as google_gmail_add_connector_router,
)
from .incentive_tasks_routes import router as incentive_tasks_router
from .jira_add_connector_route import router as jira_add_connector_router
from .linear_add_connector_route import router as linear_add_connector_router
from .logs_routes import router as logs_router
from .luma_add_connector_route import router as luma_add_connector_router
from .new_chat_routes import router as new_chat_router
from .new_llm_config_routes import router as new_llm_config_router
from .notes_routes import router as notes_router
from .notifications_routes import router as notifications_router
from .notion_add_connector_route import router as notion_add_connector_router
from .podcasts_routes import router as podcasts_router
from .public_chat_routes import router as public_chat_router
from .rbac_routes import router as rbac_router
from .search_source_connectors_routes import router as search_source_connectors_router
from .search_spaces_routes import router as search_spaces_router
from .slack_add_connector_route import router as slack_add_connector_router
from .surfsense_docs_routes import router as surfsense_docs_router
from .teams_add_connector_route import router as teams_add_connector_router

router = APIRouter()

router.include_router(search_spaces_router)
router.include_router(rbac_router)  # RBAC routes for roles, members, invites
router.include_router(editor_router)
router.include_router(documents_router)
router.include_router(notes_router)
router.include_router(new_chat_router)  # Chat with assistant-ui persistence
router.include_router(chat_comments_router)
router.include_router(podcasts_router)  # Podcast task status and audio
router.include_router(search_source_connectors_router)
router.include_router(google_calendar_add_connector_router)
router.include_router(google_gmail_add_connector_router)
router.include_router(google_drive_add_connector_router)
router.include_router(airtable_add_connector_router)
router.include_router(linear_add_connector_router)
router.include_router(luma_add_connector_router)
router.include_router(notion_add_connector_router)
router.include_router(slack_add_connector_router)
router.include_router(teams_add_connector_router)
router.include_router(discord_add_connector_router)
router.include_router(jira_add_connector_router)
router.include_router(confluence_add_connector_router)
router.include_router(clickup_add_connector_router)
router.include_router(new_llm_config_router)  # LLM configs with prompt configuration
router.include_router(logs_router)
router.include_router(circleback_webhook_router)  # Circleback meeting webhooks
router.include_router(surfsense_docs_router)  # Surfsense documentation for citations
router.include_router(notifications_router)  # Notifications with Electric SQL sync
router.include_router(composio_router)  # Composio OAuth and toolkit management
router.include_router(public_chat_router)  # Public chat sharing and cloning
router.include_router(incentive_tasks_router)  # Incentive tasks for earning free pages
