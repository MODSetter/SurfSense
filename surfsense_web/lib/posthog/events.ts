import posthog from "posthog-js";

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
 * - chat: Chat and messaging
 * - connector: External connector events
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
// CONNECTOR EVENTS
// ============================================

export function trackConnectorSetupStarted(searchSpaceId: number, connectorType: string) {
	safeCapture("connector_setup_started", {
		search_space_id: searchSpaceId,
		connector_type: connectorType,
	});
}

export function trackConnectorSetupSuccess(
	searchSpaceId: number,
	connectorType: string,
	connectorId: number
) {
	safeCapture("connector_setup_success", {
		search_space_id: searchSpaceId,
		connector_type: connectorType,
		connector_id: connectorId,
	});
}

export function trackConnectorSetupFailure(
	searchSpaceId: number,
	connectorType: string,
	error?: string
) {
	safeCapture("connector_setup_failure", {
		search_space_id: searchSpaceId,
		connector_type: connectorType,
		error,
	});
}

export function trackConnectorDeleted(
	searchSpaceId: number,
	connectorType: string,
	connectorId: number
) {
	safeCapture("connector_deleted", {
		search_space_id: searchSpaceId,
		connector_type: connectorType,
		connector_id: connectorId,
	});
}

export function trackConnectorSynced(
	searchSpaceId: number,
	connectorType: string,
	connectorId: number
) {
	safeCapture("connector_synced", {
		search_space_id: searchSpaceId,
		connector_type: connectorType,
		connector_id: connectorId,
	});
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
	safeCapture("connector_connected", {
		search_space_id: searchSpaceId,
		connector_type: connectorType,
		connector_id: connectorId,
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
 * Identify a user for PostHog analytics
 * Call this after successful authentication
 */
export function identifyUser(userId: string, properties?: Record<string, unknown>) {
	try {
		posthog.identify(userId, properties);
	} catch {
		// Silently ignore – ad-blockers may break posthog
	}
}

/**
 * Reset user identity (call on logout)
 */
export function resetUser() {
	try {
		posthog.reset();
	} catch {
		// Silently ignore – ad-blockers may break posthog
	}
}
