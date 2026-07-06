import posthog from "posthog-js";
import type { ChatErrorKind, ChatErrorSeverity, ChatFlow } from "@/lib/chat/chat-error-classifier";
import { getConnectorTelemetryMeta } from "@/lib/connector-telemetry";

/**
 * PostHog Analytics Event Definitions
 *
 * All capture/identify/reset calls are wrapped in try-catch so that
 * ad-blockers that interfere with posthog-js can never break app
 * functionality (e.g. the chat flow).
 *
 * Events follow a consistent naming convention: category_action
 *
 * Categories:
 * - auth: Authentication events
 * - workspace: Search space management
 * - document: Document management
 * - chat: Chat and messaging (authenticated + anonymous)
 * - connector: External connector events (all lifecycle stages)
 * - contact: Contact form events
 * - settings: Settings changes
 * - automation: Automation lifecycle (create/update/delete/trigger/chat)
 * - marketing: Marketing/referral tracking
 */

function safeCapture(event: string, properties?: Record<string, unknown>) {
	try {
		posthog.capture(event, properties);
	} catch {
		// Silently ignore – analytics should never break the app
	}
}

/**
 * Drop undefined values so PostHog doesn't log `"foo": undefined` noise.
 */
function compact<T extends object>(obj: T): Record<string, unknown> {
	const out: Record<string, unknown> = {};
	for (const [k, v] of Object.entries(obj)) {
		if (v !== undefined) out[k] = v;
	}
	return out;
}

// ============================================
// AUTH EVENTS
// ============================================

export function trackLoginAttempt(method: "local" | "google") {
	safeCapture("auth_login_attempt", { method });
}

export function trackLoginSuccess(method: "local" | "google") {
	safeCapture("auth_login_success", { method });
}

export function trackLoginFailure(method: "local" | "google", error?: string) {
	safeCapture("auth_login_failure", { method, error });
}

export function trackRegistrationAttempt() {
	safeCapture("auth_registration_attempt");
}

export function trackRegistrationSuccess() {
	safeCapture("auth_registration_success");
}

export function trackRegistrationFailure(error?: string) {
	safeCapture("auth_registration_failure", { error });
}

export function trackLogout() {
	safeCapture("auth_logout");
}

// ============================================
// SEARCH SPACE EVENTS
// ============================================

export function trackWorkspaceCreated(workspaceId: number, name: string) {
	safeCapture("workspace_created", {
		workspace_id: workspaceId,
		name,
	});
}

export function trackWorkspaceDeleted(workspaceId: number) {
	safeCapture("workspace_deleted", {
		workspace_id: workspaceId,
	});
}

export function trackWorkspaceViewed(workspaceId: number) {
	safeCapture("workspace_viewed", {
		workspace_id: workspaceId,
	});
}

// ============================================
// CHAT EVENTS
// ============================================

export function trackChatCreated(workspaceId: number, chatId: number) {
	safeCapture("chat_created", {
		workspace_id: workspaceId,
		chat_id: chatId,
	});
}

export function trackChatMessageSent(
	workspaceId: number,
	chatId: number,
	options?: {
		hasAttachments?: boolean;
		hasMentionedDocuments?: boolean;
		messageLength?: number;
	}
) {
	safeCapture("chat_message_sent", {
		workspace_id: workspaceId,
		chat_id: chatId,
		has_attachments: options?.hasAttachments ?? false,
		has_mentioned_documents: options?.hasMentionedDocuments ?? false,
		message_length: options?.messageLength,
	});
}

export function trackChatResponseReceived(workspaceId: number, chatId: number) {
	safeCapture("chat_response_received", {
		workspace_id: workspaceId,
		chat_id: chatId,
	});
}

export function trackChatError(workspaceId: number, chatId: number, error?: string) {
	safeCapture("chat_error", {
		workspace_id: workspaceId,
		chat_id: chatId,
		error,
	});
}

export interface ChatFailureTelemetry {
	flow: ChatFlow;
	kind: ChatErrorKind;
	error_code?: string;
	severity: ChatErrorSeverity;
	is_expected: boolean;
	message?: string;
}

