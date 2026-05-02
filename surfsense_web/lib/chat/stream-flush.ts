import { FrameBatchedUpdater } from "@/lib/chat/streaming-state";

export function createStreamFlushHelpers(flushMessages: () => void): {
	batcher: FrameBatchedUpdater;
	scheduleFlush: () => void;
	forceFlush: () => void;
} {
	const batcher = new FrameBatchedUpdater();
	const scheduleFlush = () => batcher.schedule(flushMessages);
	// Force-flush helper: ``batcher.flush()`` is a no-op when
	// ``dirty=false`` (e.g. a tool starts before any text streamed).
	// ``scheduleFlush(); batcher.flush()`` sets the dirty bit first so
	// terminal events render promptly without the throttle delay.
	const forceFlush = () => {
		scheduleFlush();
		batcher.flush();
	};
	return { batcher, scheduleFlush, forceFlush };
}
