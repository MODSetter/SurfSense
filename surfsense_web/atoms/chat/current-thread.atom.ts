import { atom } from "jotai";
import type { ChatVisibility } from "@/lib/chat/thread-persistence";

// TODO: Update `hasComments` to true when the first comment is created on a thread.
// Currently it only updates on thread load. The gutter still works because
// `addingCommentToMessageId` keeps it open, but the state is technically stale.

// TODO: Reset `addingCommentToMessageId` to null after a comment is successfully created.
// Currently it stays set until navigation or clicking another message's bubble.
// Not causing issues since panel visibility is driven by per-message comment count.

// TODO: Consider calling `resetCurrentThreadAtom` when unmounting the chat page
// for explicit cleanup, though React navigation handles this implicitly.

interface CurrentThreadState {
	id: number | null;
	visibility: ChatVisibility | null;
	hasComments: boolean;
	addingCommentToMessageId: number | null;
	/** Whether the right-side comments panel is collapsed (desktop only) */
	commentsCollapsed: boolean;
}

const initialState: CurrentThreadState = {
	id: null,
	visibility: null,
	hasComments: false,
	addingCommentToMessageId: null,
	commentsCollapsed: false,
};

export const currentThreadAtom = atom<CurrentThreadState>(initialState);

export const commentsEnabledAtom = atom(
	(get) => get(currentThreadAtom).visibility === "SEARCH_SPACE"
);

export const showCommentsGutterAtom = atom((get) => {
	const thread = get(currentThreadAtom);
	// Hide gutter if comments are collapsed
	if (thread.commentsCollapsed) return false;
	return (
		thread.visibility === "SEARCH_SPACE" &&
		(thread.hasComments || thread.addingCommentToMessageId !== null)
	);
});

export const addingCommentToMessageIdAtom = atom(
	(get) => get(currentThreadAtom).addingCommentToMessageId,
	(get, set, messageId: number | null) => {
		set(currentThreadAtom, { ...get(currentThreadAtom), addingCommentToMessageId: messageId });
	}
);

// Setter atom for updating thread visibility
export const setThreadVisibilityAtom = atom(null, (get, set, newVisibility: ChatVisibility) => {
	set(currentThreadAtom, { ...get(currentThreadAtom), visibility: newVisibility });
});

export const resetCurrentThreadAtom = atom(null, (_, set) => {
	set(currentThreadAtom, initialState);
});

/** Atom to read whether comments panel is collapsed */
export const commentsCollapsedAtom = atom((get) => get(currentThreadAtom).commentsCollapsed);

/** Atom to toggle the comments collapsed state */
export const toggleCommentsCollapsedAtom = atom(null, (get, set) => {
	const current = get(currentThreadAtom);
	set(currentThreadAtom, { ...current, commentsCollapsed: !current.commentsCollapsed });
});

/** Atom to explicitly set the comments collapsed state */
export const setCommentsCollapsedAtom = atom(null, (get, set, collapsed: boolean) => {
	set(currentThreadAtom, { ...get(currentThreadAtom), commentsCollapsed: collapsed });
});

/** Target comment ID to scroll to (from URL navigation or inbox click) */
export const targetCommentIdAtom = atom<number | null>(null);

/** Setter for target comment ID - also ensures comments are not collapsed */
export const setTargetCommentIdAtom = atom(null, (get, set, commentId: number | null) => {
	// Ensure comments are not collapsed when navigating to a comment
	if (commentId !== null) {
		set(currentThreadAtom, { ...get(currentThreadAtom), commentsCollapsed: false });
	}
	set(targetCommentIdAtom, commentId);
});

/** Clear target after navigation completes */
export const clearTargetCommentIdAtom = atom(null, (_, set) => {
	set(targetCommentIdAtom, null);
});