export function trackChatBlocked(
	workspaceId: number,
	chatId: number | null,
	payload: ChatFailureTelemetry
) {
	safeCapture(
		"chat_blocked",
		compact({
			workspace_id: workspaceId,
			chat_id: chatId ?? undefined,
			flow: payload.flow,
			kind: payload.kind,
			error_code: payload.error_code,
			severity: payload.severity,
			is_expected: payload.is_expected,
			message: payload.message,
		})
	);
}

export function trackChatErrorDetailed(
	workspaceId: number,
	chatId: number | null,
	payload: ChatFailureTelemetry
) {
	safeCapture(
		"chat_error",
		compact({
			workspace_id: workspaceId,
			chat_id: chatId ?? undefined,
			flow: payload.flow,
			kind: payload.kind,
			error_code: payload.error_code,
			severity: payload.severity,
			is_expected: payload.is_expected,
			message: payload.message,
		})
	);
}

/**
 * Track a message sent from the unauthenticated "free" / anonymous chat
 * flow. This is intentionally a separate event from `chat_message_sent`
 * so WAU / retention queries on the authenticated event stay clean while
 * still giving us visibility into top-of-funnel usage on /free/*.
 */
export function trackAnonymousChatMessageSent(options: {
	modelSlug: string;
	messageLength?: number;
	hasUploadedDoc?: boolean;
	surface?: "free_chat_page" | "free_model_page";
}) {
	safeCapture("anonymous_chat_message_sent", {
		model_slug: options.modelSlug,
		message_length: options.messageLength,
		has_uploaded_doc: options.hasUploadedDoc ?? false,
		surface: options.surface,
	});
}

// ============================================
// DOCUMENT EVENTS
// ============================================

export function trackDocumentUploadStarted(
	workspaceId: number,
	fileCount: number,
	totalSizeBytes: number
) {
	safeCapture("document_upload_started", {
		workspace_id: workspaceId,
		file_count: fileCount,
		total_size_bytes: totalSizeBytes,
	});
}

export function trackDocumentUploadSuccess(workspaceId: number, fileCount: number) {
	safeCapture("document_upload_success", {
		workspace_id: workspaceId,
		file_count: fileCount,
	});
}

export function trackDocumentUploadFailure(workspaceId: number, error?: string) {
	safeCapture("document_upload_failure", {
		workspace_id: workspaceId,
		error,
	});
}

export function trackDocumentDeleted(workspaceId: number, documentId: number) {
	safeCapture("document_deleted", {
		workspace_id: workspaceId,
		document_id: documentId,
	});
}

export function trackDocumentBulkDeleted(workspaceId: number, count: number) {
	safeCapture("document_bulk_deleted", {
		workspace_id: workspaceId,
		count,
	});
}

export function trackYouTubeImport(workspaceId: number, url: string) {
	safeCapture("youtube_import_started", {
		workspace_id: workspaceId,
		url,
	});
}

// ============================================
// CONNECTOR EVENTS (generic lifecycle dispatcher)
// ============================================
//
// All connector events go through `trackConnectorEvent`. The connector's
// human-readable title and its group (oauth/composio/crawler/other) are
// auto-attached from the shared registry in `connector-constants.ts`, so
// adding a new connector to that list is the only change required for it
// to show up correctly in PostHog dashboards.

export type ConnectorEventStage =
	| "setup_started"
	| "setup_success"
	| "setup_failure"
	| "oauth_initiated"
	| "connected"
	| "deleted"
	| "synced";

export interface ConnectorEventOptions {
	workspaceId?: number | null;
	connectorId?: number | null;
	/** Source of the action (e.g. "oauth_callback", "non_oauth_form", "webcrawler_quick_add"). */
	source?: string;
	/** Free-form error message for failure events. */
	error?: string;
	/** Extra properties specific to the stage (e.g. frequency_minutes for sync events). */
	extra?: Record<string, unknown>;
}

/**
 * Generic connector lifecycle tracker. Every connector analytics event
 * should funnel through here so the enrichment stays consistent.
 */
