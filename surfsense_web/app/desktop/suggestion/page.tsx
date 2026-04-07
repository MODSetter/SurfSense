"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useElectronAPI } from "@/hooks/use-platform";
import { ensureTokensFromElectron, getBearerToken } from "@/lib/auth-utils";

type SSEEvent =
	| { type: "text-delta"; id: string; delta: string }
	| { type: "text-start"; id: string }
	| { type: "text-end"; id: string }
	| { type: "start"; messageId: string }
	| { type: "finish" }
	| { type: "error"; errorText: string }
	| {
			type: "data-thinking-step";
			data: { id: string; title: string; status: string; items: string[] };
	  }
	| {
			type: "data-suggestions";
			data: { options: string[] };
	  };

interface AgentStep {
	id: string;
	title: string;
	status: string;
	items: string[];
}

type FriendlyError = { message: string; isSetup?: boolean };

function friendlyError(raw: string | number): FriendlyError {
	if (typeof raw === "number") {
		if (raw === 401) return { message: "Please sign in to use suggestions." };
		if (raw === 403) return { message: "You don\u2019t have permission for this." };
		if (raw === 404) return { message: "Suggestion service not found. Is the backend running?" };
		if (raw >= 500) return { message: "Something went wrong on the server. Try again." };
		return { message: "Something went wrong. Try again." };
	}
	const lower = raw.toLowerCase();
	if (lower.includes("not authenticated") || lower.includes("unauthorized"))
		return { message: "Please sign in to use suggestions." };
	if (lower.includes("no vision llm configured") || lower.includes("no llm configured"))
		return {
			message: "Configure a vision-capable model (e.g. GPT-4o, Gemini) to enable autocomplete.",
			isSetup: true,
		};
	if (lower.includes("does not support vision"))
		return {
			message: "The selected model doesn\u2019t support vision. Choose a vision-capable model.",
			isSetup: true,
		};
	if (lower.includes("fetch") || lower.includes("network") || lower.includes("econnrefused"))
		return { message: "Can\u2019t reach the server. Check your connection." };
	return { message: "Something went wrong. Try again." };
}

const AUTO_DISMISS_MS = 3000;

function StepIcon({ status }: { status: string }) {
	if (status === "complete") {
		return (
			<svg
				className="step-icon step-icon-done"
				viewBox="0 0 16 16"
				fill="none"
				aria-label="Step complete"
			>
				<circle cx="8" cy="8" r="7" stroke="#4ade80" strokeWidth="1.5" />
				<path
					d="M5 8.5l2 2 4-4.5"
					stroke="#4ade80"
					strokeWidth="1.5"
					strokeLinecap="round"
					strokeLinejoin="round"
				/>
			</svg>
		);
	}
	return <span className="step-spinner" />;
}

