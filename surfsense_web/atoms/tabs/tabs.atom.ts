import { atom } from "jotai";
import { atomWithStorage, createJSONStorage } from "jotai/utils";

export type TabType = "chat" | "document";

export interface Tab {
	id: string;
	type: TabType;
	entityId: number | null;
	workspaceId: number;
}

interface TabsState {
	tabs: Tab[];
	activeTabId: string | null;
}

const INITIAL_CHAT_TAB: Tab = {
	id: "chat-new",
	type: "chat",
	entityId: null,
	workspaceId: 0,
};

const initialState: TabsState = {
	tabs: [INITIAL_CHAT_TAB],
	activeTabId: "chat-new",
};

// Persist tabs in localStorage so they survive a hard refresh and let the user
// keep tabs open across multiple workspaces (browser-like behavior).
const localStorageAdapter = createJSONStorage<TabsState>(
	() => (typeof window !== "undefined" ? localStorage : undefined) as Storage
);

export const tabsStateAtom = atomWithStorage<TabsState>(
	"surfsense:tabs:v2",
	initialState,
	localStorageAdapter,
	{ getOnInit: true }
);

export const tabsAtom = atom((get) => get(tabsStateAtom).tabs);
export const activeTabIdAtom = atom((get) => get(tabsStateAtom).activeTabId);
export const activeTabAtom = atom((get) => {
	const state = get(tabsStateAtom);
	return state.tabs.find((t) => t.id === state.activeTabId) ?? null;
});

export function makeChatTabId(chatId: number | null): string {
	return chatId ? `chat-${chatId}` : "chat-new";
}

export function makeDocumentTabId(documentId: number): string {
	return `doc-${documentId}`;
}

/**
 * Sync the current chat from Next.js routing into the tab bar.
 * If a tab for this chat already exists, activate it.
 * Otherwise, replace the "new chat" tab or create one.
 */
export const syncChatTabAtom = atom(
	null,
	(
		get,
		set,
		{
			chatId,
			workspaceId,
		}: {
			chatId: number | null;
			workspaceId: number;
		}
	) => {
		const state = get(tabsStateAtom);
		const tabId = makeChatTabId(chatId);
		const existing = state.tabs.find((t) => t.id === tabId);

		if (existing) {
			set(tabsStateAtom, {
				...state,
				activeTabId: tabId,
				tabs: state.tabs.map((t) =>
					t.id === tabId
						? {
								...t,
								entityId: chatId,
								workspaceId,
							}
						: t
				),
			});
			return;
		}

		// If navigating to a new chat (no chatId), ensure there's a "new chat" tab
		// scoped to the current workspace.
		if (!chatId) {
			const hasNewChatTab = state.tabs.some((t) => t.id === "chat-new");
			if (hasNewChatTab) {
				set(tabsStateAtom, {
					...state,
					activeTabId: "chat-new",
					tabs: state.tabs.map((t) =>
						t.id === "chat-new" ? { ...t, entityId: null, workspaceId } : t
					),
				});
			} else {
				set(tabsStateAtom, {
					tabs: [...state.tabs, { ...INITIAL_CHAT_TAB, workspaceId }],
					activeTabId: "chat-new",
				});
			}
			return;
		}

		// Replace the "new chat" tab if it exists and is empty, otherwise add new tab
		const newChatTabIdx = state.tabs.findIndex((t) => t.id === "chat-new");
		const newTab: Tab = {
			id: tabId,
			type: "chat",
			entityId: chatId,
			workspaceId,
		};

		let updatedTabs: Tab[];
		if (newChatTabIdx !== -1) {
			updatedTabs = [...state.tabs];
			updatedTabs[newChatTabIdx] = newTab;
		} else {
			updatedTabs = [...state.tabs, newTab];
		}

		set(tabsStateAtom, { tabs: updatedTabs, activeTabId: tabId });
	}
);

/** Promote the lazy "new chat" tab once the server creates its thread. */
export const updateChatTabTitleAtom = atom(
	null,
	(get, set, { chatId }: { chatId: number; title?: string }) => {
		const state = get(tabsStateAtom);
		const tabId = makeChatTabId(chatId);
		const hasExactTab = state.tabs.some((t) => t.id === tabId);

		// During lazy thread creation, title updates can arrive before "chat-new" is
		// swapped to chat-{id}. In that case, promote the pointer only; title comes
		// from Zero.
		if (!hasExactTab && state.activeTabId === "chat-new") {
			set(tabsStateAtom, {
				...state,
				activeTabId: tabId,
				tabs: state.tabs.map((t) =>
					t.id === "chat-new" ? { ...t, id: tabId, entityId: chatId } : t
				),
			});
		}
	}
);

