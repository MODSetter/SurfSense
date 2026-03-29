import { atom } from "jotai";
import { atomWithStorage, createJSONStorage } from "jotai/utils";

export type TabType = "chat" | "document";

export interface Tab {
	id: string;
	type: TabType;
	title: string;
	/** For chat tabs */
	chatId?: number | null;
	chatUrl?: string;
	/** For document tabs */
	documentId?: number;
	searchSpaceId?: number;
}

interface TabsState {
	tabs: Tab[];
	activeTabId: string | null;
}

const INITIAL_CHAT_TAB: Tab = {
	id: "chat-new",
	type: "chat",
	title: "New Chat",
	chatId: null,
	chatUrl: undefined,
};

const initialState: TabsState = {
	tabs: [INITIAL_CHAT_TAB],
	activeTabId: "chat-new",
};

// Prevent race conditions where route-sync recreates a just-deleted chat tab.
const deletedChatIdsAtom = atom<Set<number>>(new Set<number>());

const sessionStorageAdapter = createJSONStorage<TabsState>(
	() => (typeof window !== "undefined" ? sessionStorage : undefined) as Storage
);

export const tabsStateAtom = atomWithStorage<TabsState>(
	"surfsense:tabs",
	initialState,
	sessionStorageAdapter,
	{ getOnInit: true }
);

export const tabsAtom = atom((get) => get(tabsStateAtom).tabs);
export const activeTabIdAtom = atom((get) => get(tabsStateAtom).activeTabId);
export const activeTabAtom = atom((get) => {
	const state = get(tabsStateAtom);
	return state.tabs.find((t) => t.id === state.activeTabId) ?? null;
});

function makeChatTabId(chatId: number | null): string {
	return chatId ? `chat-${chatId}` : "chat-new";
}

function makeDocumentTabId(documentId: number): string {
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
		{ chatId, title, chatUrl }: { chatId: number | null; title?: string; chatUrl?: string }
	) => {
		if (chatId && get(deletedChatIdsAtom).has(chatId)) {
			return;
		}

		const state = get(tabsStateAtom);
		const tabId = makeChatTabId(chatId);
		const existing = state.tabs.find((t) => t.id === tabId);

		if (existing) {
			set(tabsStateAtom, {
				...state,
				activeTabId: tabId,
				tabs: state.tabs.map((t) =>
					t.id === tabId ? { ...t, title: title || t.title, chatUrl: chatUrl || t.chatUrl } : t
				),
			});
			return;
		}

		// If navigating to a new chat (no chatId), ensure there's a "new chat" tab
		if (!chatId) {
			const hasNewChatTab = state.tabs.some((t) => t.id === "chat-new");
			if (hasNewChatTab) {
				set(tabsStateAtom, { ...state, activeTabId: "chat-new" });
			} else {
				set(tabsStateAtom, {
					tabs: [...state.tabs, INITIAL_CHAT_TAB],
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
			title: title || `Chat ${chatId}`,
			chatId,
			chatUrl,
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

/** Update the title of the current chat tab (e.g., when a chat gets its first response). */
export const updateChatTabTitleAtom = atom(
	null,
	(get, set, { chatId, title }: { chatId: number; title: string }) => {
		const state = get(tabsStateAtom);
		const tabId = makeChatTabId(chatId);
		const hasExactTab = state.tabs.some((t) => t.id === tabId);

		// During lazy thread creation, title updates can arrive before "chat-new"
		// is swapped to chat-{id}. In that case, promote the active "chat-new" tab.
		if (!hasExactTab && state.activeTabId === "chat-new") {
			set(tabsStateAtom, {
				...state,
				activeTabId: tabId,
				tabs: state.tabs.map((t) => (t.id === "chat-new" ? { ...t, id: tabId, chatId, title } : t)),
			});
			return;
		}

		set(tabsStateAtom, {
			...state,
			tabs: state.tabs.map((t) => (t.id === tabId ? { ...t, title } : t)),
		});
	}
);

/** Open a document tab. If already open, just switch to it. */
export const openDocumentTabAtom = atom(
	null,
	(
		get,
		set,
		{
			documentId,
			searchSpaceId,
			title,
		}: { documentId: number; searchSpaceId: number; title?: string }
	) => {
		const state = get(tabsStateAtom);
		const tabId = makeDocumentTabId(documentId);
		const existing = state.tabs.find((t) => t.id === tabId);

		if (existing) {
			set(tabsStateAtom, {
				...state,
				activeTabId: tabId,
				tabs: state.tabs.map((t) => (t.id === tabId ? { ...t, title: title || t.title } : t)),
			});
			return;
		}

		const newTab: Tab = {
			id: tabId,
			type: "document",
			title: title || `Document ${documentId}`,
			documentId,
			searchSpaceId,
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
		set(tabsStateAtom, {
			tabs: [INITIAL_CHAT_TAB],
			activeTabId: "chat-new",
		});
		return INITIAL_CHAT_TAB;
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

	const deletedChatIds = get(deletedChatIdsAtom);
	set(deletedChatIdsAtom, new Set([...deletedChatIds, chatId]));

	const remaining = state.tabs.filter((t) => t.id !== tabId);

	// Always keep at least one tab available.
	if (remaining.length === 0) {
		set(tabsStateAtom, {
			tabs: [INITIAL_CHAT_TAB],
			activeTabId: "chat-new",
		});
		return INITIAL_CHAT_TAB;
	}

	let newActiveId = state.activeTabId;
	if (state.activeTabId === tabId) {
		const newIdx = Math.min(idx, remaining.length - 1);
		newActiveId = remaining[newIdx].id;
	}

	set(tabsStateAtom, { tabs: remaining, activeTabId: newActiveId });
	return remaining.find((t) => t.id === newActiveId) ?? null;
});

/** Reset tabs when switching search spaces. */
export const resetTabsAtom = atom(null, (_get, set) => {
	set(tabsStateAtom, { ...initialState });
	set(deletedChatIdsAtom, new Set<number>());
});
