import type { ThreadMessageLike } from "@assistant-ui/react";
import { createTokenUsageStore } from "@/components/assistant-ui/token-usage-context";
import type { PendingInterruptState } from "@/features/chat-messages/hitl";

/**
 * Durable, per-thread streaming state for a single in-flight chat turn.
 *
 * Lives at module scope (see {@link chatStreamStore}) so a running turn's
 * messages / interrupts survive the chat page unmounting during in-app
 * navigation. The React tree consumes it through ``useChatStream`` via
 * ``useSyncExternalStore`` (state lives outside the render cycle).
 */
export interface ThreadStreamState {
	threadId: number;
	messages: ThreadMessageLike[];
	isRunning: boolean;
	pendingInterrupts: PendingInterruptState[];
}

type Listener = () => void;

/**
 * Module-level singleton external store for chat streaming.
 *
 * Single-active-stream invariant: at most one turn streams at a time,
 * tracked by {@link active}. Per-thread state is still keyed by threadId so
 * the currently-streaming thread and the currently-viewed thread can differ
 * (e.g. a stream finishes while the user is on another chat).
 *
 * ponytail: unbounded ``states`` map is bounded in practice by
 * ``clearInactive`` (called on navigation) + ``clear`` (called after the DB
 * re-hydrates a finished turn). Upgrade path if that ever leaks: LRU cap.
 */
class ChatStreamStore {
	private states = new Map<number, ThreadStreamState>();
	private listeners = new Set<Listener>();

	/** Shared, cross-navigation token-usage store (one instance app-wide). */
	readonly tokenUsage = createTokenUsageStore();

	/** The one in-flight turn's abort handle, or null when idle. */
	private active: { threadId: number; controller: AbortController } | null = null;

	/** Timestamp of the last explicit cancel, for the THREAD_BUSY retry window. */
	recentCancelRequestedAt = 0;

	subscribe = (listener: Listener): (() => void) => {
		this.listeners.add(listener);
		return () => {
			this.listeners.delete(listener);
		};
	};

	private notify(): void {
		for (const l of this.listeners) l();
	}

	/** Snapshot for ``useSyncExternalStore``; stable ref between mutations. */
	getSnapshot = (threadId: number | null): ThreadStreamState | null => {
		if (threadId == null) return null;
		return this.states.get(threadId) ?? null;
	};

	isRunning(threadId: number | null): boolean {
		if (threadId == null) return false;
		return this.states.get(threadId)?.isRunning ?? false;
	}

	getMessages(threadId: number): ThreadMessageLike[] {
		return this.states.get(threadId)?.messages ?? [];
	}

	getPendingInterrupts(threadId: number): PendingInterruptState[] {
		return this.states.get(threadId)?.pendingInterrupts ?? [];
	}

	private ensure(threadId: number): ThreadStreamState {
		let s = this.states.get(threadId);
		if (!s) {
			s = { threadId, messages: [], isRunning: false, pendingInterrupts: [] };
			this.states.set(threadId, s);
		}
		return s;
	}

	private commit(threadId: number, next: ThreadStreamState): void {
		this.states.set(threadId, next);
		this.notify();
	}

	/** Seed a thread's state at the start of a fresh turn (running=true). */
	begin(threadId: number, messages: ThreadMessageLike[]): void {
		this.commit(threadId, { threadId, messages, isRunning: true, pendingInterrupts: [] });
	}

	setMessages(threadId: number, updater: (prev: ThreadMessageLike[]) => ThreadMessageLike[]): void {
		const prev = this.ensure(threadId);
		const messages = updater(prev.messages);
		if (messages === prev.messages) return;
		this.commit(threadId, { ...prev, messages });
	}

	setRunning(threadId: number, running: boolean): void {
		const prev = this.ensure(threadId);
		if (prev.isRunning === running) return;
		this.commit(threadId, { ...prev, isRunning: running });
	}

	setPendingInterrupts(
		threadId: number,
		updater: (prev: PendingInterruptState[]) => PendingInterruptState[]
	): void {
		const prev = this.ensure(threadId);
		const pendingInterrupts = updater(prev.pendingInterrupts);
		if (pendingInterrupts === prev.pendingInterrupts) return;
		this.commit(threadId, { ...prev, pendingInterrupts });
	}

	/**
	 * A thread whose overlay must survive DB re-hydration / navigation: it is
	 * either streaming or paused awaiting a HITL decision (the pending
	 * interrupts + interrupt cards live only in the overlay).
	 */
	private isPinned(s: ThreadStreamState): boolean {
		return s.isRunning || s.pendingInterrupts.length > 0;
	}

	/** Drop a thread's overlay once the DB is authoritative. No-op while pinned. */
	clear(threadId: number): void {
		const s = this.states.get(threadId);
		if (!s || this.isPinned(s)) return;
		this.states.delete(threadId);
		this.notify();
	}

	/** Evict every non-pinned thread except ``exceptThreadId`` (memory bound). */
	clearInactive(exceptThreadId: number | null): void {
		let changed = false;
		for (const [id, s] of this.states) {
			if (id === exceptThreadId || this.isPinned(s)) continue;
			this.states.delete(id);
			changed = true;
		}
		if (changed) this.notify();
	}

	// ---- active-stream lifecycle -------------------------------------------

	/** Register a new in-flight turn, aborting any previous one first. */
	beginActive(threadId: number, controller: AbortController): void {
		this.abortActive();
		this.active = { threadId, controller };
	}

	get activeThreadId(): number | null {
		return this.active?.threadId ?? null;
	}

	/** Clear the active handle iff it still points at ``controller``. */
	clearActive(controller: AbortController): void {
		if (this.active?.controller === controller) this.active = null;
	}

	/** Abort the in-flight turn's fetch (client disconnect, not a server stop). */
	abortActive(): void {
		if (this.active) {
			this.active.controller.abort();
			this.active = null;
		}
	}

	markRecentCancel(): void {
		this.recentCancelRequestedAt = Date.now();
	}
}

export const chatStreamStore = new ChatStreamStore();
