/**
 * Determines if a podcast is stale compared to the current chat state.
 * A podcast is considered stale if:
 * - The chat's current state_version is greater than the podcast's chat_state_version
 *
 * @param chatVersion - The current state_version of the chat
 * @param podcastVersion - The chat_state_version stored when the podcast was generated (nullable)
 * @returns true if the podcast is stale, false otherwise
 */
export function isPodcastStale(
	chatVersion: number,
	podcastVersion: number | null | undefined
): boolean {
	// If podcast has no version, it's stale (generated before this feature)
	if (!podcastVersion) {
		return true;
	}
	// If chat version is greater than podcast version, it's stale : We can change this condition to consider staleness after a huge number of updates
	return chatVersion > podcastVersion;
}

/**
 * Gets a human-readable message about podcast staleness
 *
 * @param chatVersion - The current state_version of the chat
 * @param podcastVersion - The chat_state_version stored when the podcast was generated
 * @returns A descriptive message about the podcast's staleness status
 */
export function getPodcastStalenessMessage(
	chatVersion: number,
	podcastVersion: number | null | undefined
): string {
	if (!podcastVersion) {
		return "This podcast was generated before chat updates were tracked. Consider regenerating it.";
	}

	if (chatVersion > podcastVersion) {
		const versionDiff = chatVersion - podcastVersion;
		return `This podcast is outdated. The chat has been updated ${versionDiff} time${versionDiff > 1 ? "s" : ""} since this podcast was generated.`;
	}

	return "This podcast is up to date with the current chat.";
}
