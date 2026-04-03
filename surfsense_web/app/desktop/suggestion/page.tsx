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

function friendlyError(raw: string | number): string {
	if (typeof raw === "number") {
		if (raw === 401) return "Please sign in to use suggestions.";
		if (raw === 403) return "You don\u2019t have permission for this.";
		if (raw === 404) return "Suggestion service not found. Is the backend running?";
		if (raw >= 500) return "Something went wrong on the server. Try again.";
		return "Something went wrong. Try again.";
	}
	const lower = raw.toLowerCase();
	if (lower.includes("not authenticated") || lower.includes("unauthorized"))
		return "Please sign in to use suggestions.";
	if (lower.includes("no vision llm configured") || lower.includes("no llm configured"))
		return "No Vision LLM configured. Set one in search space settings.";
	if (lower.includes("fetch") || lower.includes("network") || lower.includes("econnrefused"))
		return "Can\u2019t reach the server. Check your connection.";
	return "Something went wrong. Try again.";
}

const AUTO_DISMISS_MS = 3000;

export default function SuggestionPage() {
	const [suggestion, setSuggestion] = useState("");
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const abortRef = useRef<AbortController | null>(null);

	useEffect(() => {
		if (!error) return;
		const timer = setTimeout(() => {
			window.electronAPI?.dismissSuggestion?.();
		}, AUTO_DISMISS_MS);
		return () => clearTimeout(timer);
	}, [error]);

	const fetchSuggestion = useCallback(
		async (screenshot: string, searchSpaceId: string, appName?: string, windowTitle?: string) => {
			abortRef.current?.abort();
			const controller = new AbortController();
			abortRef.current = controller;

			setIsLoading(true);
			setSuggestion("");
			setError(null);

			const token = getBearerToken();
			if (!token) {
				setError(friendlyError("not authenticated"));
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
							app_name: appName || "",
							window_title: windowTitle || "",
						}),
						signal: controller.signal,
					},
				);

				if (!response.ok) {
					setError(friendlyError(response.status));
					setIsLoading(false);
					return;
				}

				if (!response.body) {
					setError(friendlyError("network error"));
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
									setSuggestion((prev) => prev + parsed.delta);
								} else if (parsed.type === "error") {
									setError(friendlyError(parsed.errorText));
								}
							} catch {
								continue;
							}
						}
					}
				}
			} catch (err) {
				if (err instanceof DOMException && err.name === "AbortError") return;
				setError(friendlyError("network error"));
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
				fetchSuggestion(data.screenshot, searchSpaceId, data.appName, data.windowTitle);
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

	const handleAccept = () => {
		if (suggestion) {
			window.electronAPI?.acceptSuggestion?.(suggestion);
		}
	};

	const handleDismiss = () => {
		window.electronAPI?.dismissSuggestion?.();
	};

	if (!suggestion) return null;

	return (
		<div className="suggestion-tooltip">
			<p className="suggestion-text">{suggestion}</p>
			<div className="suggestion-actions">
				<button className="suggestion-btn suggestion-btn-accept" onClick={handleAccept}>
					Accept
				</button>
				<button className="suggestion-btn suggestion-btn-dismiss" onClick={handleDismiss}>
					Dismiss
				</button>
			</div>
		</div>
	);
}
