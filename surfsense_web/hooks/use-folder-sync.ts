"use client";

import { useEffect, useRef } from "react";
import { documentsApiService } from "@/lib/apis/documents-api.service";

interface FileChangedEvent {
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

export function useFolderSync() {
	const queueRef = useRef<FileChangedEvent[]>([]);
	const processingRef = useRef(false);
	const debounceTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

	async function processQueue() {
		if (processingRef.current) return;
		processingRef.current = true;
		while (queueRef.current.length > 0) {
			const event = queueRef.current.shift()!;
			try {
				await documentsApiService.folderIndexFile(event.searchSpaceId, {
					folder_path: event.folderPath,
					folder_name: event.folderName,
					search_space_id: event.searchSpaceId,
					target_file_path: event.fullPath,
					root_folder_id: event.rootFolderId,
				});
			} catch (err) {
				console.error("[FolderSync] Failed to trigger re-index:", err);
			}
		}
		processingRef.current = false;
	}

	useEffect(() => {
		const api = typeof window !== "undefined" ? window.electronAPI : null;
		if (!api?.onFileChanged) return;

		// Signal to main process that the renderer is ready to receive events
		api.signalRendererReady?.();

		const cleanup = api.onFileChanged((event: FileChangedEvent) => {
			const key = `${event.folderPath}:${event.fullPath}`;

			const existing = debounceTimers.current.get(key);
			if (existing) clearTimeout(existing);

			const timeout = setTimeout(() => {
				debounceTimers.current.delete(key);
				queueRef.current.push(event);
				processQueue();
			}, DEBOUNCE_MS);

			debounceTimers.current.set(key, timeout);
		});

		return () => {
			cleanup();
			for (const timeout of debounceTimers.current.values()) {
				clearTimeout(timeout);
			}
			debounceTimers.current.clear();
		};
	}, []);
}
