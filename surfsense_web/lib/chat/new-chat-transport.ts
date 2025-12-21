/**
 * Custom ChatModelAdapter for the new-chat feature using LocalRuntime.
 * Connects directly to the FastAPI backend using the Vercel AI SDK Data Stream Protocol.
 */

import type { ChatModelAdapter, ChatModelRunOptions } from "@assistant-ui/react";
import { getBearerToken } from "@/lib/auth-utils";

interface NewChatAdapterConfig {
	searchSpaceId: number;
	chatId: number;
}

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
										yield {
											content: [{ type: "text" as const, text: accumulatedText }],
										};
										break;

									case "error":
										throw new Error(parsed.errorText || "Unknown error from server");

									// Other types like text-start, text-end, tool-*, etc.
									// are handled implicitly - we just accumulate text deltas
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
										yield {
											content: [{ type: "text" as const, text: accumulatedText }],
										};
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
