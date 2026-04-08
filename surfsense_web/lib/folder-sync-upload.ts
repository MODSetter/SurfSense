import { documentsApiService } from "@/lib/apis/documents-api.service";

const MAX_BATCH_SIZE_BYTES = 20 * 1024 * 1024; // 20 MB
const MAX_BATCH_FILES = 10;
const UPLOAD_CONCURRENCY = 3;

export interface FolderSyncProgress {
	phase: "listing" | "checking" | "uploading" | "finalizing" | "done";
	uploaded: number;
	total: number;
}

export interface FolderSyncParams {
	folderPath: string;
	folderName: string;
	searchSpaceId: number;
	excludePatterns: string[];
	fileExtensions: string[];
	enableSummary: boolean;
	rootFolderId?: number | null;
	onProgress?: (progress: FolderSyncProgress) => void;
	signal?: AbortSignal;
}

function buildBatches(
	entries: FolderFileEntry[],
): FolderFileEntry[][] {
	const batches: FolderFileEntry[][] = [];
	let currentBatch: FolderFileEntry[] = [];
	let currentSize = 0;

	for (const entry of entries) {
		if (entry.size >= MAX_BATCH_SIZE_BYTES) {
			if (currentBatch.length > 0) {
				batches.push(currentBatch);
				currentBatch = [];
				currentSize = 0;
			}
			batches.push([entry]);
			continue;
		}

		if (
			currentBatch.length >= MAX_BATCH_FILES ||
			currentSize + entry.size > MAX_BATCH_SIZE_BYTES
		) {
			batches.push(currentBatch);
			currentBatch = [];
			currentSize = 0;
		}

		currentBatch.push(entry);
		currentSize += entry.size;
	}

	if (currentBatch.length > 0) {
		batches.push(currentBatch);
	}

	return batches;
}

async function uploadBatchesWithConcurrency(
	batches: FolderFileEntry[][],
	params: {
		folderName: string;
		searchSpaceId: number;
		rootFolderId: number | null;
		enableSummary: boolean;
		signal?: AbortSignal;
		onBatchComplete?: (filesInBatch: number) => void;
	},
): Promise<number | null> {
	const api = window.electronAPI;
	if (!api) throw new Error("Electron API not available");

	let batchIdx = 0;
	let resolvedRootFolderId = params.rootFolderId;
	const errors: string[] = [];

	async function processNext(): Promise<void> {
		while (true) {
			if (params.signal?.aborted) return;

			const idx = batchIdx++;
			if (idx >= batches.length) return;

			const batch = batches[idx];
			const fullPaths = batch.map((e) => e.fullPath);

			try {
				const fileDataArr = await api.readLocalFiles(fullPaths);

				const files: File[] = fileDataArr.map((fd) => {
					const blob = new Blob([fd.data], { type: fd.mimeType || "application/octet-stream" });
					return new File([blob], fd.name, { type: blob.type });
				});

				const result = await documentsApiService.folderUploadFiles(
					files,
					{
						folder_name: params.folderName,
						search_space_id: params.searchSpaceId,
						relative_paths: batch.map((e) => e.relativePath),
						root_folder_id: resolvedRootFolderId,
						enable_summary: params.enableSummary,
					},
					params.signal,
				);

				if (result.root_folder_id && !resolvedRootFolderId) {
					resolvedRootFolderId = result.root_folder_id;
				}

				params.onBatchComplete?.(batch.length);
			} catch (err) {
				if (params.signal?.aborted) return;
				const msg = (err as Error)?.message || "Upload failed";
				errors.push(`Batch ${idx}: ${msg}`);
			}
		}
	}

	const workers = Array.from({ length: Math.min(UPLOAD_CONCURRENCY, batches.length) }, () => processNext());
	await Promise.all(workers);

	if (errors.length > 0 && !params.signal?.aborted) {
		console.error("Some batches failed:", errors);
	}

	return resolvedRootFolderId;
}

/**
 * Run a full upload-based folder scan: list files, mtime-check, upload
 * changed files in parallel batches, and finalize (delete orphans).
 *
 * Returns the root_folder_id to pass to addWatchedFolder.
 */
export async function uploadFolderScan(params: FolderSyncParams): Promise<number | null> {
	const api = window.electronAPI;
	if (!api) throw new Error("Electron API not available");

	const { folderPath, folderName, searchSpaceId, excludePatterns, fileExtensions, enableSummary, signal } = params;
	let rootFolderId = params.rootFolderId ?? null;

	params.onProgress?.({ phase: "listing", uploaded: 0, total: 0 });

	if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

	const allFiles = await api.listFolderFiles({
		path: folderPath,
		name: folderName,
		excludePatterns,
		fileExtensions,
		rootFolderId: rootFolderId ?? null,
		searchSpaceId,
		active: true,
	});

	if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

	params.onProgress?.({ phase: "checking", uploaded: 0, total: allFiles.length });

	const mtimeCheckResult = await documentsApiService.folderMtimeCheck({
		folder_name: folderName,
		search_space_id: searchSpaceId,
		files: allFiles.map((f) => ({ relative_path: f.relativePath, mtime: f.mtimeMs / 1000 })),
	});

	const filesToUpload = mtimeCheckResult.files_to_upload;
	const uploadSet = new Set(filesToUpload);
	const entriesToUpload = allFiles.filter((f) => uploadSet.has(f.relativePath));

	if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

	if (entriesToUpload.length > 0) {
		const batches = buildBatches(entriesToUpload);

		let uploaded = 0;
		params.onProgress?.({ phase: "uploading", uploaded: 0, total: entriesToUpload.length });

		const uploadedRootId = await uploadBatchesWithConcurrency(batches, {
			folderName,
			searchSpaceId,
			rootFolderId: rootFolderId ?? null,
			enableSummary,
			signal,
			onBatchComplete: (count) => {
				uploaded += count;
				params.onProgress?.({ phase: "uploading", uploaded, total: entriesToUpload.length });
			},
		});

		if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

		if (uploadedRootId) {
			rootFolderId = uploadedRootId;
		}
	}

	if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

	params.onProgress?.({ phase: "finalizing", uploaded: entriesToUpload.length, total: entriesToUpload.length });

	await documentsApiService.folderSyncFinalize({
		folder_name: folderName,
		search_space_id: searchSpaceId,
		root_folder_id: rootFolderId ?? null,
		all_relative_paths: allFiles.map((f) => f.relativePath),
	});

	params.onProgress?.({ phase: "done", uploaded: entriesToUpload.length, total: entriesToUpload.length });

	// Seed the Electron mtime store so the reconciliation scan in
	// startWatcher won't re-emit events for files we just indexed.
	if (api.seedFolderMtimes) {
		const mtimes: Record<string, number> = {};
		for (const f of allFiles) {
			mtimes[f.relativePath] = f.mtimeMs;
		}
		await api.seedFolderMtimes(folderPath, mtimes);
	}

	return rootFolderId;
}
