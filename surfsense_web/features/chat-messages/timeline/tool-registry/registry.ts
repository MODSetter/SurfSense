"use client";

import dynamic from "next/dynamic";
import type { TimelineToolComponent } from "./types";

// Dynamic imports keep the per-tool UI bundles out of the main chunk —
// each component only loads when an assistant turn references it. Mirrors
// the existing ``components/assistant-ui/assistant-message.tsx`` pattern.
//
// Phase A note: the imported components are still typed as
// ``ToolCallMessagePartComponent`` from assistant-ui; the cast at the
// bottom of this file bridges the contract until the cutover commit
// retypes them to ``TimelineToolComponent``. The cast is a structural
// no-op — every consumed prop overlaps.

const UpdateMemoryToolUI = dynamic(
	() => import("@/components/tool-ui/user-memory").then((m) => ({ default: m.UpdateMemoryToolUI })),
	{ ssr: false }
);
const CreateAutomationToolUI = dynamic(
	() =>
		import("@/components/tool-ui/automation").then((m) => ({ default: m.CreateAutomationToolUI })),
	{ ssr: false }
);
const SandboxExecuteToolUI = dynamic(
	() =>
		import("@/components/tool-ui/sandbox-execute").then((m) => ({
			default: m.SandboxExecuteToolUI,
		})),
	{ ssr: false }
);
const CreateNotionPageToolUI = dynamic(
	() => import("@/components/tool-ui/notion").then((m) => ({ default: m.CreateNotionPageToolUI })),
	{ ssr: false }
);
const UpdateNotionPageToolUI = dynamic(
	() => import("@/components/tool-ui/notion").then((m) => ({ default: m.UpdateNotionPageToolUI })),
	{ ssr: false }
);
const DeleteNotionPageToolUI = dynamic(
	() => import("@/components/tool-ui/notion").then((m) => ({ default: m.DeleteNotionPageToolUI })),
	{ ssr: false }
);
const CreateLinearIssueToolUI = dynamic(
	() => import("@/components/tool-ui/linear").then((m) => ({ default: m.CreateLinearIssueToolUI })),
	{ ssr: false }
);
const UpdateLinearIssueToolUI = dynamic(
	() => import("@/components/tool-ui/linear").then((m) => ({ default: m.UpdateLinearIssueToolUI })),
	{ ssr: false }
);
const DeleteLinearIssueToolUI = dynamic(
	() => import("@/components/tool-ui/linear").then((m) => ({ default: m.DeleteLinearIssueToolUI })),
	{ ssr: false }
);
const CreateGoogleDriveFileToolUI = dynamic(
	() =>
		import("@/components/tool-ui/google-drive").then((m) => ({
			default: m.CreateGoogleDriveFileToolUI,
		})),
	{ ssr: false }
);
const DeleteGoogleDriveFileToolUI = dynamic(
	() =>
		import("@/components/tool-ui/google-drive").then((m) => ({
			default: m.DeleteGoogleDriveFileToolUI,
		})),
	{ ssr: false }
);
const CreateOneDriveFileToolUI = dynamic(
	() =>
		import("@/components/tool-ui/onedrive").then((m) => ({ default: m.CreateOneDriveFileToolUI })),
	{ ssr: false }
);
const DeleteOneDriveFileToolUI = dynamic(
	() =>
		import("@/components/tool-ui/onedrive").then((m) => ({ default: m.DeleteOneDriveFileToolUI })),
	{ ssr: false }
);
const CreateDropboxFileToolUI = dynamic(
	() =>
		import("@/components/tool-ui/dropbox").then((m) => ({ default: m.CreateDropboxFileToolUI })),
	{ ssr: false }
);
const DeleteDropboxFileToolUI = dynamic(
	() =>
		import("@/components/tool-ui/dropbox").then((m) => ({ default: m.DeleteDropboxFileToolUI })),
	{ ssr: false }
);
const CreateCalendarEventToolUI = dynamic(
	() =>
		import("@/components/tool-ui/google-calendar").then((m) => ({
			default: m.CreateCalendarEventToolUI,
		})),
	{ ssr: false }
);
const UpdateCalendarEventToolUI = dynamic(
	() =>
		import("@/components/tool-ui/google-calendar").then((m) => ({
			default: m.UpdateCalendarEventToolUI,
		})),
	{ ssr: false }
);
const DeleteCalendarEventToolUI = dynamic(
	() =>
		import("@/components/tool-ui/google-calendar").then((m) => ({
			default: m.DeleteCalendarEventToolUI,
		})),
	{ ssr: false }
);
const CreateGmailDraftToolUI = dynamic(
	() => import("@/components/tool-ui/gmail").then((m) => ({ default: m.CreateGmailDraftToolUI })),
	{ ssr: false }
);
const UpdateGmailDraftToolUI = dynamic(
	() => import("@/components/tool-ui/gmail").then((m) => ({ default: m.UpdateGmailDraftToolUI })),
	{ ssr: false }
);
const SendGmailEmailToolUI = dynamic(
	() => import("@/components/tool-ui/gmail").then((m) => ({ default: m.SendGmailEmailToolUI })),
	{ ssr: false }
);
const TrashGmailEmailToolUI = dynamic(
	() => import("@/components/tool-ui/gmail").then((m) => ({ default: m.TrashGmailEmailToolUI })),
	{ ssr: false }
);
const CreateJiraIssueToolUI = dynamic(
	() => import("@/components/tool-ui/jira").then((m) => ({ default: m.CreateJiraIssueToolUI })),
	{ ssr: false }
);
const UpdateJiraIssueToolUI = dynamic(
	() => import("@/components/tool-ui/jira").then((m) => ({ default: m.UpdateJiraIssueToolUI })),
	{ ssr: false }
);
const DeleteJiraIssueToolUI = dynamic(
	() => import("@/components/tool-ui/jira").then((m) => ({ default: m.DeleteJiraIssueToolUI })),
	{ ssr: false }
);
const CreateConfluencePageToolUI = dynamic(
	() =>
		import("@/components/tool-ui/confluence").then((m) => ({
			default: m.CreateConfluencePageToolUI,
		})),
	{ ssr: false }
);
const UpdateConfluencePageToolUI = dynamic(
	() =>
		import("@/components/tool-ui/confluence").then((m) => ({
			default: m.UpdateConfluencePageToolUI,
		})),
	{ ssr: false }
);
const DeleteConfluencePageToolUI = dynamic(
	() =>
		import("@/components/tool-ui/confluence").then((m) => ({
			default: m.DeleteConfluencePageToolUI,
		})),
	{ ssr: false }
);

