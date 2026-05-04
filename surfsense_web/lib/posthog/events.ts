import posthog from "posthog-js";
import { getConnectorTelemetryMeta } from "@/components/assistant-ui/connector-popup/constants/connector-constants";
import type { ChatErrorKind, ChatErrorSeverity, ChatFlow } from "@/lib/chat/chat-error-classifier";

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
 * - search_space: Search space management
 * - document: Document management
 * - chat: Chat and messaging (authenticated + anonymous)
 * - connector: External connector events (all lifecycle stages)
 * - contact: Contact form events
 * - settings: Settings changes
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
function compact<T extends Record<string, unknown>>(obj: T): Record<string, unknown> {
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

export function trackSearchSpaceCreated(searchSpaceId: number, name: string) {
	safeCapture("search_space_created", {
		search_space_id: searchSpaceId,
		name,
	});
}

export function trackSearchSpaceDeleted(searchSpaceId: number) {
	safeCapture("search_space_deleted", {
		search_space_id: searchSpaceId,
	});
}

export function trackSearchSpaceViewed(searchSpaceId: number) {
	safeCapture("search_space_viewed", {
		search_space_id: searchSpaceId,
	});
}

// ============================================
// CHAT EVENTS
// ============================================

export function trackChatCreated(searchSpaceId: number, chatId: number) {
	safeCapture("chat_created", {
		search_space_id: searchSpaceId,
		chat_id: chatId,
	});
}

export function trackChatMessageSent(
	searchSpaceId: number,
	chatId: number,
	options?: {
		hasAttachments?: boolean;
		hasMentionedDocuments?: boolean;
		messageLength?: number;
	}
) {
	safeCapture("chat_message_sent", {
		search_space_id: searchSpaceId,
		chat_id: chatId,
		has_attachments: options?.hasAttachments ?? false,
		has_mentioned_documents: options?.hasMentionedDocuments ?? false,
		message_length: options?.messageLength,
	});
}

export function trackChatResponseReceived(searchSpaceId: number, chatId: number) {
	safeCapture("chat_response_received", {
		search_space_id: searchSpaceId,
		chat_id: chatId,
	});
}

export function trackChatError(searchSpaceId: number, chatId: number, error?: string) {
	safeCapture("chat_error", {
		search_space_id: searchSpaceId,
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
	searchSpaceId: number,
	chatId: number | null,
	payload: ChatFailureTelemetry
) {
	safeCapture(
		"chat_blocked",
		compact({
			search_space_id: searchSpaceId,
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
	searchSpaceId: number,
	chatId: number | null,
	payload: ChatFailureTelemetry
) {
	safeCapture(
		"chat_error",
		compact({
			search_space_id: searchSpaceId,
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
	webSearchEnabled?: boolean;
	surface?: "free_chat_page" | "free_model_page";
}) {
	safeCapture("anonymous_chat_message_sent", {
		model_slug: options.modelSlug,
		message_length: options.messageLength,
		has_uploaded_doc: options.hasUploadedDoc ?? false,
		web_search_enabled: options.webSearchEnabled,
		surface: options.surface,
	});
}

// ============================================
// DOCUMENT EVENTS
// ============================================

export function trackDocumentUploadStarted(
	searchSpaceId: number,
	fileCount: number,
	totalSizeBytes: number
) {
	safeCapture("document_upload_started", {
		search_space_id: searchSpaceId,
		file_count: fileCount,
		total_size_bytes: totalSizeBytes,
	});
}

export function trackDocumentUploadSuccess(searchSpaceId: number, fileCount: number) {
	safeCapture("document_upload_success", {
		search_space_id: searchSpaceId,
		file_count: fileCount,
	});
}

export function trackDocumentUploadFailure(searchSpaceId: number, error?: string) {
	safeCapture("document_upload_failure", {
		search_space_id: searchSpaceId,
		error,
	});
}

export function trackDocumentDeleted(searchSpaceId: number, documentId: number) {
	safeCapture("document_deleted", {
		search_space_id: searchSpaceId,
		document_id: documentId,
	});
}

export function trackDocumentBulkDeleted(searchSpaceId: number, count: number) {
	safeCapture("document_bulk_deleted", {
		search_space_id: searchSpaceId,
		count,
	});
}

export function trackYouTubeImport(searchSpaceId: number, url: string) {
	safeCapture("youtube_import_started", {
		search_space_id: searchSpaceId,
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
	searchSpaceId?: number | null;
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
			search_space_id: options.searchSpaceId ?? undefined,
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
	searchSpaceId: number,
	connectorType: string,
	source?: string
) {
	trackConnectorEvent("setup_started", connectorType, { searchSpaceId, source });
}

export function trackConnectorSetupSuccess(
	searchSpaceId: number,
	connectorType: string,
	connectorId: number
) {
	trackConnectorEvent("setup_success", connectorType, { searchSpaceId, connectorId });
}

export function trackConnectorSetupFailure(
	searchSpaceId: number | null | undefined,
	connectorType: string,
	error?: string,
	source?: string
) {
	trackConnectorEvent("setup_failure", connectorType, {
		searchSpaceId: searchSpaceId ?? undefined,
		error,
		source,
	});
}

export function trackConnectorDeleted(
	searchSpaceId: number,
	connectorType: string,
	connectorId: number
) {
	trackConnectorEvent("deleted", connectorType, { searchSpaceId, connectorId });
}

export function trackConnectorSynced(
	searchSpaceId: number,
	connectorType: string,
	connectorId: number
) {
	trackConnectorEvent("synced", connectorType, { searchSpaceId, connectorId });
}

// ============================================
// SETTINGS EVENTS
// ============================================

export function trackSettingsViewed(searchSpaceId: number, section: string) {
	safeCapture("settings_viewed", {
		search_space_id: searchSpaceId,
		section,
	});
}

export function trackSettingsUpdated(searchSpaceId: number, section: string, setting: string) {
	safeCapture("settings_updated", {
		search_space_id: searchSpaceId,
		section,
		setting,
	});
}

// ============================================
// FEATURE USAGE EVENTS
// ============================================

export function trackPodcastGenerated(searchSpaceId: number, chatId: number) {
	safeCapture("podcast_generated", {
		search_space_id: searchSpaceId,
		chat_id: chatId,
	});
}

export function trackSourcesTabViewed(searchSpaceId: number, tab: string) {
	safeCapture("sources_tab_viewed", {
		search_space_id: searchSpaceId,
		tab,
	});
}

// ============================================
// SEARCH SPACE INVITE EVENTS
// ============================================

export function trackSearchSpaceInviteSent(
	searchSpaceId: number,
	options?: {
		roleName?: string;
		hasExpiry?: boolean;
		hasMaxUses?: boolean;
	}
) {
	safeCapture("search_space_invite_sent", {
		search_space_id: searchSpaceId,
		role_name: options?.roleName,
		has_expiry: options?.hasExpiry ?? false,
		has_max_uses: options?.hasMaxUses ?? false,
	});
}

export function trackSearchSpaceInviteAccepted(
	searchSpaceId: number,
	searchSpaceName: string,
	roleName?: string | null
) {
	safeCapture("search_space_invite_accepted", {
		search_space_id: searchSpaceId,
		search_space_name: searchSpaceName,
		role_name: roleName,
	});
}

export function trackSearchSpaceInviteDeclined(searchSpaceName?: string) {
	safeCapture("search_space_invite_declined", {
		search_space_name: searchSpaceName,
	});
}

export function trackSearchSpaceUserAdded(
	searchSpaceId: number,
	searchSpaceName: string,
	roleName?: string | null
) {
	safeCapture("search_space_user_added", {
		search_space_id: searchSpaceId,
		search_space_name: searchSpaceName,
		role_name: roleName,
	});
}

export function trackSearchSpaceUsersViewed(
	searchSpaceId: number,
	userCount: number,
	ownerCount: number
) {
	safeCapture("search_space_users_viewed", {
		search_space_id: searchSpaceId,
		user_count: userCount,
		owner_count: ownerCount,
	});
}

// ============================================
// CONNECTOR CONNECTION EVENTS
// ============================================

export function trackConnectorConnected(
	searchSpaceId: number,
	connectorType: string,
	connectorId?: number
) {
	trackConnectorEvent("connected", connectorType, {
		searchSpaceId,
		connectorId: connectorId ?? undefined,
	});
}

// ============================================
// INDEXING EVENTS
// ============================================

export function trackIndexWithDateRangeOpened(
	searchSpaceId: number,
	connectorType: string,
	connectorId: number
) {
	safeCapture("index_with_date_range_opened", {
		search_space_id: searchSpaceId,
		connector_type: connectorType,
		connector_id: connectorId,
	});
}

export function trackIndexWithDateRangeStarted(
	searchSpaceId: number,
	connectorType: string,
	connectorId: number,
	options?: {
		hasStartDate?: boolean;
		hasEndDate?: boolean;
	}
) {
	safeCapture("index_with_date_range_started", {
		search_space_id: searchSpaceId,
		connector_type: connectorType,
		connector_id: connectorId,
		has_start_date: options?.hasStartDate ?? false,
		has_end_date: options?.hasEndDate ?? false,
	});
}

export function trackQuickIndexClicked(
	searchSpaceId: number,
	connectorType: string,
	connectorId: number
) {
	safeCapture("quick_index_clicked", {
		search_space_id: searchSpaceId,
		connector_type: connectorType,
		connector_id: connectorId,
	});
}

export function trackConfigurePeriodicIndexingOpened(
	searchSpaceId: number,
	connectorType: string,
	connectorId: number
) {
	safeCapture("configure_periodic_indexing_opened", {
		search_space_id: searchSpaceId,
		connector_type: connectorType,
		connector_id: connectorId,
	});
}

export function trackPeriodicIndexingStarted(
	searchSpaceId: number,
	connectorType: string,
	connectorId: number,
	frequencyMinutes: number
) {
	safeCapture("periodic_indexing_started", {
		search_space_id: searchSpaceId,
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

export function trackIncentiveTaskCompleted(taskType: string, pagesRewarded: number) {
	safeCapture("incentive_task_completed", {
		task_type: taskType,
		pages_rewarded: pagesRewarded,
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
