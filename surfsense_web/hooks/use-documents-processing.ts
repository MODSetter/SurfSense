"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useEffect, useRef, useState } from "react";
import { queries } from "@/zero/queries";

export type DocumentsProcessingStatus =
	| "idle"
	| "processing"
	| "background_sync"
	| "success"
	| "error";

const SUCCESS_LINGER_MS = 5000;

interface UseDocumentsProcessingOptions {
	hasPeriodicSyncEnabled?: boolean;
}

/**
 * Returns the processing status of documents in the search space:
 *   - "processing"      — docs are queued or actively being prepared for search
 *   - "background_sync" — existing docs are being refreshed in the background
 *   - "error"      — nothing processing, but failed docs exist (show red icon)
 *   - "success"    — just transitioned from processing → all clear (green check, auto-dismisses)
 *   - "idle"       — nothing noteworthy (show normal icon)
 */
export function useDocumentsProcessing(
	searchSpaceId: number | null,
	{ hasPeriodicSyncEnabled = false }: UseDocumentsProcessingOptions = {}
): DocumentsProcessingStatus {
	const [status, setStatus] = useState<DocumentsProcessingStatus>("idle");
	const wasProcessingRef = useRef(false);
	const successTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	const [documents] = useQuery(queries.documents.bySpace({ searchSpaceId: searchSpaceId ?? -1 }));

	useEffect(() => {
		if (!searchSpaceId || !documents) return;

		const clearSuccessTimer = () => {
			if (successTimerRef.current) {
				clearTimeout(successTimerRef.current);
				successTimerRef.current = null;
			}
		};

		let pendingCount = 0;
		let processingCount = 0;
		let failedCount = 0;
		let readyCount = 0;

		for (const doc of documents) {
			// Keep the nav indicator aligned with what the Documents sidebar actually renders.
			// Some connectors can create temporary untitled placeholder rows that remain hidden
			// from the sidebar, and those should not keep the whole section looking "stuck".
			if (!doc.title || doc.title.trim() === "") {
				continue;
			}

			const state = (doc.status as { state?: string } | null)?.state;
			if (state === "pending") {
				pendingCount++;
			} else if (state === "processing") {
				processingCount++;
			} else if (state === "failed") {
				failedCount++;
			} else {
				readyCount++;
			}
		}

		if (pendingCount > 0) {
			wasProcessingRef.current = true;
			clearSuccessTimer();
			setStatus("processing");
		} else if (processingCount > 0) {
			wasProcessingRef.current = true;
			clearSuccessTimer();

			const isBackgroundSync = hasPeriodicSyncEnabled && readyCount > 0;
			setStatus(isBackgroundSync ? "background_sync" : "processing");
		} else if (failedCount > 0) {
			wasProcessingRef.current = false;
			clearSuccessTimer();
			setStatus("error");
		} else if (wasProcessingRef.current) {
			wasProcessingRef.current = false;
			setStatus("success");
			clearSuccessTimer();
			successTimerRef.current = setTimeout(() => {
				setStatus("idle");
				successTimerRef.current = null;
			}, SUCCESS_LINGER_MS);
		} else {
			setStatus("idle");
		}
	}, [searchSpaceId, documents, hasPeriodicSyncEnabled]);

	useEffect(() => {
		return () => {
			if (successTimerRef.current) {
				clearTimeout(successTimerRef.current);
				successTimerRef.current = null;
			}
		};
	}, []);

	return status;
}
