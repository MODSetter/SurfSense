import { atom } from "jotai";
import type { ChatVisibility } from "@/lib/chat/thread-persistence";
import { reportPanelAtom } from "./report-panel.atom";

interface CurrentThreadState {
	id: number | null;
	workspaceId: number | null;
	visibility: ChatVisibility | null;
	hasComments: boolean;
}

interface CurrentThreadMetadataPatch {
	id: number | null;
	workspaceId?: number | null;
	visibility?: ChatVisibility | null;
	hasComments?: boolean;
}

interface CurrentThreadMetadataUpdate {
	id: number;
	visibility?: ChatVisibility | null;
	hasComments?: boolean;
}

const initialState: CurrentThreadState = {
	id: null,
	workspaceId: null,
	visibility: null,
	hasComments: false,
};

export const currentThreadAtom = atom<CurrentThreadState>(initialState);

export const commentsEnabledAtom = atom(
	(get) => get(currentThreadAtom).visibility === "SEARCH_SPACE"
);

export const setCurrentThreadMetadataAtom = atom(
	null,
	(get, set, metadata: CurrentThreadMetadataPatch) => {
		const current = get(currentThreadAtom);
		const isSameThread = current.id === metadata.id;

		set(currentThreadAtom, {
			...current,
			id: metadata.id,
			workspaceId:
				"workspaceId" in metadata
					? (metadata.workspaceId ?? null)
					: isSameThread
						? current.workspaceId
						: null,
			visibility:
				"visibility" in metadata
					? (metadata.visibility ?? null)
					: isSameThread
						? current.visibility
						: null,
			hasComments:
				"hasComments" in metadata
					? (metadata.hasComments ?? false)
					: isSameThread
						? current.hasComments
						: false,
		});
	}
);

export const patchCurrentThreadMetadataAtom = atom(
	null,
	(get, set, patch: CurrentThreadMetadataUpdate) => {
		const current = get(currentThreadAtom);
		if (current.id !== patch.id) {
			return;
		}

		set(currentThreadAtom, {
			...current,
			visibility: "visibility" in patch ? (patch.visibility ?? null) : current.visibility,
			hasComments: "hasComments" in patch ? (patch.hasComments ?? false) : current.hasComments,
		});
	}
);

export const resetCurrentThreadAtom = atom(null, (_, set) => {
	set(currentThreadAtom, initialState);
	set(reportPanelAtom, {
		isOpen: false,
		reportId: null,
		title: null,
		wordCount: null,
		shareToken: null,
		contentType: "markdown",
	});
});

/** Target comment ID to scroll to (from URL navigation or inbox click) */
export const targetCommentIdAtom = atom<number | null>(null);

export const setTargetCommentIdAtom = atom(null, (_, set, commentId: number | null) => {
	set(targetCommentIdAtom, commentId);
});

export const clearTargetCommentIdAtom = atom(null, (_, set) => {
	set(targetCommentIdAtom, null);
});
