"use client";

import { useEffect, useRef } from "react";
import { documentsApiService } from "@/lib/apis/documents-api.service";

interface FileChangedEvent {
	id: string;
	rootFolderId: number | null;
	searchSpaceId: number;
	folderPath: string;
	folderName: string;
	relativePath: string;
	fullPath: string;
	action: string;
	timestamp: number;
}

const DEBOUNCE_MS = 2000;
interface QueueItem {
	event: FileChangedEvent;
	ackIds: string[];
}

export function useFolderSync() {
	const queueRef = useRef<QueueItem[]>([]);
	const processingRef = useRef(false);
	const debounceTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
	const pendingByKey = useRef<Map<string, QueueItem>>(new Map());
	const isMountedRef = useRef(false);

	async function processQueue() {
		if (processingRef.current) return;
		processingRef.current = true;
		while (queueRef.current.length > 0) {
			const item = queueRef.current.shift()!;
			try {
				await documentsApiService.folderIndexFile(item.event.searchSpaceId, {
					folder_path: item.event.folderPath,
					folder_name: item.event.folderName,
					search_space_id: item.event.searchSpaceId,
					target_file_path: item.event.fullPath,
					root_folder_id: item.event.rootFolderId,
				});
				const api = typeof window !== "undefined" ? window.electronAPI : null;
				if (api?.acknowledgeFileEvents && item.ackIds.length > 0) {
					await api.acknowledgeFileEvents(item.ackIds);
				}
			} catch (err) {
				console.error("[FolderSync] Failed to trigger re-index:", err);
			}
		}
		processingRef.current = false;
	}

	function enqueueWithDebounce(event: FileChangedEvent) {
		const key = `${event.folderPath}:${event.relativePath}`;
		const existing = pendingByKey.current.get(key);
		const ackSet = new Set(existing?.ackIds ?? []);
		ackSet.add(event.id);
		pendingByKey.current.set(key, {
			event,
			ackIds: Array.from(ackSet),
		});

		const existingTimeout = debounceTimers.current.get(key);
		if (existingTimeout) clearTimeout(existingTimeout);

		const timeout = setTimeout(() => {
			debounceTimers.current.delete(key);
			const pending = pendingByKey.current.get(key);
			if (!pending) return;
			pendingByKey.current.delete(key);
			queueRef.current.push(pending);
			processQueue();
		}, DEBOUNCE_MS);

		debounceTimers.current.set(key, timeout);
	}

	useEffect(() => {
		isMountedRef.current = true;
		const api = typeof window !== "undefined" ? window.electronAPI : null;
		if (!api?.onFileChanged) {
			return () => {
				isMountedRef.current = false;
			};
		}

		// Signal to main process that the renderer is ready to receive events
		api.signalRendererReady?.();

		// Drain durable outbox first so events survive renderer startup gaps and restarts
		void api.getPendingFileEvents?.().then((pendingEvents) => {
			if (!isMountedRef.current || !pendingEvents?.length) return;
			for (const event of pendingEvents) {
				enqueueWithDebounce(event);
			}
		});

		const cleanup = api.onFileChanged((event: FileChangedEvent) => {
			enqueueWithDebounce(event);
		});

		return () => {
			isMountedRef.current = false;
			cleanup();
			for (const timeout of debounceTimers.current.values()) {
				clearTimeout(timeout);
			}
			debounceTimers.current.clear();
			pendingByKey.current.clear();
		};
	}, []);
}
