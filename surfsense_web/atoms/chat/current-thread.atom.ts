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
}

const initialState: CurrentThreadState = {
	id: null,
	visibility: null,
	hasComments: false,
	addingCommentToMessageId: null,
};

export const currentThreadAtom = atom<CurrentThreadState>(initialState);

export const commentsEnabledAtom = atom(
	(get) => get(currentThreadAtom).visibility === "SEARCH_SPACE"
);

export const showCommentsGutterAtom = atom((get) => {
	const thread = get(currentThreadAtom);
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
