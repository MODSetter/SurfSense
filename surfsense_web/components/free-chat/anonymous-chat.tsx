"use client";

import { ArrowUp, Loader2, Square } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { AnonModel, AnonQuotaResponse } from "@/contracts/types/anonymous-chat.types";
import { anonymousChatApiService } from "@/lib/apis/anonymous-chat-api.service";
import { readSSEStream } from "@/lib/chat/streaming-state";
import { trackAnonymousChatMessageSent } from "@/lib/posthog/events";
import { cn } from "@/lib/utils";
import { QuotaBar } from "./quota-bar";
import { QuotaWarningBanner } from "./quota-warning-banner";

interface Message {
	id: string;
	role: "user" | "assistant";
	content: string;
}

interface AnonymousChatProps {
	model: AnonModel;
}

export function AnonymousChat({ model }: AnonymousChatProps) {
	const [messages, setMessages] = useState<Message[]>([]);
	const [input, setInput] = useState("");
	const [isStreaming, setIsStreaming] = useState(false);
	const [quota, setQuota] = useState<AnonQuotaResponse | null>(null);
	const abortRef = useRef<AbortController | null>(null);
	const messagesEndRef = useRef<HTMLDivElement>(null);
	const textareaRef = useRef<HTMLTextAreaElement>(null);

	useEffect(() => {
		anonymousChatApiService.getQuota().then(setQuota).catch(console.error);
	}, []);

	useEffect(() => {
		messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [messages]);

	const autoResizeTextarea = useCallback(() => {
		const textarea = textareaRef.current;
		if (textarea) {
			textarea.style.height = "auto";
			textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
		}
	}, []);

	const handleSubmit = useCallback(async () => {
		const trimmed = input.trim();
		if (!trimmed || isStreaming) return;
		if (quota && quota.used >= quota.limit) return;

		const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: trimmed };
		const assistantId = crypto.randomUUID();
		const assistantMsg: Message = { id: assistantId, role: "assistant", content: "" };

		setMessages((prev) => [...prev, userMsg, assistantMsg]);
		setInput("");
		setIsStreaming(true);

		if (textareaRef.current) {
			textareaRef.current.style.height = "auto";
		}

		trackAnonymousChatMessageSent({
			modelSlug: model.seo_slug,
			messageLength: trimmed.length,
			surface: "free_model_page",
		});

		const controller = new AbortController();
		abortRef.current = controller;

		try {
			const chatHistory = [...messages, userMsg].map((m) => ({
				role: m.role,
				content: m.content,
			}));

			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000"}/api/v1/public/anon-chat/stream`,
				{
					method: "POST",
					headers: { "Content-Type": "application/json" },
					credentials: "include",
					body: JSON.stringify({
						model_slug: model.seo_slug,
						messages: chatHistory,
					}),
					signal: controller.signal,
				}
			);

			if (!response.ok) {
				if (response.status === 429) {
					const errorData = await response.json();
					setQuota({
						used: errorData.detail?.used ?? quota?.limit ?? 1000000,
						limit: errorData.detail?.limit ?? quota?.limit ?? 1000000,
						remaining: 0,
						status: "exceeded",
						warning_threshold: quota?.warning_threshold ?? 800000,
					});
					setMessages((prev) => prev.filter((m) => m.id !== assistantId));
					return;
				}
				throw new Error(`Stream error: ${response.status}`);
			}

			for await (const event of readSSEStream(response)) {
				if (controller.signal.aborted) break;

				if (event.type === "text-delta") {
					setMessages((prev) =>
						prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + event.delta } : m))
					);
				} else if (event.type === "error") {
					setMessages((prev) =>
						prev.map((m) =>
							m.id === assistantId ? { ...m, content: m.content || event.errorText } : m
						)
					);
				} else if ("type" in event && event.type === "data-token-usage") {
					// After streaming completes, refresh quota
					anonymousChatApiService.getQuota().then(setQuota).catch(console.error);
				}
			}
		} catch (err) {
			if (err instanceof DOMException && err.name === "AbortError") return;
			console.error("Chat stream error:", err);
			setMessages((prev) =>
				prev.map((m) =>
					m.id === assistantId && !m.content
						? { ...m, content: "An error occurred. Please try again." }
						: m
				)
			);
		} finally {
			setIsStreaming(false);
			abortRef.current = null;
			anonymousChatApiService.getQuota().then(setQuota).catch(console.error);
		}
	}, [input, isStreaming, messages, model.seo_slug, quota]);

	const handleCancel = useCallback(() => {
		abortRef.current?.abort();
	}, []);

	const handleKeyDown = (e: React.KeyboardEvent) => {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			handleSubmit();
		}
	};

	const isExceeded = quota ? quota.used >= quota.limit : false;

	return (
		<div className="flex flex-col h-[calc(100vh-8rem)] max-w-3xl mx-auto">
			{quota && (
				<QuotaWarningBanner
					used={quota.used}
					limit={quota.limit}
					warningThreshold={quota.warning_threshold}
					className="mb-3"
				/>
			)}

			<div className="flex-1 overflow-y-auto space-y-4 pb-4 min-h-0">
				{messages.length === 0 && (
					<div className="flex flex-col items-center justify-center h-full text-center px-4">
						<div className="rounded-full bg-linear-to-r from-purple-500/10 to-blue-500/10 p-4 mb-4">
							<div className="h-10 w-10 rounded-full bg-linear-to-r from-purple-500 to-blue-500 flex items-center justify-center">
								<span className="text-white text-lg font-bold">
									{model.name.charAt(0).toUpperCase()}
								</span>
							</div>
						</div>
						<h2 className="text-xl font-semibold mb-2">{model.name}</h2>
						{model.description && (
							<p className="text-sm text-muted-foreground max-w-md">{model.description}</p>
						)}
						<p className="text-xs text-muted-foreground mt-4">
							Free to use &middot; No login required &middot; Start typing below
						</p>
					</div>
				)}

				{messages.map((msg) => (
					<div
						key={msg.id}
						className={cn("flex gap-3 px-4", msg.role === "user" ? "justify-end" : "justify-start")}
					>
						{msg.role === "assistant" && (
							<div className="h-7 w-7 rounded-full bg-linear-to-r from-purple-500 to-blue-500 flex items-center justify-center shrink-0 mt-0.5">
								<span className="text-white text-xs font-bold">
									{model.name.charAt(0).toUpperCase()}
								</span>
							</div>
						)}
						<div
							className={cn(
								"rounded-2xl px-4 py-2.5 max-w-[80%] text-sm leading-relaxed",
								msg.role === "user"
									? "bg-primary text-primary-foreground"
									: "bg-muted text-foreground"
							)}
						>
							{msg.role === "assistant" && !msg.content && isStreaming ? (
								<Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
							) : (
								<div className="whitespace-pre-wrap wrap-break-word">{msg.content}</div>
							)}
						</div>
					</div>
				))}
				<div ref={messagesEndRef} />
			</div>

			<div className="border-t pt-3 pb-2 space-y-2">
				{quota && (
					<QuotaBar
						used={quota.used}
						limit={quota.limit}
						warningThreshold={quota.warning_threshold}
					/>
				)}

				<div className="relative">
					<textarea
						ref={textareaRef}
						value={input}
						onChange={(e) => {
							setInput(e.target.value);
							autoResizeTextarea();
						}}
						onKeyDown={handleKeyDown}
						placeholder={
							isExceeded
								? "Token limit reached. Create a free account to continue."
								: `Message ${model.name}...`
						}
						disabled={isExceeded}
						rows={1}
						className={cn(
							"w-full resize-none rounded-xl border bg-background px-4 py-3 pr-12 text-sm",
							"placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring",
							"disabled:cursor-not-allowed disabled:opacity-50",
							"min-h-[44px] max-h-[200px]"
						)}
					/>
					{isStreaming ? (
						<button
							type="button"
							onClick={handleCancel}
							className="absolute right-2 bottom-2 flex h-8 w-8 items-center justify-center rounded-lg bg-foreground text-background transition-colors hover:opacity-80"
						>
							<Square className="h-3.5 w-3.5" fill="currentColor" />
						</button>
					) : (
						<button
							type="button"
							onClick={handleSubmit}
							disabled={!input.trim() || isExceeded}
							className="absolute right-2 bottom-2 flex h-8 w-8 items-center justify-center rounded-lg bg-foreground text-background transition-colors hover:opacity-80 disabled:opacity-40 disabled:cursor-not-allowed"
						>
							<ArrowUp className="h-4 w-4" />
						</button>
					)}
				</div>

				<p className="text-center text-[10px] text-muted-foreground">
					{model.name} via SurfSense &middot; Responses may be inaccurate
				</p>
			</div>
		</div>
	);
}