export default function SuggestionPage() {
	const api = useElectronAPI();
	const [options, setOptions] = useState<string[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<FriendlyError | null>(null);
	const [steps, setSteps] = useState<AgentStep[]>([]);
	const [expandedOption, setExpandedOption] = useState<number | null>(null);
	const abortRef = useRef<AbortController | null>(null);

	const isDesktop = !!api?.onAutocompleteContext;

	useEffect(() => {
		if (!api?.onAutocompleteContext) {
			setIsLoading(false);
		}
	}, [api]);

	useEffect(() => {
		if (!error || error.isSetup) return;
		const timer = setTimeout(() => {
			api?.dismissSuggestion?.();
		}, AUTO_DISMISS_MS);
		return () => clearTimeout(timer);
	}, [error, api]);

	useEffect(() => {
		if (isLoading || error || options.length > 0) return;
		const timer = setTimeout(() => {
			api?.dismissSuggestion?.();
		}, AUTO_DISMISS_MS);
		return () => clearTimeout(timer);
	}, [isLoading, error, options, api]);

	const fetchSuggestion = useCallback(
		async (screenshot: string, searchSpaceId: string, appName?: string, windowTitle?: string) => {
			abortRef.current?.abort();
			const controller = new AbortController();
			abortRef.current = controller;

			setIsLoading(true);
			setOptions([]);
			setError(null);
			setSteps([]);
			setExpandedOption(null);

			let token = getBearerToken();
			if (!token) {
				await ensureTokensFromElectron();
				token = getBearerToken();
			}
			if (!token) {
				setError(friendlyError("not authenticated"));
				setIsLoading(false);
				return;
			}

			const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";

			try {
				const response = await fetch(`${backendUrl}/api/v1/autocomplete/vision/stream`, {
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
				});

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
								if (parsed.type === "data-suggestions") {
									setOptions(parsed.data.options);
								} else if (parsed.type === "error") {
									setError(friendlyError(parsed.errorText));
								} else if (parsed.type === "data-thinking-step") {
									const { id, title, status, items } = parsed.data;
									setSteps((prev) => {
										const existing = prev.findIndex((s) => s.id === id);
										if (existing >= 0) {
											const updated = [...prev];
											updated[existing] = { id, title, status, items };
											return updated;
										}
										return [...prev, { id, title, status, items }];
									});
								}
							} catch {}
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
		[]
	);

	useEffect(() => {
		if (!api?.onAutocompleteContext) return;

		const cleanup = api.onAutocompleteContext((data) => {
			const searchSpaceId = data.searchSpaceId || "1";
			if (data.screenshot) {
				fetchSuggestion(data.screenshot, searchSpaceId, data.appName, data.windowTitle);
			}
		});

		return cleanup;
	}, [fetchSuggestion, api]);

	if (!isDesktop) {
		return (
			<div className="suggestion-tooltip">
				<span className="suggestion-error-text">
					This page is only available in the SurfSense desktop app.
				</span>
			</div>
		);
	}

	if (error) {
		if (error.isSetup) {
			return (
				<div className="suggestion-tooltip suggestion-setup">
					<div className="setup-icon">
						<svg viewBox="0 0 24 24" fill="none" width="28" height="28" aria-hidden="true">
							<path
								d="M1 12C1 12 5 4 12 4C19 4 23 12 23 12C23 12 19 20 12 20C5 20 1 12 1 12Z"
								stroke="#a78bfa"
								strokeWidth="1.5"
								strokeLinecap="round"
								strokeLinejoin="round"
							/>
							<circle
								cx="12"
								cy="12"
								r="3"
								stroke="#a78bfa"
								strokeWidth="1.5"
								strokeLinecap="round"
								strokeLinejoin="round"
							/>
						</svg>
					</div>
					<div className="setup-content">
						<span className="setup-title">Vision Model Required</span>
						<span className="setup-message">{error.message}</span>
						<span className="setup-hint">Settings → Vision Models</span>
					</div>
					<button
						type="button"
						className="setup-dismiss"
						onClick={() => api?.dismissSuggestion?.()}
					>
						✕
					</button>
				</div>
			);
		}
		return (
			<div className="suggestion-tooltip suggestion-error">
				<span className="suggestion-error-text">{error.message}</span>
			</div>
		);
	}

	const showLoading = isLoading && options.length === 0;

	if (showLoading) {
		return (
			<div className="suggestion-tooltip">
				<div className="agent-activity">
					{steps.length === 0 && (
						<div className="activity-initial">
							<span className="step-spinner" />
							<span className="activity-label">Preparing…</span>
						</div>
					)}
					{steps.length > 0 && (
						<div className="activity-steps">
							{steps.map((step) => (
								<div key={step.id} className="activity-step">
									<StepIcon status={step.status} />
									<span className="step-label">
										{step.title}
										{step.items.length > 0 && (
											<span className="step-detail"> · {step.items[0]}</span>
										)}
									</span>
								</div>
							))}
						</div>
					)}
				</div>
			</div>
		);
	}

	const handleSelect = (text: string) => {
		api?.acceptSuggestion?.(text);
	};

	const handleDismiss = () => {
		api?.dismissSuggestion?.();
	};

	const TRUNCATE_LENGTH = 120;

	if (options.length === 0) {
		return (
			<div className="suggestion-tooltip suggestion-error">
				<span className="suggestion-error-text">No suggestions available.</span>
			</div>
		);
	}

	return (
		<div className="suggestion-tooltip">
			<div className="suggestion-options">
				{options.map((option, index) => {
					const isExpanded = expandedOption === index;
					const needsTruncation = option.length > TRUNCATE_LENGTH;
					const displayText =
						needsTruncation && !isExpanded ? option.slice(0, TRUNCATE_LENGTH) + "…" : option;

					return (
						<div
							key={index}
							role="button"
							tabIndex={0}
							className="suggestion-option"
							onClick={() => handleSelect(option)}
							onKeyDown={(e) => {
								if (e.key === "Enter") handleSelect(option);
							}}
						>
							<span className="option-number">{index + 1}</span>
							<span className="option-text">{displayText}</span>
							{needsTruncation && (
								<button
									type="button"
									className="option-expand"
									onClick={(e) => {
										e.stopPropagation();
										setExpandedOption(isExpanded ? null : index);
									}}
								>
									{isExpanded ? "less" : "more"}
								</button>
							)}
						</div>
					);
				})}
			</div>
			<div className="suggestion-actions">
				<button
					type="button"
					className="suggestion-btn suggestion-btn-dismiss"
					onClick={handleDismiss}
				>
					Dismiss
				</button>
			</div>
		</div>
	);
}