/**
 * Headers-only tools — the timeline shows their ``ItemHeader`` (title +
 * sub-bullets) but mounts no tool body beneath. Two reasons to use
 * this:
 *  - **Structural primitives** (``task``): the row IS the parent of a
 *    delegation span; its job is to label the group. Children render
 *    as their own indented entries.
 *  - **Suppressed connectors** (``link_preview``, ``multi_link_preview``,
 *    ``scrape_webpage``): citations they produce render inline in
 *    markdown; a separate card would be redundant noise.
 */
const NullTimelineBody: TimelineToolComponent = () => null;

/**
 * The timeline's tool-name → component map. Mounted by
 * ``timeline/items/tool-call-item.tsx`` via ``getToolComponent(name)``.
 *
 * Includes only "process" tools (connector CRUD, sandbox execute,
 * memory updates) and the 4 invisible tools mapped to a null component.
 * Deliverables (``generate_report``, ``generate_resume``,
 * ``generate_podcast``, ``generate_video_presentation``,
 * ``display_image``, ``generate_image``) live in ``BODY_TOOLS`` in
 * ``assistant-message.tsx`` — they're product, not process.
 *
 * Tools NOT in this map fall through to ``FallbackToolBody`` (which
 * itself dispatches between HITL approval cards and
 * ``DefaultFallbackCard`` based on result discrimination).
 */
const TOOLS_BY_NAME = {
	task: NullTimelineBody,
	create_automation: CreateAutomationToolUI,
	update_memory: UpdateMemoryToolUI,
	execute: SandboxExecuteToolUI,
	execute_code: SandboxExecuteToolUI,
	create_notion_page: CreateNotionPageToolUI,
	update_notion_page: UpdateNotionPageToolUI,
	delete_notion_page: DeleteNotionPageToolUI,
	create_linear_issue: CreateLinearIssueToolUI,
	update_linear_issue: UpdateLinearIssueToolUI,
	delete_linear_issue: DeleteLinearIssueToolUI,
	create_google_drive_file: CreateGoogleDriveFileToolUI,
	delete_google_drive_file: DeleteGoogleDriveFileToolUI,
	create_onedrive_file: CreateOneDriveFileToolUI,
	delete_onedrive_file: DeleteOneDriveFileToolUI,
	create_dropbox_file: CreateDropboxFileToolUI,
	delete_dropbox_file: DeleteDropboxFileToolUI,
	create_calendar_event: CreateCalendarEventToolUI,
	update_calendar_event: UpdateCalendarEventToolUI,
	delete_calendar_event: DeleteCalendarEventToolUI,
	create_gmail_draft: CreateGmailDraftToolUI,
	update_gmail_draft: UpdateGmailDraftToolUI,
	send_gmail_email: SendGmailEmailToolUI,
	trash_gmail_email: TrashGmailEmailToolUI,
	create_jira_issue: CreateJiraIssueToolUI,
	update_jira_issue: UpdateJiraIssueToolUI,
	delete_jira_issue: DeleteJiraIssueToolUI,
	create_confluence_page: CreateConfluencePageToolUI,
	update_confluence_page: UpdateConfluencePageToolUI,
	delete_confluence_page: DeleteConfluencePageToolUI,
	link_preview: NullTimelineBody,
	multi_link_preview: NullTimelineBody,
	scrape_webpage: NullTimelineBody,
} as unknown as Record<string, TimelineToolComponent>;

/**
 * Lookup a tool component by name. Returns ``undefined`` for unknown
 * tools so the caller can mount ``FallbackToolBody`` instead.
 */
export function getToolComponent(toolName: string): TimelineToolComponent | undefined {
	return TOOLS_BY_NAME[toolName];
}

export const TIMELINE_TOOL_NAMES = Object.keys(TOOLS_BY_NAME) as readonly string[];
