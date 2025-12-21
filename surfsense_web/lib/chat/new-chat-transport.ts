/**
 * Custom ChatModelAdapter for the new-chat feature using LocalRuntime.
 * Connects directly to the FastAPI backend using the Vercel AI SDK Data Stream Protocol.
 */

import type { ChatModelAdapter, ChatModelRunOptions } from "@assistant-ui/react";
import { toast } from "sonner";
import { getBearerToken } from "@/lib/auth-utils";
import {
	isPodcastGenerating,
	looksLikePodcastRequest,
	setActivePodcastTaskId,
} from "@/lib/chat/podcast-state";

interface NewChatAdapterConfig {
	searchSpaceId: number;
	chatId: number;
}

/**
 * Represents an in-progress or completed tool call
 */
interface ToolCallState {
	toolCallId: string;
	toolName: string;
	args: Record<string, unknown>;
	result?: unknown;
}

/**
 * Tools that should render custom UI in the chat.
 * Other tools (like search_knowledge_base) will be hidden from the UI.
 */
const TOOLS_WITH_UI = new Set(["generate_podcast"]);

/**
 * Creates a ChatModelAdapter that connects to the FastAPI new_chat endpoint.
 *
 * The backend expects:
 * - POST /api/v1/new_chat
 * - Body: { chat_id: number, user_query: string, search_space_id: number }
 * - Returns: SSE stream with Vercel AI SDK Data Stream Protocol
 */
