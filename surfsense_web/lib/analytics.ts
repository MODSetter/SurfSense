/**
 * PostHog Analytics Utility
 * Provides typed event tracking functions for SurfSense
 */

import posthog from "posthog-js";

// Check if PostHog is initialized
function isPostHogReady(): boolean {
	return typeof window !== "undefined" && !!process.env.NEXT_PUBLIC_POSTHOG_KEY;
}

// =============================================================================
// Event Names (Constants for consistency)
// =============================================================================

export const ANALYTICS_EVENTS = {
	// Authentication
	USER_SIGNED_UP: "user_signed_up",
	USER_LOGGED_IN: "user_logged_in",
	USER_LOGGED_OUT: "user_logged_out",

	// Search Spaces
	SEARCH_SPACE_CREATED: "search_space_created",
	SEARCH_SPACE_DELETED: "search_space_deleted",

	// Chat
	CHAT_CREATED: "chat_created",
	MESSAGE_SENT: "message_sent",
	CHAT_DELETED: "chat_deleted",

	// Documents
	DOCUMENT_INDEXED: "document_indexed",
	DOCUMENT_DELETED: "document_deleted",

	// Connectors
	CONNECTOR_ADDED: "connector_added",
	CONNECTOR_DELETED: "connector_deleted",
	CONNECTOR_INDEXED: "connector_indexed",

	// Podcasts
	PODCAST_GENERATED: "podcast_generated",
	PODCAST_DELETED: "podcast_deleted",

	// LLM Config
	LLM_CONFIG_CREATED: "llm_config_created",

	// Invites
	INVITE_CREATED: "invite_created",
	INVITE_ACCEPTED: "invite_accepted",
} as const;

// =============================================================================
// Authentication Events
// =============================================================================

export function trackUserSignedUp(properties?: { method?: "email" | "google" }) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.USER_SIGNED_UP, properties);
}

export function trackUserLoggedIn(properties?: { method?: "email" | "google" }) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.USER_LOGGED_IN, properties);
}

export function trackUserLoggedOut() {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.USER_LOGGED_OUT);
}

// =============================================================================
// Search Space Events
// =============================================================================

export function trackSearchSpaceCreated(properties: { search_space_id: number; name: string }) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.SEARCH_SPACE_CREATED, properties);
}

export function trackSearchSpaceDeleted(properties: { search_space_id: number }) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.SEARCH_SPACE_DELETED, properties);
}

// =============================================================================
// Chat Events
// =============================================================================

export function trackChatCreated(properties: { search_space_id: number; thread_id: number }) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.CHAT_CREATED, properties);
}

export function trackMessageSent(properties: {
	search_space_id: number;
	thread_id: number;
	role: "user" | "assistant" | "system";
}) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.MESSAGE_SENT, properties);
}

export function trackChatDeleted(properties: { search_space_id: number; thread_id: number }) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.CHAT_DELETED, properties);
}

// =============================================================================
// Document Events
// =============================================================================

export function trackDocumentIndexed(properties: {
	search_space_id: number;
	document_type: string;
	count?: number;
}) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.DOCUMENT_INDEXED, {
		...properties,
		count: properties.count ?? 1,
	});
}

export function trackDocumentDeleted(properties: { search_space_id: number; document_id: number }) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.DOCUMENT_DELETED, properties);
}

// =============================================================================
// Connector Events
// =============================================================================

export function trackConnectorAdded(properties: {
	search_space_id: number;
	connector_type: string;
	connector_id?: number;
}) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.CONNECTOR_ADDED, properties);
}

export function trackConnectorDeleted(properties: {
	search_space_id: number;
	connector_type: string;
	connector_id: number;
}) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.CONNECTOR_DELETED, properties);
}

export function trackConnectorIndexed(properties: {
	search_space_id: number;
	connector_type: string;
	connector_id: number;
}) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.CONNECTOR_INDEXED, properties);
}

// =============================================================================
// Podcast Events
// =============================================================================

export function trackPodcastGenerated(properties: { search_space_id: number; podcast_id: number }) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.PODCAST_GENERATED, properties);
}

export function trackPodcastDeleted(properties: { search_space_id: number; podcast_id: number }) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.PODCAST_DELETED, properties);
}

// =============================================================================
// LLM Config Events
// =============================================================================

export function trackLLMConfigCreated(properties: {
	search_space_id: number;
	provider: string;
	model_name: string;
}) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.LLM_CONFIG_CREATED, properties);
}

// =============================================================================
// Invite Events
// =============================================================================

export function trackInviteCreated(properties: { search_space_id: number; role_name?: string }) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.INVITE_CREATED, properties);
}

export function trackInviteAccepted(properties: { search_space_id: number; invite_code: string }) {
	if (!isPostHogReady()) return;
	posthog.capture(ANALYTICS_EVENTS.INVITE_ACCEPTED, properties);
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Generic event capture for custom events
 */
export function trackEvent(eventName: string, properties?: Record<string, unknown>) {
	if (!isPostHogReady()) return;
	posthog.capture(eventName, properties);
}

/**
 * Reset PostHog user identification (call on logout)
 */
export function resetAnalytics() {
	if (!isPostHogReady()) return;
	posthog.reset();
}
