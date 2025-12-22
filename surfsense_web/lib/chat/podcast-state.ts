/**
 * Module-level state for tracking active podcast generation.
 * Used by the new-chat adapter to prevent duplicate podcast requests.
 */

type PodcastStateListener = (isGenerating: boolean) => void;

let _activePodcastTaskId: string | null = null;
const _listeners: Set<PodcastStateListener> = new Set();

/**
 * Check if a podcast is currently being generated
 */
export function isPodcastGenerating(): boolean {
	return _activePodcastTaskId !== null;
}

/**
 * Get the active podcast task ID
 */
export function getActivePodcastTaskId(): string | null {
	return _activePodcastTaskId;
}

/**
 * Set the active podcast task ID (when podcast generation starts)
 */
export function setActivePodcastTaskId(taskId: string): void {
	_activePodcastTaskId = taskId;
	notifyListeners();
}

/**
 * Clear the active podcast task ID (when podcast generation completes or errors)
 */
export function clearActivePodcastTaskId(): void {
	_activePodcastTaskId = null;
	notifyListeners();
}

/**
 * Subscribe to podcast state changes
 */
export function subscribeToPodcastState(listener: PodcastStateListener): () => void {
	_listeners.add(listener);
	return () => {
		_listeners.delete(listener);
	};
}

function notifyListeners(): void {
	const isGenerating = _activePodcastTaskId !== null;
	for (const listener of _listeners) {
		listener(isGenerating);
	}
}

/**
 * Check if a message looks like a podcast request
 */
export function looksLikePodcastRequest(message: string): boolean {
	const podcastPatterns = [
		/\bpodcast\b/i,
		/\bcreate.*podcast\b/i,
		/\bgenerate.*podcast\b/i,
		/\bmake.*podcast\b/i,
		/\bturn.*into.*podcast\b/i,
		/\bpodcast.*about\b/i,
		/\bgive.*podcast\b/i,
	];

	return podcastPatterns.some((pattern) => pattern.test(message));
}
