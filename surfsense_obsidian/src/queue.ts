import type { QueueItem } from "./types";

/**
 * Persistent upload queue.
 *
 * Mobile-safety contract:
 *   - Persistence is delegated to a save callback (which the plugin wires
 *     to `plugin.saveData()`); never `node:fs`. Items also live in the
 *     plugin's settings JSON so a crash mid-flight loses nothing.
 *   - No top-level `node:*` imports.
 *
 * Behavioural contract:
 *   - Per-file debounce: enqueueing the same path coalesces, the latest
 *     `enqueuedAt` wins so we don't ship a stale snapshot.
 *   - `delete` for a path drops any pending `upsert` for that path
 *     (otherwise we'd resurrect a note the user just deleted).
 *   - `rename` is a first-class op so the backend can update
 *     `unique_identifier_hash` instead of "delete + create" (which would
 *     blow away document versions, citations, and the document_id used
 *     in chat history).
 *   - Drain takes a worker, returns once the worker either succeeds for
 *     every batch or hits a stop signal (transient error, mid-drain
 *     stop request).
 */

export interface QueueWorker {
	processBatch(batch: QueueItem[]): Promise<BatchResult>;
}

export interface BatchResult {
	/** Items that succeeded; they will be ack'd off the queue. */
	acked: QueueItem[];
	/** Items that should be retried; their `attempt` is bumped. */
	retry: QueueItem[];
	/** Items that failed permanently (4xx). They get dropped. */
	dropped: QueueItem[];
	/** If true, the drain loop stops (e.g. transient/network error). */
	stop: boolean;
	/** Optional retry-after for transient errors (ms). */
	backoffMs?: number;
}

export interface PersistentQueueOptions {
	debounceMs?: number;
	batchSize?: number;
	maxAttempts?: number;
	persist: (items: QueueItem[]) => Promise<void> | void;
	now?: () => number;
}

const DEFAULTS = {
	debounceMs: 2000,
	batchSize: 15,
	maxAttempts: 8,
};

export class PersistentQueue {
	private items: QueueItem[];
	private readonly opts: Required<
		Omit<PersistentQueueOptions, "persist" | "now">
	> & {
		persist: PersistentQueueOptions["persist"];
		now: () => number;
	};
	private draining = false;
	private stopRequested = false;
	private flushTimer: ReturnType<typeof setTimeout> | null = null;
	private onFlush: (() => void) | null = null;

	constructor(initial: QueueItem[], opts: PersistentQueueOptions) {
		this.items = [...initial];
		this.opts = {
			debounceMs: opts.debounceMs ?? DEFAULTS.debounceMs,
			batchSize: opts.batchSize ?? DEFAULTS.batchSize,
			maxAttempts: opts.maxAttempts ?? DEFAULTS.maxAttempts,
			persist: opts.persist,
			now: opts.now ?? (() => Date.now()),
		};
	}

	get size(): number {
		return this.items.length;
	}

	snapshot(): QueueItem[] {
		return this.items.map((i) => ({ ...i }));
	}

	setFlushHandler(handler: () => void): void {
		this.onFlush = handler;
	}

	enqueueUpsert(path: string): void {
		const now = this.opts.now();
		this.items = this.items.filter(
			(i) => !(i.op === "upsert" && i.path === path),
		);
		this.items.push({ op: "upsert", path, enqueuedAt: now, attempt: 0 });
		void this.persist();
		this.scheduleFlush();
	}

	enqueueDelete(path: string): void {
		const now = this.opts.now();
		// A delete supersedes any pending upsert for the same path.
		this.items = this.items.filter(
			(i) =>
				!(
					(i.op === "upsert" && i.path === path) ||
					(i.op === "delete" && i.path === path)
				),
		);
		this.items.push({ op: "delete", path, enqueuedAt: now, attempt: 0 });
		void this.persist();
		this.scheduleFlush();
	}

	enqueueRename(oldPath: string, newPath: string): void {
		const now = this.opts.now();
		this.items = this.items.filter(
			(i) =>
				!(
					(i.op === "upsert" && (i.path === oldPath || i.path === newPath)) ||
					(i.op === "rename" && i.oldPath === oldPath && i.newPath === newPath)
				),
		);
		this.items.push({
			op: "rename",
			oldPath,
			newPath,
			enqueuedAt: now,
			attempt: 0,
		});
		// Also enqueue an upsert of the new path so its content/metadata
		// reflects whatever the editor flushed alongside the rename.
		this.items.push({ op: "upsert", path: newPath, enqueuedAt: now, attempt: 0 });
		void this.persist();
		this.scheduleFlush();
	}

	requestStop(): void {
		this.stopRequested = true;
	}

	cancelFlush(): void {
		if (this.flushTimer !== null) {
			clearTimeout(this.flushTimer);
			this.flushTimer = null;
		}
	}

	private scheduleFlush(): void {
		if (!this.onFlush) return;
		if (this.flushTimer !== null) clearTimeout(this.flushTimer);
		this.flushTimer = setTimeout(() => {
			this.flushTimer = null;
			this.onFlush?.();
		}, this.opts.debounceMs);
	}

	async drain(worker: QueueWorker): Promise<DrainSummary> {
		if (this.draining) return { batches: 0, acked: 0, dropped: 0, stopped: false };
		this.draining = true;
		this.stopRequested = false;
		const summary: DrainSummary = {
			batches: 0,
			acked: 0,
			dropped: 0,
			stopped: false,
		};
		try {
			while (this.items.length > 0 && !this.stopRequested) {
				const batch = this.takeBatch();
				summary.batches += 1;

				const result = await worker.processBatch(batch);
				summary.acked += result.acked.length;
				summary.dropped += result.dropped.length;

				const ackKeys = new Set(result.acked.map(itemKey));
				const dropKeys = new Set(result.dropped.map(itemKey));
				const retryKeys = new Set(result.retry.map(itemKey));

				// Keep any item we didn't explicitly account for in `retry`
				// so a partial-batch drop never silently loses work.
				const unhandled = batch.filter(
					(b) =>
						!ackKeys.has(itemKey(b)) &&
						!dropKeys.has(itemKey(b)) &&
						!retryKeys.has(itemKey(b)),
				);
				const retry = [...result.retry, ...unhandled].map((i) => ({
					...i,
					attempt: i.attempt + 1,
				}));
				const survivors = retry.filter((i) => i.attempt <= this.opts.maxAttempts);
				summary.dropped += retry.length - survivors.length;

				this.items = [...survivors, ...this.items];
				await this.persist();

				if (result.stop) {
					summary.stopped = true;
					if (result.backoffMs) summary.backoffMs = result.backoffMs;
					break;
				}
			}
			if (this.stopRequested) summary.stopped = true;
			return summary;
		} finally {
			this.draining = false;
		}
	}

	private takeBatch(): QueueItem[] {
		const head = this.items.slice(0, this.opts.batchSize);
		this.items = this.items.slice(this.opts.batchSize);
		return head;
	}

	private async persist(): Promise<void> {
		await this.opts.persist(this.snapshot());
	}
}

export interface DrainSummary {
	batches: number;
	acked: number;
	dropped: number;
	stopped: boolean;
	backoffMs?: number;
}

export function itemKey(i: QueueItem): string {
	if (i.op === "rename") return `rename:${i.oldPath}=>${i.newPath}`;
	return `${i.op}:${i.path}`;
}
