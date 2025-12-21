import type { UIMessage } from "ai";

export const maxDuration = 30;

export async function POST(req: Request) {
	try {
		const body = await req.json();
		const {
			messages,
			chat_id,
			search_space_id,
		}: {
			messages: UIMessage[];
			chat_id?: number;
			search_space_id?: number;
		} = body;

		// Get auth token from headers
		const authHeader = req.headers.get("authorization");
		if (!authHeader) {
			return new Response("Unauthorized", { status: 401 });
		}

		// Get the last user message
		const lastUserMessage = messages.filter((m) => m.role === "user").pop();

		if (!lastUserMessage) {
			return new Response("No user message found", { status: 400 });
		}

		// Extract text content from the message
		const userQuery =
			typeof lastUserMessage.content === "string"
				? lastUserMessage.content
				: lastUserMessage.content
						.filter((c: any) => c.type === "text")
						.map((c: any) => c.text)
						.join(" ");

		// Call the DeepAgent backend
		const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
		const response = await fetch(`${backendUrl}/api/v1/new_chat`, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				Authorization: authHeader,
			},
			body: JSON.stringify({
				chat_id: chat_id || 0,
				user_query: userQuery,
				search_space_id: search_space_id || 0,
			}),
		});

		if (!response.ok) {
			return new Response(`Backend error: ${response.statusText}`, {
				status: response.status,
			});
		}

		// The backend returns SSE stream with Vercel AI SDK Data Stream Protocol
		// We need to forward this stream to the client
		return new Response(response.body, {
			headers: {
				"Content-Type": "text/event-stream",
				"Cache-Control": "no-cache",
				Connection: "keep-alive",
			},
		});
	} catch (error) {
		console.error("Error in deep-agent-chat route:", error);
		return new Response("Internal Server Error", { status: 500 });
	}
}