export function trackConnectorEvent(
	stage: ConnectorEventStage,
	connectorType: string,
	options: ConnectorEventOptions = {}
) {
	const meta = getConnectorTelemetryMeta(connectorType);
	safeCapture(`connector_${stage}`, {
		...compact({
			workspace_id: options.workspaceId ?? undefined,
			connector_id: options.connectorId ?? undefined,
			source: options.source,
			error: options.error,
		}),
		connector_type: meta.connector_type,
		connector_title: meta.connector_title,
		connector_group: meta.connector_group,
		is_oauth: meta.is_oauth,
		...(options.extra ?? {}),
	});
}

// ---- Convenience wrappers kept for backward compatibility ----

export function trackConnectorSetupStarted(
	workspaceId: number,
	connectorType: string,
	source?: string
) {
	trackConnectorEvent("setup_started", connectorType, { workspaceId, source });
}

export function trackConnectorSetupSuccess(
	workspaceId: number,
	connectorType: string,
	connectorId: number
) {
	trackConnectorEvent("setup_success", connectorType, { workspaceId, connectorId });
}

export function trackConnectorSetupFailure(
	workspaceId: number | null | undefined,
	connectorType: string,
	error?: string,
	source?: string
) {
	trackConnectorEvent("setup_failure", connectorType, {
		workspaceId: workspaceId ?? undefined,
		error,
		source,
	});
}

export function trackConnectorDeleted(
	workspaceId: number,
	connectorType: string,
	connectorId: number
) {
	trackConnectorEvent("deleted", connectorType, { workspaceId, connectorId });
}

export function trackConnectorSynced(
	workspaceId: number,
	connectorType: string,
	connectorId: number
) {
	trackConnectorEvent("synced", connectorType, { workspaceId, connectorId });
}

// ============================================
// SETTINGS EVENTS
// ============================================

export function trackSettingsViewed(workspaceId: number, section: string) {
	safeCapture("settings_viewed", {
		workspace_id: workspaceId,
		section,
	});
}

export function trackSettingsUpdated(workspaceId: number, section: string, setting: string) {
	safeCapture("settings_updated", {
		workspace_id: workspaceId,
		section,
		setting,
	});
}

// ============================================
// FEATURE USAGE EVENTS
// ============================================

export function trackPodcastGenerated(workspaceId: number, chatId: number) {
	safeCapture("podcast_generated", {
		workspace_id: workspaceId,
		chat_id: chatId,
	});
}

export function trackSourcesTabViewed(workspaceId: number, tab: string) {
	safeCapture("sources_tab_viewed", {
		workspace_id: workspaceId,
		tab,
	});
}

export function trackDesktopDownloadClicked(options: {
	os: string;
	placement: "sidebar_collapsed" | "sidebar_expanded";
}) {
	safeCapture("desktop_download_clicked", {
		os: options.os,
		placement: options.placement,
	});
}

// ============================================
// SEARCH SPACE INVITE EVENTS
// ============================================

export function trackWorkspaceInviteSent(
	workspaceId: number,
	options?: {
		roleName?: string;
		hasExpiry?: boolean;
		hasMaxUses?: boolean;
	}
) {
	safeCapture("workspace_invite_sent", {
		workspace_id: workspaceId,
		role_name: options?.roleName,
		has_expiry: options?.hasExpiry ?? false,
		has_max_uses: options?.hasMaxUses ?? false,
	});
}

export function trackWorkspaceInviteAccepted(
	workspaceId: number,
	workspaceName: string,
	roleName?: string | null
) {
	safeCapture("workspace_invite_accepted", {
		workspace_id: workspaceId,
		workspace_name: workspaceName,
		role_name: roleName,
	});
}

export function trackWorkspaceInviteDeclined(workspaceName?: string) {
	safeCapture("workspace_invite_declined", {
		workspace_name: workspaceName,
	});
}

export function trackWorkspaceUserAdded(
	workspaceId: number,
	workspaceName: string,
	roleName?: string | null
) {
	safeCapture("workspace_user_added", {
		workspace_id: workspaceId,
		workspace_name: workspaceName,
		role_name: roleName,
	});
}

export function trackWorkspaceUsersViewed(
	workspaceId: number,
	userCount: number,
	ownerCount: number
) {
	safeCapture("workspace_users_viewed", {
		workspace_id: workspaceId,
		user_count: userCount,
		owner_count: ownerCount,
	});
}

