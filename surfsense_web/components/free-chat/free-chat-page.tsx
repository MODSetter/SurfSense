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
import { ThinkingStepsDataUI } from "@/components/assistant-ui/thinking-steps";
import {
	createTokenUsageStore,
	type TokenUsageData,
	TokenUsageProvider,
} from "@/components/assistant-ui/token-usage-context";
import { useAnonymousMode } from "@/contexts/anonymous-mode";
import {
	addStepSeparator,
	addToolCall,
	appendReasoning,
	appendText,
	buildContentForUI,
	type ContentPartsState,
	endReasoning,
	FrameBatchedUpdater,
	readSSEStream,
	type ThinkingStepData,
	updateThinkingSteps,
	updateToolCall,
} from "@/lib/chat/streaming-state";
import { BACKEND_URL } from "@/lib/env-config";
import { trackAnonymousChatMessageSent } from "@/lib/posthog/events";
import { FreeModelSelector } from "./free-model-selector";
import { FreeThread } from "./free-thread";

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

export function FreeChatPage() {
	const anonMode = useAnonymousMode();
	const modelSlug = anonMode.isAnonymous ? anonMode.modelSlug : "";
	const resetKey = anonMode.isAnonymous ? anonMode.resetKey : 0;

	const [messages, setMessages] = useState<ThreadMessageLike[]>([]);
	const [isRunning, setIsRunning] = useState(false);
	const [tokenUsageStore] = useState(() => createTokenUsageStore());
	const abortControllerRef = useRef<AbortController | null>(null);

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

	const cancelRun = useCallback(() => {
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
		): Promise<"captcha" | void> => {
			const reqBody: Record<string, unknown> = {
				model_slug: modelSlug,
				messages: messageHistory,
			};
			if (turnstileToken) reqBody.turnstile_token = turnstileToken;

			const response = await fetch(`${BACKEND_URL}/api/v1/public/anon-chat/stream`, {
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
				throw new Error(body || `Server error: ${response.status}`);
			}

			const currentThinkingSteps = new Map<string, ThinkingStepData>();
			const batcher = new FrameBatchedUpdater();
			const contentPartsState: ContentPartsState = {
				contentParts: [],
				currentTextPartIndex: -1,
				currentReasoningPartIndex: -1,
				toolCallIndices: new Map(),
			};
			const { toolCallIndices } = contentPartsState;

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

			try {
				for await (const parsed of readSSEStream(response)) {
					switch (parsed.type) {
						case "text-delta":
							appendText(contentPartsState, parsed.delta);
							scheduleFlush();
							break;

						case "reasoning-delta":
							appendReasoning(contentPartsState, parsed.delta);
							scheduleFlush();
							break;

						case "reasoning-end":
							endReasoning(contentPartsState);
							scheduleFlush();
							break;

						case "start-step":
							addStepSeparator(contentPartsState);
							scheduleFlush();
							break;

						case "finish-step":
							break;

						case "tool-input-start":
							addToolCall(
								contentPartsState,
								TOOLS_WITH_UI,
								parsed.toolCallId,
								parsed.toolName,
								{},
								false,
								parsed.langchainToolCallId
							);
							batcher.flush();
							break;

						case "tool-input-available":
							if (toolCallIndices.has(parsed.toolCallId)) {
								updateToolCall(contentPartsState, parsed.toolCallId, {
									args: parsed.input || {},
									langchainToolCallId: parsed.langchainToolCallId,
								});
							} else {
								addToolCall(
									contentPartsState,
									TOOLS_WITH_UI,
									parsed.toolCallId,
									parsed.toolName,
									parsed.input || {},
									false,
									parsed.langchainToolCallId
								);
							}
							batcher.flush();
							break;

						case "tool-output-available":
							updateToolCall(contentPartsState, parsed.toolCallId, {
								result: parsed.output,
								langchainToolCallId: parsed.langchainToolCallId,
							});
							batcher.flush();
							break;

						case "data-thinking-step": {
							const stepData = parsed.data as ThinkingStepData;
							if (stepData?.id) {
								currentThinkingSteps.set(stepData.id, stepData);
								if (updateThinkingSteps(contentPartsState, currentThinkingSteps)) scheduleFlush();
							}
							break;
						}

						case "data-token-usage":
							tokenUsageStore.set(assistantMsgId, parsed.data as TokenUsageData);
							break;

						case "error":
							throw new Error(parsed.errorText || "Server error");
					}
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

			const messageHistory = messages
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
				const errorText = error instanceof Error ? error.message : "An unexpected error occurred";
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
		[messages, doStream]
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
				const errorText = error instanceof Error ? error.message : "An unexpected error occurred";
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
				<ThinkingStepsDataUI />
				<StepSeparatorDataUI />
				<div className="flex h-full flex-col overflow-hidden">
					<div className="flex h-14 shrink-0 items-center justify-between border-b border-border/40 px-4">
						<FreeModelSelector />
					</div>

					{captchaRequired && TURNSTILE_SITE_KEY && (
						<div className="flex flex-col items-center gap-3 border-b border-border/40 bg-muted/30 py-4">
							<div className="flex items-center gap-2 text-sm text-muted-foreground">
								<ShieldCheck className="h-4 w-4" />
								<span>Quick verification to continue chatting</span>
							</div>
							<Turnstile
								ref={turnstileRef}
								siteKey={TURNSTILE_SITE_KEY}
								onSuccess={handleTurnstileSuccess}
								onError={() => turnstileRef.current?.reset()}
								onExpire={() => turnstileRef.current?.reset()}
								options={{ theme: "auto", size: "normal" }}
							/>
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
