"use client";

import { useEffect, useRef } from "react";
import { useElectronAPI } from "@/hooks/use-platform";
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

interface FileEntry {
	fullPath: string;
	relativePath: string;
	action: string;
}

interface BatchItem {
	folderPath: string;
	folderName: string;
	searchSpaceId: number;
	rootFolderId: number | null;
	files: FileEntry[];
	ackIds: string[];
}

export function useFolderSync() {
	const electronAPI = useElectronAPI();
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
				const addChangeFiles = batch.files.filter(
					(f) => f.action === "add" || f.action === "change"
				);
				const unlinkFiles = batch.files.filter((f) => f.action === "unlink");

				if (addChangeFiles.length > 0 && electronAPI?.readLocalFiles) {
					const fullPaths = addChangeFiles.map((f) => f.fullPath);
					const fileDataArr = await electronAPI.readLocalFiles(fullPaths);

					const files: File[] = fileDataArr.map((fd) => {
						const blob = new Blob([fd.data], { type: fd.mimeType || "application/octet-stream" });
						return new File([blob], fd.name, { type: blob.type });
					});

					await documentsApiService.folderUploadFiles(files, {
						folder_name: batch.folderName,
						search_space_id: batch.searchSpaceId,
						relative_paths: addChangeFiles.map((f) => f.relativePath),
						root_folder_id: batch.rootFolderId,
					});
				}

				if (unlinkFiles.length > 0) {
					await documentsApiService.folderNotifyUnlinked({
						folder_name: batch.folderName,
						search_space_id: batch.searchSpaceId,
						root_folder_id: batch.rootFolderId,
						relative_paths: unlinkFiles.map((f) => f.relativePath),
					});
				}

				if (electronAPI?.acknowledgeFileEvents && batch.ackIds.length > 0) {
					await electronAPI.acknowledgeFileEvents(batch.ackIds);
				}
			} catch (err) {
				console.error("[FolderSync] Failed to process batch:", err);
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

		for (let i = 0; i < pending.files.length; i += MAX_BATCH_SIZE) {
			queueRef.current.push({
				...pending,
				files: pending.files.slice(i, i + MAX_BATCH_SIZE),
				ackIds: i === 0 ? pending.ackIds : [],
			});
		}
		processQueue();
	}

	function enqueueWithDebounce(event: FileChangedEvent) {
		const folderKey = event.folderPath;
		const existing = pendingByFolder.current.get(folderKey);

		if (existing) {
			const pathSet = new Set(existing.files.map((f) => f.fullPath));
			if (!pathSet.has(event.fullPath)) {
				existing.files.push({
					fullPath: event.fullPath,
					relativePath: event.relativePath,
					action: event.action,
				});
			}
			if (!existing.ackIds.includes(event.id)) {
				existing.ackIds.push(event.id);
			}
		} else {
			pendingByFolder.current.set(folderKey, {
				folderPath: event.folderPath,
				folderName: event.folderName,
				searchSpaceId: event.searchSpaceId,
				rootFolderId: event.rootFolderId,
				files: [
					{
						fullPath: event.fullPath,
						relativePath: event.relativePath,
						action: event.action,
					},
				],
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
		if (!electronAPI?.onFileChanged) {
			return () => {
				isMountedRef.current = false;
			};
		}

		electronAPI.signalRendererReady?.();

		void electronAPI.getPendingFileEvents?.().then((pendingEvents) => {
			if (!isMountedRef.current || !pendingEvents?.length) return;
			for (const event of pendingEvents) {
				enqueueWithDebounce(event);
			}
		});

		const cleanup = electronAPI.onFileChanged((event: FileChangedEvent) => {
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
	}, [electronAPI]);
}
