"use client";

import {
	type AppendMessage,
	AssistantRuntimeProvider,
	type ThreadMessageLike,
	useExternalStoreRuntime,
} from "@assistant-ui/react";
import { Turnstile, type TurnstileInstance } from "@marsidev/react-turnstile";
import { ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { StepSeparatorDataUI } from "@/components/assistant-ui/step-separator";
import {
	createTokenUsageStore,
	type TokenUsageData,
	TokenUsageProvider,
} from "@/components/assistant-ui/token-usage-context";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useAnonymousMode } from "@/contexts/anonymous-mode";
import { TimelineDataUI } from "@/features/chat-messages/timeline";
import { classifyChatError, GENERIC_CHAT_ERROR_MESSAGE } from "@/lib/chat/chat-error-classifier";
import { processSharedStreamEvent } from "@/lib/chat/stream-pipeline";
import {
	buildContentForUI,
	type ContentPartsState,
	FrameBatchedUpdater,
	readSSEStream,
} from "@/lib/chat/streaming-state";
import { buildBackendUrl } from "@/lib/env-config";
import { trackAnonymousChatMessageSent } from "@/lib/posthog/events";
import { FreeThread } from "./free-thread";
import { RemoveAdsBanner } from "./remove-ads-banner";

// Render all tool calls via ToolFallback; backend keeps persisted
// payloads bounded by summarising / truncating outputs.
const TOOLS_WITH_UI = "all" as const;
const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";

/** Try to parse a CAPTCHA_REQUIRED or CAPTCHA_INVALID code from a non-ok response. */
function parseCaptchaError(status: number, body: string): string | null {
	if (status !== 403) return null;
	try {
		const json = JSON.parse(body);
		const code = json?.detail?.code ?? json?.error?.code;
		if (code === "CAPTCHA_REQUIRED" || code === "CAPTCHA_INVALID") return code;
	} catch {
		/* not JSON */
	}
	return null;
}

function normalizeFreeChatErrorMessage(error: unknown): string {
	return classifyChatError({ error, flow: "new" }).userMessage;
}

function toFreeChatHttpError(status: number, body: string): Error & { errorCode?: string } {
	let errorCode: string | undefined;
	let message = GENERIC_CHAT_ERROR_MESSAGE;
	try {
		const parsed = JSON.parse(body) as Record<string, unknown>;
		const detail =
			typeof parsed.detail === "object" && parsed.detail !== null
				? (parsed.detail as Record<string, unknown>)
				: null;
		errorCode =
			(typeof detail?.error_code === "string" ? detail.error_code : undefined) ??
			(typeof detail?.errorCode === "string" ? detail.errorCode : undefined) ??
			(typeof parsed.error_code === "string" ? parsed.error_code : undefined) ??
			(typeof parsed.errorCode === "string" ? parsed.errorCode : undefined);
		message =
			(typeof detail?.message === "string" ? detail.message : undefined) ??
			(typeof parsed.message === "string" ? parsed.message : undefined) ??
			message;
	} catch {
		// non-json response
	}

	if (!errorCode) {
		if (status === 409) errorCode = "THREAD_BUSY";
		else if (status === 429) errorCode = "RATE_LIMITED";
		else if (status === 401 || status === 403) errorCode = "AUTH_EXPIRED";
		else errorCode = "SERVER_ERROR";
	}

	return Object.assign(new Error(message), { errorCode });
}