// ============================================
// CONNECTOR CONNECTION EVENTS
// ============================================

export function trackConnectorConnected(
	workspaceId: number,
	connectorType: string,
	connectorId?: number
) {
	trackConnectorEvent("connected", connectorType, {
		workspaceId,
		connectorId: connectorId ?? undefined,
	});
}

// ============================================
// INDEXING EVENTS
// ============================================

export function trackIndexWithDateRangeOpened(
	workspaceId: number,
	connectorType: string,
	connectorId: number
) {
	safeCapture("index_with_date_range_opened", {
		workspace_id: workspaceId,
		connector_type: connectorType,
		connector_id: connectorId,
	});
}

export function trackIndexWithDateRangeStarted(
	workspaceId: number,
	connectorType: string,
	connectorId: number,
	options?: {
		hasStartDate?: boolean;
		hasEndDate?: boolean;
	}
) {
	safeCapture("index_with_date_range_started", {
		workspace_id: workspaceId,
		connector_type: connectorType,
		connector_id: connectorId,
		has_start_date: options?.hasStartDate ?? false,
		has_end_date: options?.hasEndDate ?? false,
	});
}

export function trackQuickIndexClicked(
	workspaceId: number,
	connectorType: string,
	connectorId: number
) {
	safeCapture("quick_index_clicked", {
		workspace_id: workspaceId,
		connector_type: connectorType,
		connector_id: connectorId,
	});
}

export function trackConfigurePeriodicIndexingOpened(
	workspaceId: number,
	connectorType: string,
	connectorId: number
) {
	safeCapture("configure_periodic_indexing_opened", {
		workspace_id: workspaceId,
		connector_type: connectorType,
		connector_id: connectorId,
	});
}

export function trackPeriodicIndexingStarted(
	workspaceId: number,
	connectorType: string,
	connectorId: number,
	frequencyMinutes: number
) {
	safeCapture("periodic_indexing_started", {
		workspace_id: workspaceId,
		connector_type: connectorType,
		connector_id: connectorId,
		frequency_minutes: frequencyMinutes,
	});
}

// ============================================
// INCENTIVE TASKS EVENTS
// ============================================

export function trackIncentivePageViewed() {
	safeCapture("incentive_page_viewed");
}

export function trackIncentiveTaskCompleted(taskType: string, creditMicrosRewarded: number) {
	safeCapture("incentive_task_completed", {
		task_type: taskType,
		credit_micros_rewarded: creditMicrosRewarded,
	});
}

export function trackIncentiveTaskClicked(taskType: string) {
	safeCapture("incentive_task_clicked", {
		task_type: taskType,
	});
}

export function trackIncentiveContactOpened() {
	safeCapture("incentive_contact_opened");
}

// ============================================
// MARKETING / REFERRAL EVENTS
// ============================================

export function trackReferralLanding(refCode: string, landingUrl: string) {
	safeCapture("marketing_referral_landing", {
		ref_code: refCode,
		landing_url: landingUrl,
		$set_once: { first_ref_code: refCode },
		$set: { latest_ref_code: refCode },
	});
}

// ============================================
// AUTOMATION EVENTS
// ============================================

interface AutomationCreatedProps {
	workspace_id: number;
	automation_id: number;
	task_count?: number;
	trigger_type?: string;
	has_schedule?: boolean;
	chat_model_id?: number;
	image_gen_model_id?: number;
	vision_model_id?: number;
	tags_count?: number;
}

export function trackAutomationCreated(props: AutomationCreatedProps) {
	safeCapture("automation_created", compact(props));
}

export function trackAutomationCreateFailed(props: { workspace_id?: number; error?: string }) {
	safeCapture("automation_create_failed", compact(props));
}

export function trackAutomationUpdated(props: {
	automation_id: number;
	workspace_id?: number;
	has_definition_change?: boolean;
	has_name_change?: boolean;
	has_description_change?: boolean;
	task_count?: number;
}) {
	safeCapture("automation_updated", compact(props));
}

export function trackAutomationStatusChanged(props: {
	automation_id: number;
	workspace_id?: number;
	next_status: string;
}) {
	safeCapture("automation_status_changed", compact(props));
}

