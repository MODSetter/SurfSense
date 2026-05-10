/**
 * Pure helpers for turning agent-facing virtual paths into human-friendly
 * chip labels.
 *
 * Why this lives in `lib` and not in the UI component:
 * - Pure function = trivial to unit-test (no React, no DOM).
 * - Used in two render sites today (the user-message chip and the AI-answer
 *   `MentionChip`) and likely more (history search, share-card previews, etc).
 *   Centralising the rules keeps the agent's path encoding and the UI's
 *   decoding from drifting apart.
 *
 * The agent emits paths under `/documents/...` with two encoding rules
 * applied by `surfsense_backend/app/agents/new_chat/path_resolver.py`:
 *
 * 1. Every basename ends with `.xml` (so the LLM treats KB documents as XML
 *    files). Display layer strips this — users think of the underlying
 *    filename, not the LLM's wrapper.
 * 2. Title collisions get a ` (<doc_id>).xml` disambiguation suffix.
 *    Display layer strips the parenthesised id since it's an implementation
 *    detail, not user-facing identity.
 */

const XML_EXTENSION_RE = /\.xml$/i;
const DOC_ID_DISAMBIG_RE = /\s\(\d+\)$/;

export interface VirtualPathDisplay {
	/** Human-friendly leaf name with `.xml` and ` (<doc_id>)` suffixes stripped. */
	displayName: string;
	/** Whether the path points to a folder (trailing slash) rather than a file. */
	isFolder: boolean;
}

/**
 * Decode a virtual path into the label that should appear in chip UI.
 *
 * Folder detection uses the trailing-slash convention the agent already
 * follows in `<priority_documents>` and `KnowledgeTreeMiddleware`. Falls
 * back to the raw path if nothing else can be extracted (defensive — the
 * caller will at least show *something*).
 */
export function getVirtualPathDisplay(path: string): VirtualPathDisplay {
	const trimmed = (path ?? "").trim();
	if (!trimmed) return { displayName: "", isFolder: false };

	const isFolder = trimmed.endsWith("/");
	const normalized = trimmed.replace(/\/+$/, "");
	const segments = normalized.split("/").filter(Boolean);
	const leaf = segments.at(-1);
	if (!leaf) return { displayName: trimmed, isFolder };

	const withoutXml = leaf.replace(XML_EXTENSION_RE, "");
	const displayName = withoutXml.replace(DOC_ID_DISAMBIG_RE, "");

	return { displayName: displayName || leaf, isFolder };
}