export function FreeChatPage() {
	const anonMode = useAnonymousMode();
	const modelSlug = anonMode.isAnonymous ? anonMode.modelSlug : "";
	const resetKey = anonMode.isAnonymous ? anonMode.resetKey : 0;

	const [messages, setMessages] = useState<ThreadMessageLike[]>([]);
	const [isRunning, setIsRunning] = useState(false);
	const [tokenUsageStore] = useState(() => createTokenUsageStore());
	const abortControllerRef = useRef<AbortController | null>(null);
	// Mirror the latest messages into a ref so onNew stays a stable callback
	// (it reads history on demand instead of depending on the array).
	const messagesRef = useRef<ThreadMessageLike[]>([]);
	messagesRef.current = messages;

	// Turnstile CAPTCHA state
	const [captchaRequired, setCaptchaRequired] = useState(false);
	const turnstileRef = useRef<TurnstileInstance | null>(null);
	const turnstileTokenRef = useRef<string | null>(null);
	const pendingRetryRef = useRef<{
		messageHistory: { role: string; content: string }[];
		userMsgId: string;
	} | null>(null);

	useEffect(() => {
		setMessages([]);
		tokenUsageStore.clear();
		if (abortControllerRef.current) {
			abortControllerRef.current.abort();
			abortControllerRef.current = null;
		}
		setIsRunning(false);
		setCaptchaRequired(false);
		turnstileTokenRef.current = null;
		pendingRetryRef.current = null;
	}, [resetKey, modelSlug, tokenUsageStore]);

	const cancelRun = useCallback(async () => {
		if (abortControllerRef.current) {
			abortControllerRef.current.abort();
			abortControllerRef.current = null;
		}
		setIsRunning(false);
	}, []);

	/**
	 * Core streaming logic shared by initial sends and CAPTCHA retries.
	 * Returns "captcha" if the server demands a CAPTCHA, otherwise void.
	 */
	const doStream = useCallback(
		async (
			messageHistory: { role: string; content: string }[],
			assistantMsgId: string,
			signal: AbortSignal,
			turnstileToken: string | null
		): Promise<"captcha" | undefined> => {
			const reqBody: Record<string, unknown> = {
				model_slug: modelSlug,
				messages: messageHistory,
			};
			if (turnstileToken) reqBody.turnstile_token = turnstileToken;

			const response = await fetch(buildBackendUrl("/api/v1/public/anon-chat/stream"), {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				credentials: "include",
				body: JSON.stringify(reqBody),
				signal,
			});

			if (!response.ok) {
				const body = await response.text().catch(() => "");
				const captchaCode = parseCaptchaError(response.status, body);
				if (captchaCode) return "captcha";
				throw toFreeChatHttpError(response.status, body);
			}

			const batcher = new FrameBatchedUpdater();
			const contentPartsState: ContentPartsState = {
				contentParts: [],
				currentTextPartIndex: -1,
				currentReasoningPartIndex: -1,
				toolCallIndices: new Map(),
				activities: new Map(),
			};

			const flushMessages = () => {
				setMessages((prev) =>
					prev.map((m) =>
						m.id === assistantMsgId
							? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
							: m
					)
				);
			};
			const scheduleFlush = () => batcher.schedule(flushMessages);
			const forceFlush = () => {
				scheduleFlush();
				batcher.flush();
			};

			try {
				for await (const parsed of readSSEStream(response)) {
					processSharedStreamEvent(parsed, {
						contentPartsState,
						toolsWithUI: TOOLS_WITH_UI,
						scheduleFlush,
						forceFlush,
						onTokenUsage: (data) => tokenUsageStore.set(assistantMsgId, data as TokenUsageData),
					});
				}
				batcher.flush();
			} catch (err) {
				batcher.dispose();
				throw err;
			}
		},
		[modelSlug, tokenUsageStore]
	);

	const onNew = useCallback(
		async (message: AppendMessage) => {
			let userQuery = "";
			for (const part of message.content) {
				if (part.type === "text") userQuery += part.text;
			}
			if (!userQuery.trim()) return;

			trackAnonymousChatMessageSent({
				modelSlug,
				messageLength: userQuery.trim().length,
				hasUploadedDoc: anonMode.isAnonymous && anonMode.uploadedDoc !== null ? true : false,
				surface: "free_chat_page",
			});

			const userMsgId = `msg-user-${Date.now()}`;
			setMessages((prev) => [
				...prev,
				{
					id: userMsgId,
					role: "user" as const,
					content: [{ type: "text" as const, text: userQuery }],
					createdAt: new Date(),
				},
			]);

			setIsRunning(true);
			const controller = new AbortController();
			abortControllerRef.current = controller;

			const assistantMsgId = `msg-assistant-${Date.now()}`;
			setMessages((prev) => [
				...prev,
				{
					id: assistantMsgId,
					role: "assistant" as const,
					content: [{ type: "text" as const, text: "" }],
					createdAt: new Date(),
				},
			]);

			const messageHistory = messagesRef.current
				.filter((m) => m.role === "user" || m.role === "assistant")
				.map((m) => {
					let text = "";
					for (const part of m.content) {
						if (typeof part === "object" && part.type === "text" && "text" in part) {
							text += (part as { type: "text"; text: string }).text;
						}
					}
					return { role: m.role as string, content: text };
				})
				.filter((m) => m.content.length > 0);
			messageHistory.push({ role: "user", content: userQuery.trim() });

			try {
				const result = await doStream(
					messageHistory,
					assistantMsgId,
					controller.signal,
					turnstileTokenRef.current
				);

				// Consume the token after use regardless of outcome
				turnstileTokenRef.current = null;

				if (result === "captcha" && TURNSTILE_SITE_KEY) {
					// Remove the empty assistant placeholder; keep the user message
					setMessages((prev) => prev.filter((m) => m.id !== assistantMsgId));
					pendingRetryRef.current = { messageHistory, userMsgId };
					setCaptchaRequired(true);
					setIsRunning(false);
					abortControllerRef.current = null;
					return;
				}
			} catch (error) {
				if (error instanceof Error && error.name === "AbortError") return;
				console.error("[FreeChatPage] Chat error:", error);
				const errorText = normalizeFreeChatErrorMessage(error);
				setMessages((prev) =>
					prev.map((m) =>
						m.id === assistantMsgId
							? { ...m, content: [{ type: "text" as const, text: `Error: ${errorText}` }] }
							: m
					)
				);
			} finally {
				setIsRunning(false);
				abortControllerRef.current = null;
			}
		},
		[modelSlug, anonMode, doStream]
	);

	/** Called when Turnstile resolves successfully. Stores the token and auto-retries. */
	const handleTurnstileSuccess = useCallback(
		async (token: string) => {
			turnstileTokenRef.current = token;
			setCaptchaRequired(false);

			const pending = pendingRetryRef.current;
			if (!pending) return;
			pendingRetryRef.current = null;

			setIsRunning(true);
			const controller = new AbortController();
			abortControllerRef.current = controller;

			const assistantMsgId = `msg-assistant-${Date.now()}`;
			setMessages((prev) => [
				...prev,
				{
					id: assistantMsgId,
					role: "assistant" as const,
					content: [{ type: "text" as const, text: "" }],
					createdAt: new Date(),
				},
			]);

			try {
				const result = await doStream(
					pending.messageHistory,
					assistantMsgId,
					controller.signal,
					token
				);
				turnstileTokenRef.current = null;

				if (result === "captcha") {
					setMessages((prev) => prev.filter((m) => m.id !== assistantMsgId));
					pendingRetryRef.current = pending;
					setCaptchaRequired(true);
					turnstileRef.current?.reset();
				}
			} catch (error) {
				if (error instanceof Error && error.name === "AbortError") return;
				console.error("[FreeChatPage] Retry error:", error);
				const errorText = normalizeFreeChatErrorMessage(error);
				setMessages((prev) =>
					prev.map((m) =>
						m.id === assistantMsgId
							? { ...m, content: [{ type: "text" as const, text: `Error: ${errorText}` }] }
							: m
					)
				);
			} finally {
				setIsRunning(false);
				abortControllerRef.current = null;
			}
		},
		[doStream]
	);

	const convertMessage = useCallback(
		(message: ThreadMessageLike): ThreadMessageLike => message,
		[]
	);

	const runtime = useExternalStoreRuntime({
		messages,
		isRunning,
		onNew,
		convertMessage,
		onCancel: cancelRun,
	});

	return (
		<TokenUsageProvider store={tokenUsageStore}>
			<AssistantRuntimeProvider runtime={runtime}>
				<TimelineDataUI />
				<StepSeparatorDataUI />
				<div className="flex h-full flex-col overflow-hidden">
					<RemoveAdsBanner />

					{captchaRequired && TURNSTILE_SITE_KEY && (
						<div className="flex justify-center border-b bg-muted/30 px-4 py-4">
							<Alert className="w-auto max-w-md">
								<ShieldCheck />
								<AlertTitle>Quick verification to continue chatting</AlertTitle>
								<AlertDescription>
									<Turnstile
										ref={turnstileRef}
										siteKey={TURNSTILE_SITE_KEY}
										onSuccess={handleTurnstileSuccess}
										onError={() => turnstileRef.current?.reset()}
										onExpire={() => turnstileRef.current?.reset()}
										options={{ theme: "auto", size: "normal" }}
									/>
								</AlertDescription>
							</Alert>
						</div>
					)}

					<div className="flex flex-1 min-h-0 overflow-hidden">
						<div className="flex-1 flex flex-col min-w-0">
							<FreeThread />
						</div>
					</div>
				</div>
			</AssistantRuntimeProvider>
		</TokenUsageProvider>
	);
}
