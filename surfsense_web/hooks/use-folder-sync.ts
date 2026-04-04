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
const MAX_WAIT_MS = 10_000;
const MAX_BATCH_SIZE = 50;

interface BatchItem {
	folderPath: string;
	folderName: string;
	searchSpaceId: number;
	rootFolderId: number | null;
	filePaths: string[];
	ackIds: string[];
}

export function useFolderSync() {
	const queueRef = useRef<BatchItem[]>([]);
	const processingRef = useRef(false);
	const debounceTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
	const pendingByFolder = useRef<Map<string, BatchItem>>(new Map());
	const firstEventTime = useRef<Map<string, number>>(new Map());
	const isMountedRef = useRef(false);

	async function processQueue() {
		if (processingRef.current) return;
		processingRef.current = true;
		while (queueRef.current.length > 0) {
			const batch = queueRef.current.shift()!;
			try {
				await documentsApiService.folderIndexFiles(batch.searchSpaceId, {
					folder_path: batch.folderPath,
					folder_name: batch.folderName,
					search_space_id: batch.searchSpaceId,
					target_file_paths: batch.filePaths,
					root_folder_id: batch.rootFolderId,
				});
				const api = typeof window !== "undefined" ? window.electronAPI : null;
				if (api?.acknowledgeFileEvents && batch.ackIds.length > 0) {
					await api.acknowledgeFileEvents(batch.ackIds);
				}
			} catch (err) {
				console.error("[FolderSync] Failed to trigger batch re-index:", err);
			}
		}
		processingRef.current = false;
	}

	function flushFolder(folderKey: string) {
		debounceTimers.current.delete(folderKey);
		firstEventTime.current.delete(folderKey);
		const pending = pendingByFolder.current.get(folderKey);
		if (!pending) return;
		pendingByFolder.current.delete(folderKey);

		for (let i = 0; i < pending.filePaths.length; i += MAX_BATCH_SIZE) {
			queueRef.current.push({
				...pending,
				filePaths: pending.filePaths.slice(i, i + MAX_BATCH_SIZE),
				ackIds: i === 0 ? pending.ackIds : [],
			});
		}
		processQueue();
	}

	function enqueueWithDebounce(event: FileChangedEvent) {
		const folderKey = event.folderPath;
		const existing = pendingByFolder.current.get(folderKey);

		if (existing) {
			const pathSet = new Set(existing.filePaths);
			pathSet.add(event.fullPath);
			existing.filePaths = Array.from(pathSet);
			if (!existing.ackIds.includes(event.id)) {
				existing.ackIds.push(event.id);
			}
		} else {
			pendingByFolder.current.set(folderKey, {
				folderPath: event.folderPath,
				folderName: event.folderName,
				searchSpaceId: event.searchSpaceId,
				rootFolderId: event.rootFolderId,
				filePaths: [event.fullPath],
				ackIds: [event.id],
			});
			firstEventTime.current.set(folderKey, Date.now());
		}

		const elapsed = Date.now() - (firstEventTime.current.get(folderKey) ?? Date.now());
		if (elapsed >= MAX_WAIT_MS) {
			const existingTimeout = debounceTimers.current.get(folderKey);
			if (existingTimeout) clearTimeout(existingTimeout);
			flushFolder(folderKey);
			return;
		}

		const existingTimeout = debounceTimers.current.get(folderKey);
		if (existingTimeout) clearTimeout(existingTimeout);

		const timeout = setTimeout(() => flushFolder(folderKey), DEBOUNCE_MS);
		debounceTimers.current.set(folderKey, timeout);
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
			pendingByFolder.current.clear();
			firstEventTime.current.clear();
		};
	}, []);
}
