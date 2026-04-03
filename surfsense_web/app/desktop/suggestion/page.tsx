"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getBearerToken } from "@/lib/auth-utils";

type SSEEvent =
	| { type: "text-delta"; id: string; delta: string }
	| { type: "text-start"; id: string }
	| { type: "text-end"; id: string }
	| { type: "start"; messageId: string }
	| { type: "finish" }
	| { type: "error"; errorText: string };

export default function SuggestionPage() {
	const [suggestion, setSuggestion] = useState("");
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const abortRef = useRef<AbortController | null>(null);

	const fetchSuggestion = useCallback(
		async (screenshot: string, searchSpaceId: string) => {
			abortRef.current?.abort();
			const controller = new AbortController();
			abortRef.current = controller;

			setIsLoading(true);
			setSuggestion("");
			setError(null);

			const token = getBearerToken();
			if (!token) {
				setError("Not authenticated");
				setIsLoading(false);
				return;
			}

			const backendUrl =
				process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";

			try {
				const response = await fetch(
					`${backendUrl}/api/v1/autocomplete/vision/stream`,
					{
						method: "POST",
						headers: {
							Authorization: `Bearer ${token}`,
							"Content-Type": "application/json",
						},
						body: JSON.stringify({
							screenshot,
							search_space_id: parseInt(searchSpaceId, 10),
						}),
						signal: controller.signal,
					},
				);

				if (!response.ok) {
					setError(`Error: ${response.status}`);
					setIsLoading(false);
					return;
				}

				if (!response.body) {
					setError("No response body");
					setIsLoading(false);
					return;
				}

				const reader = response.body.getReader();
				const decoder = new TextDecoder();
				let buffer = "";

				while (true) {
					const { done, value } = await reader.read();
					if (done) break;

					buffer += decoder.decode(value, { stream: true });
					const events = buffer.split(/\r?\n\r?\n/);
					buffer = events.pop() || "";

					for (const event of events) {
						const lines = event.split(/\r?\n/);
						for (const line of lines) {
							if (!line.startsWith("data: ")) continue;
							const data = line.slice(6).trim();
							if (!data || data === "[DONE]") continue;

							try {
								const parsed: SSEEvent = JSON.parse(data);
								if (parsed.type === "text-delta") {
									setSuggestion((prev) => {
										const updated = prev + parsed.delta;
										window.electronAPI?.updateSuggestionText?.(updated);
										return updated;
									});
								} else if (parsed.type === "error") {
									setError(parsed.errorText);
								}
							} catch {
								continue;
							}
						}
					}
				}
			} catch (err) {
				if (err instanceof DOMException && err.name === "AbortError") return;
				setError("Failed to get suggestion");
			} finally {
				setIsLoading(false);
			}
		},
		[],
	);

	useEffect(() => {
		if (!window.electronAPI?.onAutocompleteContext) return;

		const cleanup = window.electronAPI.onAutocompleteContext((data) => {
			const searchSpaceId = data.searchSpaceId || "1";
			if (data.screenshot) {
				fetchSuggestion(data.screenshot, searchSpaceId);
			}
		});

		return cleanup;
	}, [fetchSuggestion]);

	if (error) {
		return (
			<div className="suggestion-tooltip suggestion-error">
				<span className="suggestion-error-text">{error}</span>
			</div>
		);
	}

	if (isLoading && !suggestion) {
		return (
			<div className="suggestion-tooltip">
				<div className="suggestion-loading">
					<span className="suggestion-dot" />
					<span className="suggestion-dot" />
					<span className="suggestion-dot" />
				</div>
			</div>
		);
	}

	if (!suggestion) return null;

	return (
		<div className="suggestion-tooltip">
			<p className="suggestion-text">{suggestion}</p>
			<div className="suggestion-hint">
				<kbd>Tab</kbd> accept
				<span className="suggestion-separator" />
				<kbd>Esc</kbd> dismiss
			</div>
		</div>
	);
}