export function trackAutomationUpdateFailed(props: { automation_id: number; error?: string }) {
	safeCapture("automation_update_failed", compact(props));
}

export function trackAutomationDeleted(props: { automation_id: number; workspace_id?: number }) {
	safeCapture("automation_deleted", compact(props));
}

export function trackAutomationDeleteFailed(props: { automation_id: number; error?: string }) {
	safeCapture("automation_delete_failed", compact(props));
}

export function trackAutomationTriggerAdded(props: {
	automation_id: number;
	trigger_id?: number;
	trigger_type?: string;
	enabled?: boolean;
	has_cron?: boolean;
}) {
	safeCapture("automation_trigger_added", compact(props));
}

export function trackAutomationTriggerAddFailed(props: { automation_id: number; error?: string }) {
	safeCapture("automation_trigger_add_failed", compact(props));
}

export function trackAutomationTriggerUpdated(props: {
	automation_id: number;
	trigger_id: number;
	change?: "enabled" | "params" | "other";
	enabled?: boolean;
}) {
	safeCapture("automation_trigger_updated", compact(props));
}

export function trackAutomationTriggerUpdateFailed(props: {
	automation_id: number;
	trigger_id: number;
	error?: string;
}) {
	safeCapture("automation_trigger_update_failed", compact(props));
}

export function trackAutomationTriggerRemoved(props: {
	automation_id: number;
	trigger_id: number;
}) {
	safeCapture("automation_trigger_removed", compact(props));
}

export function trackAutomationTriggerRemoveFailed(props: {
	automation_id: number;
	trigger_id: number;
	error?: string;
}) {
	safeCapture("automation_trigger_remove_failed", compact(props));
}

interface AutomationChatDecisionProps {
	workspace_id?: number;
	edited?: boolean;
	task_count?: number;
	trigger_type?: string;
	chat_model_id?: number;
	image_gen_model_id?: number;
	vision_model_id?: number;
}

export function trackAutomationChatApproved(props: AutomationChatDecisionProps) {
	safeCapture("automation_chat_approved", compact(props));
}

export function trackAutomationChatRejected(props: { workspace_id?: number }) {
	safeCapture("automation_chat_rejected", compact(props));
}

export function trackAutomationChatDraftEdited(props: { workspace_id?: number }) {
	safeCapture("automation_chat_draft_edited", compact(props));
}

export function trackAutomationChatCreateSucceeded(props: {
	automation_id: number;
	name?: string;
	workspace_id?: number;
}) {
	safeCapture("automation_chat_create_succeeded", compact(props));
}

export function trackAutomationChatCreateFailed(props: {
	reason: "invalid" | "error";
	workspace_id?: number;
	issue_count?: number;
	message?: string;
}) {
	safeCapture("automation_chat_create_failed", compact(props));
}

// ============================================
// USER IDENTIFICATION
// ============================================

/**
 * Identify a user for PostHog analytics.
 * Call this after successful authentication.
 *
 * In the Electron desktop app the same call is mirrored into the
 * main-process PostHog client so desktop-only events (e.g.
 * `desktop_quick_ask_opened`, `desktop_autocomplete_accepted`) are
 * attributed to the logged-in user rather than an anonymous machine ID.
 */
export function identifyUser(userId: string, properties?: Record<string, unknown>) {
	try {
		posthog.identify(userId, properties);
	} catch {
		// Silently ignore – ad-blockers may break posthog
	}

	try {
		if (typeof window !== "undefined" && window.electronAPI?.analyticsIdentify) {
			void window.electronAPI.analyticsIdentify(userId, properties);
		}
	} catch {
		// IPC errors must never break the app
	}
}

/**
 * Reset user identity (call on logout). Mirrors the reset into the
 * Electron main process when running inside the desktop app.
 */
export function resetUser() {
	try {
		posthog.reset();
	} catch {
		// Silently ignore – ad-blockers may break posthog
	}

	try {
		if (typeof window !== "undefined" && window.electronAPI?.analyticsReset) {
			void window.electronAPI.analyticsReset();
		}
	} catch {
		// IPC errors must never break the app
	}
}