/** Open a document tab. If already open, just switch to it. */
export const openDocumentTabAtom = atom(
	null,
	(
		get,
		set,
		{ documentId, workspaceId }: { documentId: number; workspaceId: number; title?: string }
	) => {
		const state = get(tabsStateAtom);
		const tabId = makeDocumentTabId(documentId);
		const existing = state.tabs.find((t) => t.id === tabId);

		if (existing) {
			set(tabsStateAtom, {
				...state,
				activeTabId: tabId,
				tabs: state.tabs.map((t) => (t.id === tabId ? { ...t, workspaceId } : t)),
			});
			return;
		}

		const newTab: Tab = {
			id: tabId,
			type: "document",
			entityId: documentId,
			workspaceId,
		};

		set(tabsStateAtom, {
			tabs: [...state.tabs, newTab],
			activeTabId: tabId,
		});
	}
);

/** Switch to a tab by ID. Returns the tab so the caller can navigate if needed. */
export const switchTabAtom = atom(null, (get, set, tabId: string) => {
	const state = get(tabsStateAtom);
	const tab = state.tabs.find((t) => t.id === tabId);
	if (tab) {
		set(tabsStateAtom, { ...state, activeTabId: tabId });
	}
	return tab ?? null;
});

/** Close a tab. If it was active, activate the nearest sibling. */
export const closeTabAtom = atom(null, (get, set, tabId: string) => {
	const state = get(tabsStateAtom);
	const idx = state.tabs.findIndex((t) => t.id === tabId);
	if (idx === -1) return null;

	const remaining = state.tabs.filter((t) => t.id !== tabId);

	// Don't close the last tab — always keep at least one
	if (remaining.length === 0) {
		const closedTab = state.tabs[idx];
		set(tabsStateAtom, {
			tabs: [{ ...INITIAL_CHAT_TAB, workspaceId: closedTab.workspaceId }],
			activeTabId: "chat-new",
		});
		return { ...INITIAL_CHAT_TAB, workspaceId: closedTab.workspaceId };
	}

	let newActiveId = state.activeTabId;
	if (state.activeTabId === tabId) {
		// Activate the tab to the left (or right if first)
		const newIdx = Math.min(idx, remaining.length - 1);
		newActiveId = remaining[newIdx].id;
	}

	set(tabsStateAtom, { tabs: remaining, activeTabId: newActiveId });
	return remaining.find((t) => t.id === newActiveId) ?? null;
});

/** Remove a chat tab by chat ID (used when a chat is deleted). */
export const removeChatTabAtom = atom(null, (get, set, chatId: number) => {
	const state = get(tabsStateAtom);
	const tabId = makeChatTabId(chatId);
	const idx = state.tabs.findIndex((t) => t.id === tabId);
	if (idx === -1) return null;

	const remaining = state.tabs.filter((t) => t.id !== tabId);

	// Always keep at least one tab available.
	if (remaining.length === 0) {
		const removedTab = state.tabs[idx];
		set(tabsStateAtom, {
			tabs: [{ ...INITIAL_CHAT_TAB, workspaceId: removedTab.workspaceId }],
			activeTabId: "chat-new",
		});
		return { ...INITIAL_CHAT_TAB, workspaceId: removedTab.workspaceId };
	}

	let newActiveId = state.activeTabId;
	if (state.activeTabId === tabId) {
		const newIdx = Math.min(idx, remaining.length - 1);
		newActiveId = remaining[newIdx].id;
	}

	set(tabsStateAtom, { tabs: remaining, activeTabId: newActiveId });
	return remaining.find((t) => t.id === newActiveId) ?? null;
});

/** Remove unresolved chat pointers after Zero confirms the queried rows are complete. */
export const pruneMissingChatTabsAtom = atom(null, (get, set, missingChatIds: Set<number>) => {
	if (missingChatIds.size === 0) return;

	const state = get(tabsStateAtom);
	const firstMissingIdx = state.tabs.findIndex(
		(t) => t.type === "chat" && t.entityId !== null && missingChatIds.has(t.entityId)
	);
	if (firstMissingIdx === -1) return;

	const remaining = state.tabs.filter(
		(t) => !(t.type === "chat" && t.entityId !== null && missingChatIds.has(t.entityId))
	);

	if (remaining.length === 0) {
		set(tabsStateAtom, {
			tabs: [INITIAL_CHAT_TAB],
			activeTabId: "chat-new",
		});
		return;
	}

	const activeWasPruned = state.tabs.some(
		(t) => t.id === state.activeTabId && t.type === "chat" && t.entityId !== null && missingChatIds.has(t.entityId)
	);
	const newActiveId = activeWasPruned
		? remaining[Math.min(firstMissingIdx, remaining.length - 1)].id
		: state.activeTabId;

	set(tabsStateAtom, { tabs: remaining, activeTabId: newActiveId });
});
