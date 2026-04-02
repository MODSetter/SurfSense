"use client";

import { useEffect, useRef } from "react";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";

const DEBOUNCE_MS = 2000;

export function useFolderSync() {
	const pendingRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

	useEffect(() => {
		const api = typeof window !== "undefined" ? window.electronAPI : null;
		if (!api?.onFileChanged) return;

		const cleanup = api.onFileChanged((event) => {
			const key = `${event.connectorId}:${event.fullPath}`;

			const existing = pendingRef.current.get(key);
			if (existing) clearTimeout(existing);

			const timeout = setTimeout(async () => {
				pendingRef.current.delete(key);
				try {
					await connectorsApiService.indexFile(event.connectorId, event.fullPath);
				} catch (err) {
					console.error("[FolderSync] Failed to trigger re-index:", err);
				}
			}, DEBOUNCE_MS);

			pendingRef.current.set(key, timeout);
		});

		return () => {
			cleanup();
			for (const timeout of pendingRef.current.values()) {
				clearTimeout(timeout);
			}
			pendingRef.current.clear();
		};
	}, []);
}