export function createNewChatAdapter(config: NewChatAdapterConfig): ChatModelAdapter {
	const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";

	return {
		async *run({ messages, abortSignal }: ChatModelRunOptions) {
			// Get the last user message
			const lastUserMessage = messages.filter((m) => m.role === "user").pop();

			if (!lastUserMessage) {
				throw new Error("No user message found");
			}

			// Extract text content from the message
			let userQuery = "";
			for (const part of lastUserMessage.content) {
				if (part.type === "text") {
					userQuery += part.text;
				}
			}

			if (!userQuery.trim()) {
				throw new Error("User query cannot be empty");
			}

			// Check if user is requesting a podcast while one is already generating
			if (isPodcastGenerating() && looksLikePodcastRequest(userQuery)) {
				toast.warning("A podcast is already being generated. Please wait for it to complete.");
				// Return a message telling the user to wait
				yield {
					content: [
						{
							type: "text",
							text: "A podcast is already being generated. Please wait for it to complete before requesting another one.",
						},
					],
				};
				return;
			}

			const token = getBearerToken();
			if (!token) {
				throw new Error("Not authenticated. Please log in again.");
			}

			const response = await fetch(`${backendUrl}/api/v1/new_chat`, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					Authorization: `Bearer ${token}`,
				},
				body: JSON.stringify({
					chat_id: config.chatId,
					user_query: userQuery.trim(),
					search_space_id: config.searchSpaceId,
				}),
				signal: abortSignal,
			});

			if (!response.ok) {
				const errorText = await response.text().catch(() => "Unknown error");
				throw new Error(`Backend error (${response.status}): ${errorText}`);
			}

			if (!response.body) {
				throw new Error("No response body");
			}

			// Parse the SSE stream (Vercel AI SDK Data Stream Protocol)
			const reader = response.body.getReader();
			const decoder = new TextDecoder();
			let buffer = "";
			let accumulatedText = "";

			// Track tool calls by their ID
			const toolCalls = new Map<string, ToolCallState>();

			/**
			 * Build the content array with text and tool calls.
			 * Only includes tools that have custom UI (defined in TOOLS_WITH_UI).
			 */
			function buildContent() {
				const content: Array<
					| { type: "text"; text: string }
					| { type: "tool-call"; toolCallId: string; toolName: string; args: Record<string, unknown>; result?: unknown }
				> = [];

				// Add text content if any
				if (accumulatedText) {
					content.push({ type: "text" as const, text: accumulatedText });
				}

				// Only add tool calls that have custom UI registered
				// Other tools (like search_knowledge_base) are hidden from the UI
				for (const toolCall of toolCalls.values()) {
					if (TOOLS_WITH_UI.has(toolCall.toolName)) {
						content.push({
							type: "tool-call" as const,
							toolCallId: toolCall.toolCallId,
							toolName: toolCall.toolName,
							args: toolCall.args,
							result: toolCall.result,
						});
					}
				}

				return content;
			}

			try {
				while (true) {
					const { done, value } = await reader.read();
					if (done) {
						break;
					}

					const chunk = decoder.decode(value, { stream: true });
					buffer += chunk;

					// Split on double newlines (handle both \n\n and \r\n\r\n)
					const events = buffer.split(/\r?\n\r?\n/);
					buffer = events.pop() || "";

					for (const event of events) {
						// Each event can have multiple lines, find the data line
						const lines = event.split(/\r?\n/);
						for (const line of lines) {
							if (!line.startsWith("data: ")) continue;

							const data = line.slice(6).trim(); // Remove "data: " prefix

							// Handle [DONE] marker
							if (data === "[DONE]") {
								continue;
							}

							if (!data) continue;

							try {
								const parsed = JSON.parse(data);

								// Handle different message types from the Data Stream Protocol
								switch (parsed.type) {
									case "text-delta":
										accumulatedText += parsed.delta;
										yield { content: buildContent() };
										break;

									case "tool-input-start": {
										// Tool call is starting - create a new tool call entry
										const { toolCallId, toolName } = parsed;
										toolCalls.set(toolCallId, {
											toolCallId,
											toolName,
											args: {},
										});
										// Yield to show tool is starting (running state)
										yield { content: buildContent() };
										break;
									}

									case "tool-input-available": {
										// Tool input is complete - update the args
										const { toolCallId, toolName, input } = parsed;
										const existing = toolCalls.get(toolCallId);
										if (existing) {
											existing.args = input || {};
										} else {
											// Create new entry if we missed tool-input-start
											toolCalls.set(toolCallId, {
												toolCallId,
												toolName,
												args: input || {},
											});
										}
										yield { content: buildContent() };
										break;
									}

									case "tool-output-available": {
										// Tool execution is complete - add the result
										const { toolCallId, output } = parsed;
										const existing = toolCalls.get(toolCallId);
										if (existing) {
											existing.result = output;

											// If this is a podcast tool with status="processing", set the state immediately
											// This ensures subsequent podcast requests are intercepted
											if (
												existing.toolName === "generate_podcast" &&
												output &&
												typeof output === "object" &&
												"status" in output &&
												output.status === "processing" &&
												"task_id" in output &&
												typeof output.task_id === "string"
											) {
												setActivePodcastTaskId(output.task_id);
											}
										}
										yield { content: buildContent() };
										break;
									}

									case "error":
										throw new Error(parsed.errorText || "Unknown error from server");

									// Other types like text-start, text-end, start-step, finish-step, etc.
									// are handled implicitly
									default:
										break;
								}
							} catch (e) {
								// Skip non-JSON lines
								if (e instanceof SyntaxError) {
									continue;
								}
								throw e;
							}
						}
					}
				}

				// Handle any remaining buffer
				if (buffer.trim()) {
					const lines = buffer.split(/\r?\n/);
					for (const line of lines) {
						if (line.startsWith("data: ")) {
							const data = line.slice(6).trim();
							if (data && data !== "[DONE]") {
								try {
									const parsed = JSON.parse(data);
									if (parsed.type === "text-delta") {
										accumulatedText += parsed.delta;
										yield { content: buildContent() };
									} else if (parsed.type === "tool-output-available") {
										const { toolCallId, output } = parsed;
										const existing = toolCalls.get(toolCallId);
										if (existing) {
											existing.result = output;

											// Set podcast state if processing
											if (
												existing.toolName === "generate_podcast" &&
												output &&
												typeof output === "object" &&
												"status" in output &&
												output.status === "processing" &&
												"task_id" in output &&
												typeof output.task_id === "string"
											) {
												setActivePodcastTaskId(output.task_id);
											}
										}
										yield { content: buildContent() };
									}
								} catch {
									// Ignore parse errors
								}
							}
						}
					}
				}
			} finally {
				reader.releaseLock();
			}
		},
	};
}
