"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useEffect, useRef, useState } from "react";
import { queries } from "@/zero/queries";

export type DocumentsProcessingStatus = "idle" | "processing" | "success" | "error";

const SUCCESS_LINGER_MS = 5000;

/**
 * Returns the processing status of documents in the search space:
 *   - "processing" — at least one doc is pending/processing (show spinner)
 *   - "error"      — nothing processing, but failed docs exist (show red icon)
 *   - "success"    — just transitioned from processing → all clear (green check, auto-dismisses)
 *   - "idle"       — nothing noteworthy (show normal icon)
 */
export function useDocumentsProcessing(searchSpaceId: number | null): DocumentsProcessingStatus {
	const [status, setStatus] = useState<DocumentsProcessingStatus>("idle");
	const wasProcessingRef = useRef(false);
	const successTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	const [documents] = useQuery(queries.documents.bySpace({ searchSpaceId: searchSpaceId ?? -1 }));

	useEffect(() => {
		if (!searchSpaceId || !documents) return;

		let processingCount = 0;
		let failedCount = 0;

		for (const doc of documents) {
			const state = (doc.status as { state?: string } | null)?.state;
			if (state === "pending" || state === "processing") {
				processingCount++;
			} else if (state === "failed") {
				failedCount++;
			}
		}

		if (processingCount > 0) {
			wasProcessingRef.current = true;
			if (successTimerRef.current) {
				clearTimeout(successTimerRef.current);
				successTimerRef.current = null;
			}
			setStatus("processing");
		} else if (failedCount > 0) {
			wasProcessingRef.current = false;
			if (successTimerRef.current) {
				clearTimeout(successTimerRef.current);
				successTimerRef.current = null;
			}
			setStatus("error");
		} else if (wasProcessingRef.current) {
			wasProcessingRef.current = false;
			setStatus("success");
			if (successTimerRef.current) {
				clearTimeout(successTimerRef.current);
			}
			successTimerRef.current = setTimeout(() => {
				setStatus("idle");
				successTimerRef.current = null;
			}, SUCCESS_LINGER_MS);
		} else {
			setStatus("idle");
		}
	}, [searchSpaceId, documents]);

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
