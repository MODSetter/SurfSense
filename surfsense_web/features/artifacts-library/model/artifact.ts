export type LibraryArtifactStatus = "ready" | "running" | "error";

/**
 * A deliverable aggregated for the library.
 *
 * ``artifactId`` is canonical and enables a deep link to the exact card in the
 * source chat. Legacy entries without one still link to their source thread.
 */
export interface LibraryArtifact {
	/** Stable list key for canonical and legacy deliverables. */
	key: string;
	/** Canonical backend format, or a compatibility format for legacy report rows. */
	format: string;
	/** Canonical Artifact id when listed from the Artifact API. */
	artifactId?: number;
	title: string;
	status: LibraryArtifactStatus;
	createdAt: string;
	/** Chat thread that produced this artifact, when the source recorded one. */
	sourceThreadId?: number | null;
}
